"""NewsRadar API — FastAPI entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.core.logging_config import get_logger, setup_logging
from src.infrastructure.database.session import dispose_engine
from src.infrastructure.database.settings import settings
from src.infrastructure.scheduler.sync_jobs import (
    bootstrap_if_needed,
    start_scheduler,
    stop_scheduler,
)
from src.presentation.routers import (
    feed_router,
    github_router,
    google_news_router,
    youtube_router,
)

setup_logging(settings.log_level)
logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Radar API iniciando (env=%s)", settings.app_env)

    start_scheduler()
    await bootstrap_if_needed()

    yield

    stop_scheduler()
    await dispose_engine()
    logger.info("🛑 Radar API apagándose")


app = FastAPI(
    title="Radar API",
    description="Agregador de noticias sobre IA — Angular + FastAPI",
    version="0.2.0",
    lifespan=lifespan,
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(youtube_router.router, prefix="/api/youtube", tags=["YouTube"])
app.include_router(google_news_router.router, prefix="/api/news", tags=["Google News"])
app.include_router(github_router.router, prefix="/api/github", tags=["GitHub"])
app.include_router(feed_router.router, prefix="/api", tags=["Feed"])


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Evita filtrar tracebacks al cliente en produccion, pero si los registra."""
    logger.exception("Error no controlado en %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Error interno del servidor. Revisa los logs del backend."},
    )


@app.get("/health", tags=["System"])
async def health_check():
    """Health check. Incluye el estado del scheduler para el dashboard."""
    from src.infrastructure.scheduler.sync_jobs import scheduler

    return {
        "status": "ok",
        "env": settings.app_env,
        "scheduler_running": scheduler.running,
        "sync_interval_minutes": settings.sync_interval_minutes,
    }


@app.get("/", include_in_schema=False)
async def root():
    return {
        "name": "Radar API",
        "version": "0.2.0",
        "docs": "/docs",
        "health": "/health",
    }