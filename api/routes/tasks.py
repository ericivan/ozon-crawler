import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models import KeywordTask, OzonProduct, OzonAnalysis

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskCreate(BaseModel):
    keyword_cn: str
    keyword_ru: str


class TaskResponse(BaseModel):
    id: int
    keyword_cn: str
    keyword_ru: str
    status: str
    created_at: str
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


@router.get("")
async def list_tasks(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(KeywordTask).order_by(KeywordTask.created_at.desc())
    if status:
        stmt = stmt.where(KeywordTask.status == status)
    result = await db.execute(stmt)
    tasks = result.scalars().all()
    return [
        {
            "id": t.id,
            "keyword_cn": t.keyword_cn,
            "keyword_ru": t.keyword_ru,
            "status": t.status,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        }
        for t in tasks
    ]


@router.post("")
async def create_task(body: TaskCreate, db: AsyncSession = Depends(get_db)):
    task = KeywordTask(
        keyword_cn=body.keyword_cn,
        keyword_ru=body.keyword_ru,
        status="pending",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return {
        "id": task.id,
        "keyword_cn": task.keyword_cn,
        "keyword_ru": task.keyword_ru,
        "status": task.status,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }


@router.get("/{task_id}")
async def get_task(task_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(KeywordTask).where(KeywordTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    products_result = await db.execute(
        select(OzonProduct).where(OzonProduct.task_id == task_id)
    )
    products = products_result.scalars().all()

    analysis_result = await db.execute(
        select(OzonAnalysis).where(OzonAnalysis.task_id == task_id)
    )
    analysis = analysis_result.scalars().all()

    return {
        "id": task.id,
        "keyword_cn": task.keyword_cn,
        "keyword_ru": task.keyword_ru,
        "status": task.status,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        "products_count": len(products),
        "analysis_count": len(analysis),
    }


@router.delete("/{task_id}")
async def delete_task(task_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(KeywordTask).where(KeywordTask.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    await db.execute(delete(OzonProduct).where(OzonProduct.task_id == task_id))
    await db.execute(delete(OzonAnalysis).where(OzonAnalysis.task_id == task_id))
    await db.execute(delete(KeywordTask).where(KeywordTask.id == task_id))
    await db.commit()
    return {"message": "Task deleted", "id": task_id}
