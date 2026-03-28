import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models import KeywordTask, OzonProduct
from analyzer.claude_client import suggest_keywords
from scraper.ozon_scraper import OzonScraper

logger = logging.getLogger(__name__)
router = APIRouter(tags=["keywords"])


class ScrapeRequest(BaseModel):
    task_id: int


async def run_scrape_task(task_id: int):
    from api.database import AsyncSessionLocal
    from analyzer.claude_client import analyze_products

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(KeywordTask).where(KeywordTask.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            logger.error(f"Task {task_id} not found for scraping")
            return

        task.status = "running"
        await db.commit()

        try:
            scraper = OzonScraper()
            products = await scraper.scrape(task_id, task.keyword_ru, db)

            if products:
                task.status = "done"
                await db.commit()

                products_data = [
                    {
                        "title": p.title,
                        "price": float(p.price) if p.price else None,
                        "review_count": p.review_count,
                        "rating": float(p.rating) if p.rating else None,
                        "seller": p.seller,
                        "product_url": p.product_url,
                    }
                    for p in products
                ]
                await analyze_products(
                    task_id=task_id,
                    keyword_ru=task.keyword_ru,
                    keyword_cn=task.keyword_cn,
                    products=products_data,
                    db=db,
                )
            else:
                task.status = "failed"
                await db.commit()

        except Exception as e:
            logger.exception(f"Scrape task {task_id} failed: {e}")
            task.status = "failed"
            await db.commit()


@router.post("/scrape/trigger")
async def trigger_scrape(
    body: ScrapeRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(KeywordTask).where(KeywordTask.id == body.task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status == "running":
        raise HTTPException(status_code=400, detail="Task is already running")

    background_tasks.add_task(run_scrape_task, body.task_id)
    return {"message": "Scrape triggered", "task_id": body.task_id}


@router.get("/keywords/suggest")
async def keyword_suggest(
    product_name_cn: str,
    attributes: Optional[str] = "",
    target_user: Optional[str] = "",
    price_range: Optional[str] = "",
):
    try:
        result = await suggest_keywords(
            product_name_cn=product_name_cn,
            attributes=attributes or "",
            target_user=target_user or "",
            price_range=price_range or "",
        )
        return {"keywords": result}
    except Exception as e:
        logger.exception(f"Keyword suggest failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
