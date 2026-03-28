import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.database import init_db
from api.routes.tasks import router as tasks_router
from api.routes.analysis import router as analysis_router
from api.routes.keywords import router as keywords_router
from scheduler.tasks import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up: initializing DB and scheduler")
    await init_db()
    start_scheduler()
    yield
    logger.info("Shutting down: stopping scheduler")
    stop_scheduler()


app = FastAPI(
    title="Ozon Analyzer API",
    description="Ozon 电商选品分析系统",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tasks_router)
app.include_router(analysis_router)
app.include_router(keywords_router)


@app.get("/")
async def root():
    return {"message": "Ozon Analyzer API is running"}


@app.get("/health")
async def health():
    return {"status": "ok"}
