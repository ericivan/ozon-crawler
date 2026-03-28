import json
import logging
from typing import Any, Optional

import anthropic
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from analyzer.prompts import (
    ANALYZE_PRODUCTS_SYSTEM, ANALYZE_PRODUCTS_USER,
    SUGGEST_KEYWORDS_SYSTEM, SUGGEST_KEYWORDS_USER,
    ANALYZE_REVIEWS_SYSTEM, ANALYZE_REVIEWS_USER,
    BATCH_RANK_SYSTEM, BATCH_RANK_USER,
)

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 2000


def _get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def _clean_json_response(text: str) -> str:
    """Remove markdown code fences and strip whitespace."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove opening fence (```json or ```)
        lines = lines[1:]
        # Remove closing fence
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _call_claude(system: str, user: str) -> str:
    """Call Claude API and return the raw text response."""
    client = _get_client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text


def _parse_with_retry(system: str, user: str) -> Any:
    """Call Claude and parse JSON, retrying once on failure."""
    for attempt in range(2):
        raw = _call_claude(system, user)
        cleaned = _clean_json_response(raw)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse failed (attempt {attempt + 1}): {e}\nRaw: {cleaned[:300]}")
            if attempt == 1:
                raise RuntimeError(
                    f"Failed to parse Claude response as JSON after 2 attempts. "
                    f"Last error: {e}"
                )
    return None  # Unreachable


async def analyze_products(
    task_id: int,
    keyword_ru: str,
    keyword_cn: str,
    products: list[dict],
    db: AsyncSession,
) -> None:
    """
    Analyze scraped products with Claude and persist result to ozon_analysis.
    """
    from api.models import OzonAnalysis

    limited = products[:50]
    user_prompt = ANALYZE_PRODUCTS_USER.format(
        keyword_ru=keyword_ru,
        keyword_cn=keyword_cn,
        total_count=len(products),
        json_data=json.dumps(limited, ensure_ascii=False, indent=2),
    )

    data = _parse_with_retry(ANALYZE_PRODUCTS_SYSTEM, user_prompt)
    action = data.get("action", {})

    analysis = OzonAnalysis(
        task_id=task_id,
        keyword_ru=keyword_ru,
        competition_level=data.get("competition_level"),
        opportunity_score=data.get("opportunity_score"),
        summary=data.get("summary"),
        price_analysis=data.get("price_analysis"),
        gap_opportunities=data.get("gap_opportunities"),
        keywords_recommend=data.get("keywords_recommend"),
        action_conclusion=action.get("conclusion"),
        action_reason=action.get("reason"),
        next_step=action.get("next_step"),
    )
    db.add(analysis)
    await db.commit()
    logger.info(
        f"Analysis saved for task {task_id}: "
        f"competition={analysis.competition_level}, "
        f"score={analysis.opportunity_score}, "
        f"conclusion={analysis.action_conclusion}"
    )


async def suggest_keywords(
    product_name_cn: str,
    attributes: str,
    target_user: str,
    price_range: str,
) -> list[dict]:
    """Generate Russian keyword suggestions for a product."""
    user_prompt = SUGGEST_KEYWORDS_USER.format(
        product_name_cn=product_name_cn,
        attributes=attributes,
        target_user=target_user,
        price_range=price_range,
    )
    result = _parse_with_retry(SUGGEST_KEYWORDS_SYSTEM, user_prompt)
    if not isinstance(result, list):
        raise RuntimeError(f"Expected JSON array from suggest_keywords, got: {type(result)}")
    return result


async def analyze_reviews(
    keyword_ru: str,
    reviews: list[str],
) -> dict:
    """Analyze consumer reviews and extract pain points / opportunities."""
    limited = reviews[:50]
    user_prompt = ANALYZE_REVIEWS_USER.format(
        keyword_ru=keyword_ru,
        reviews_json=json.dumps(limited, ensure_ascii=False, indent=2),
    )
    return _parse_with_retry(ANALYZE_REVIEWS_SYSTEM, user_prompt)


async def batch_rank(summaries: list[dict]) -> dict:
    """
    Rank multiple keyword summaries by composite score.
    summaries: list of dicts with keyword info and analysis data.
    """
    user_prompt = BATCH_RANK_USER.format(
        total=len(summaries),
        batch_summary_json=json.dumps(summaries, ensure_ascii=False, indent=2),
    )
    return _parse_with_retry(BATCH_RANK_SYSTEM, user_prompt)
