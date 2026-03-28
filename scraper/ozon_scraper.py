import asyncio
import json
import logging
import random
from typing import Optional
from urllib.parse import quote

from playwright.async_api import async_playwright, Page, Response, BrowserContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import OzonProduct, KeywordTask
from config import settings
from scraper.proxy_manager import ProxyManager

logger = logging.getLogger(__name__)

OZON_SEARCH_URL = "https://www.ozon.ru/search/?text={query}&page={page}"


class OzonScraper:
    def __init__(self):
        self.proxy_manager = ProxyManager()
        self._intercepted_products: list[dict] = []
        self._intercept_success = False

    async def scrape(
        self,
        task_id: int,
        keyword_ru: str,
        db: AsyncSession,
    ) -> list[OzonProduct]:
        """
        抓取 Ozon 搜索结果。
        优先拦截内部 API JSON，降级使用 CSS 选择器。
        最多重试 proxy_manager._max_attempts 次（IP 封禁时切换代理）。
        """
        self.proxy_manager.reset()
        products: list[OzonProduct] = []

        while self.proxy_manager.can_retry():
            self.proxy_manager.record_attempt()
            try:
                products = await self._do_scrape(task_id, keyword_ru, db)
                break
            except CaptchaError:
                logger.warning(f"Captcha detected for task {task_id}. Marking as failed.")
                raise
            except BannedError:
                if self.proxy_manager.can_retry():
                    logger.warning(
                        f"IP banned (attempt {self.proxy_manager.attempts}). "
                        "Retrying with proxy..."
                    )
                    await asyncio.sleep(3)
                else:
                    logger.error("Max proxy retries reached. Giving up.")
                    raise
            except Exception as e:
                logger.exception(f"Scrape failed on attempt {self.proxy_manager.attempts}: {e}")
                raise

        return products

    async def _do_scrape(
        self,
        task_id: int,
        keyword_ru: str,
        db: AsyncSession,
    ) -> list[OzonProduct]:
        proxy = self.proxy_manager.get_playwright_proxy()
        products: list[OzonProduct] = []

        async with async_playwright() as pw:
            browser_args = {
                "headless": True,
                "args": [
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-blink-features=AutomationControlled",
                ],
            }
            if proxy:
                browser_args["proxy"] = proxy

            browser = await pw.chromium.launch(**browser_args)
            context: BrowserContext = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="ru-RU",
                viewport={"width": 1366, "height": 768},
            )

            try:
                for page_num in range(1, settings.SCRAPE_MAX_PAGES + 1):
                    self._intercepted_products = []
                    self._intercept_success = False

                    page: Page = await context.new_page()
                    page.on("response", self._handle_response)

                    url = OZON_SEARCH_URL.format(
                        query=quote(keyword_ru), page=page_num
                    )
                    logger.info(f"Scraping page {page_num}: {url}")

                    try:
                        await page.goto(url, wait_until="networkidle", timeout=30000)
                    except Exception as e:
                        logger.warning(f"Page load timeout/error: {e}")

                    # Check for captcha
                    if await self._has_captcha(page):
                        await page.close()
                        raise CaptchaError("Captcha detected")

                    # Check for IP ban
                    if await self._is_banned(page):
                        await page.close()
                        raise BannedError("IP banned")

                    # Wait briefly to allow JS response handlers to fire
                    await asyncio.sleep(1)

                    if self._intercept_success and self._intercepted_products:
                        logger.info(
                            f"Page {page_num}: intercepted "
                            f"{len(self._intercepted_products)} products via API"
                        )
                        page_products = self._intercepted_products[:]
                    else:
                        logger.info(f"Page {page_num}: falling back to CSS scraping")
                        page_products = await self._scrape_with_css(page)

                    await page.close()

                    # Persist products
                    for item in page_products:
                        product = OzonProduct(
                            task_id=task_id,
                            keyword_ru=keyword_ru,
                            title=item.get("title"),
                            price=item.get("price"),
                            review_count=item.get("review_count", 0),
                            rating=item.get("rating"),
                            seller=item.get("seller"),
                            product_url=item.get("product_url"),
                        )
                        db.add(product)
                        products.append(product)

                    await db.commit()

                    if not page_products:
                        logger.info("No products found on this page, stopping pagination.")
                        break

                    # Random delay between pages
                    delay = random.uniform(settings.SCRAPE_DELAY_MIN, settings.SCRAPE_DELAY_MAX)
                    logger.info(f"Waiting {delay:.1f}s before next page...")
                    await asyncio.sleep(delay)

            finally:
                await context.close()
                await browser.close()

        # Reload persisted products with IDs
        from sqlalchemy import select as sa_select
        result = await db.execute(
            sa_select(OzonProduct).where(OzonProduct.task_id == task_id)
        )
        return result.scalars().all()

    async def _handle_response(self, response: Response):
        """Intercept Ozon internal API responses."""
        url = response.url
        if not (
            ("api/composer" in url or "/search" in url)
            and "ozon.ru" in url
        ):
            return

        try:
            content_type = response.headers.get("content-type", "")
            if "application/json" not in content_type:
                return

            body = await response.json()
            extracted = self._parse_api_response(body)
            if extracted:
                self._intercepted_products.extend(extracted)
                self._intercept_success = True
        except Exception:
            pass  # Silently ignore parse failures; CSS fallback will handle it

    def _parse_api_response(self, body: dict) -> list[dict]:
        """Parse Ozon composer / search API JSON for product data."""
        products = []

        # Attempt to navigate common Ozon API structures
        # The actual structure varies by API version; we try multiple paths
        items = []

        if isinstance(body, dict):
            # composer-api structure
            for widget in body.get("widgetStates", {}).values():
                try:
                    data = json.loads(widget) if isinstance(widget, str) else widget
                    if isinstance(data, dict):
                        items.extend(data.get("items", []))
                        items.extend(data.get("products", []))
                except Exception:
                    continue

            # search API structure
            items.extend(body.get("items", []))
            items.extend(body.get("products", []))

        for item in items:
            if not isinstance(item, dict):
                continue
            product = self._extract_product_from_item(item)
            if product:
                products.append(product)

        return products

    def _extract_product_from_item(self, item: dict) -> Optional[dict]:
        """Extract normalized product dict from a raw API item."""
        title = (
            item.get("name")
            or item.get("title")
            or item.get("displayName")
        )
        if not title:
            return None

        price_raw = (
            item.get("price")
            or item.get("finalPrice")
            or item.get("pricePerUnit")
        )
        price = None
        if isinstance(price_raw, (int, float)):
            price = float(price_raw)
        elif isinstance(price_raw, dict):
            price = float(price_raw.get("value", 0) or 0) or None

        review_count = item.get("reviewsCount") or item.get("countReviews") or 0
        rating = item.get("rating") or item.get("reviewRating")
        if rating:
            try:
                rating = float(str(rating).replace(",", "."))
            except Exception:
                rating = None

        seller = item.get("seller", {})
        if isinstance(seller, dict):
            seller = seller.get("name") or seller.get("title")

        url = item.get("url") or item.get("link") or ""
        if url and not url.startswith("http"):
            url = f"https://www.ozon.ru{url}"

        return {
            "title": str(title)[:500],
            "price": price,
            "review_count": int(review_count) if review_count else 0,
            "rating": rating,
            "seller": str(seller)[:200] if seller else None,
            "product_url": url[:2000] if url else None,
        }

    async def _scrape_with_css(self, page: Page) -> list[dict]:
        """Fallback CSS-based scraping."""
        products = []
        try:
            await page.wait_for_selector(
                '[data-widget="searchResultsV2"]', timeout=10000
            )
        except Exception:
            logger.warning("searchResultsV2 widget not found; page may be empty")
            return products

        items = await page.query_selector_all(
            '[data-widget="searchResultsV2"] > div > div'
        )

        for item in items:
            try:
                title_el = await item.query_selector("span.tsBody500Medium, a[data-prerender]")
                title = await title_el.inner_text() if title_el else None

                price_el = await item.query_selector("span.price-number, [class*='price']")
                price_text = await price_el.inner_text() if price_el else ""
                price = self._parse_price(price_text)

                review_el = await item.query_selector("[class*='review'], [class*='rating-count']")
                review_text = await review_el.inner_text() if review_el else "0"
                review_count = self._parse_int(review_text)

                rating_el = await item.query_selector("[class*='rating'] span")
                rating_text = await rating_el.inner_text() if rating_el else ""
                rating = self._parse_float(rating_text)

                seller_el = await item.query_selector("[class*='seller'], [class*='brand']")
                seller = await seller_el.inner_text() if seller_el else None

                link_el = await item.query_selector("a[href*='/product/']")
                href = await link_el.get_attribute("href") if link_el else ""
                url = f"https://www.ozon.ru{href}" if href and not href.startswith("http") else href

                if title:
                    products.append({
                        "title": title.strip()[:500],
                        "price": price,
                        "review_count": review_count,
                        "rating": rating,
                        "seller": seller.strip()[:200] if seller else None,
                        "product_url": url[:2000] if url else None,
                    })
            except Exception as e:
                logger.debug(f"Failed to parse CSS item: {e}")
                continue

        logger.info(f"CSS scraping found {len(products)} products")
        return products

    def _parse_price(self, text: str) -> Optional[float]:
        if not text:
            return None
        cleaned = "".join(c for c in text if c.isdigit() or c in ".,")
        cleaned = cleaned.replace(",", ".").strip(".")
        try:
            return float(cleaned) if cleaned else None
        except ValueError:
            return None

    def _parse_int(self, text: str) -> int:
        if not text:
            return 0
        digits = "".join(c for c in text if c.isdigit())
        return int(digits) if digits else 0

    def _parse_float(self, text: str) -> Optional[float]:
        if not text:
            return None
        try:
            return float(text.strip().replace(",", "."))
        except ValueError:
            return None

    async def _has_captcha(self, page: Page) -> bool:
        try:
            el = await page.query_selector("[class*='captcha'], #captcha, .robot-check")
            if el:
                return True
            content = await page.content()
            return "captcha" in content.lower() or "robot" in content.lower()
        except Exception:
            return False

    async def _is_banned(self, page: Page) -> bool:
        try:
            status_code = getattr(page, "_last_status", None)
            if status_code and status_code in (403, 429):
                return True
            content = await page.content()
            return "access denied" in content.lower() or "заблокирован" in content.lower()
        except Exception:
            return False


class CaptchaError(Exception):
    pass


class BannedError(Exception):
    pass
