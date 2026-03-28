import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models import OzonAnalysis, KeywordTask

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analysis", tags=["analysis"])


def serialize_analysis(a: OzonAnalysis) -> dict:
    return {
        "id": a.id,
        "task_id": a.task_id,
        "keyword_ru": a.keyword_ru,
        "competition_level": a.competition_level,
        "opportunity_score": a.opportunity_score,
        "summary": a.summary,
        "price_analysis": a.price_analysis,
        "gap_opportunities": a.gap_opportunities,
        "keywords_recommend": a.keywords_recommend,
        "action_conclusion": a.action_conclusion,
        "action_reason": a.action_reason,
        "next_step": a.next_step,
        "analyzed_at": a.analyzed_at.isoformat() if a.analyzed_at else None,
    }


@router.get("")
async def list_analysis(
    conclusion: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(OzonAnalysis).order_by(OzonAnalysis.analyzed_at.desc())
    if conclusion:
        stmt = stmt.where(OzonAnalysis.action_conclusion == conclusion)
    result = await db.execute(stmt)
    analyses = result.scalars().all()
    return [serialize_analysis(a) for a in analyses]


@router.get("/{task_id}")
async def get_analysis_by_task(task_id: int, db: AsyncSession = Depends(get_db)):
    task_result = await db.execute(select(KeywordTask).where(KeywordTask.id == task_id))
    task = task_result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    result = await db.execute(
        select(OzonAnalysis)
        .where(OzonAnalysis.task_id == task_id)
        .order_by(OzonAnalysis.analyzed_at.desc())
    )
    analyses = result.scalars().all()
    if not analyses:
        raise HTTPException(status_code=404, detail="Analysis not found for this task")

    return {
        "task": {
            "id": task.id,
            "keyword_cn": task.keyword_cn,
            "keyword_ru": task.keyword_ru,
            "status": task.status,
        },
        "analyses": [serialize_analysis(a) for a in analyses],
    }
