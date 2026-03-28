import asyncio
import logging
from datetime import datetime, date

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None


def _run_async(coro):
    """Run an async coroutine in a new event loop (called from sync APScheduler thread)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _process_pending_tasks():
    """每小时：依次处理所有 pending 任务。"""
    from api.database import AsyncSessionLocal
    from api.models import KeywordTask
    from sqlalchemy import select
    from api.routes.keywords import run_scrape_task

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(KeywordTask).where(KeywordTask.status == "pending")
        )
        tasks = result.scalars().all()
        task_ids = [t.id for t in tasks]

    if not task_ids:
        logger.info("[Scheduler] No pending tasks found.")
        return

    logger.info(f"[Scheduler] Processing {len(task_ids)} pending task(s): {task_ids}")
    for task_id in task_ids:
        try:
            await run_scrape_task(task_id)
        except Exception as e:
            logger.exception(f"[Scheduler] Task {task_id} failed: {e}")


async def _daily_batch_rank():
    """每天 02:00：对当天所有已完成 task 执行 batch_rank 并写日志。"""
    from api.database import AsyncSessionLocal
    from api.models import KeywordTask, OzonAnalysis
    from sqlalchemy import select, and_, func
    from analyzer.claude_client import batch_rank

    today = date.today()
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(KeywordTask).where(
                and_(
                    KeywordTask.status == "done",
                    func.date(KeywordTask.updated_at) == today,
                )
            )
        )
        tasks = result.scalars().all()

    if not tasks:
        logger.info(f"[Scheduler] No done tasks for today ({today}).")
        return

    summaries = []
    async with AsyncSessionLocal() as db:
        for task in tasks:
            analysis_result = await db.execute(
                select(OzonAnalysis)
                .where(OzonAnalysis.task_id == task.id)
                .order_by(OzonAnalysis.analyzed_at.desc())
                .limit(1)
            )
            analysis = analysis_result.scalar_one_or_none()
            if analysis:
                summaries.append({
                    "keyword_ru": task.keyword_ru,
                    "keyword_cn": task.keyword_cn,
                    "opportunity_score": analysis.opportunity_score,
                    "competition_level": analysis.competition_level,
                    "action_conclusion": analysis.action_conclusion,
                    "price_analysis": analysis.price_analysis,
                    "gap_count": len(analysis.gap_opportunities or []),
                })

    if not summaries:
        logger.info("[Scheduler] No analysis data available for batch rank.")
        return

    try:
        ranked = await batch_rank(summaries)
        logger.info(
            f"[Scheduler] Batch rank completed for {today}. "
            f"Top pick: {ranked.get('top_pick')}. "
            f"Insight: {ranked.get('weekly_insight')}"
        )
        logger.info(f"[Scheduler] Full batch rank result: {ranked}")
    except Exception as e:
        logger.exception(f"[Scheduler] Batch rank failed: {e}")


def _hourly_job():
    logger.info("[Scheduler] Hourly job triggered: processing pending tasks")
    _run_async(_process_pending_tasks())


def _daily_job():
    logger.info("[Scheduler] Daily job triggered: batch rank")
    _run_async(_daily_batch_rank())


def start_scheduler():
    global _scheduler
    _scheduler = BackgroundScheduler(timezone="Asia/Shanghai")

    _scheduler.add_job(
        _hourly_job,
        trigger=IntervalTrigger(hours=1),
        id="hourly_scrape",
        name="Process pending tasks every hour",
        replace_existing=True,
    )

    _scheduler.add_job(
        _daily_job,
        trigger=CronTrigger(hour=2, minute=0),
        id="daily_batch_rank",
        name="Daily batch rank at 02:00",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("[Scheduler] APScheduler started with 2 jobs.")


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[Scheduler] APScheduler stopped.")
