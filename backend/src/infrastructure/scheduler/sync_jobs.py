"""Sincronizacion periodica con APScheduler.

Reemplaza el auto-sync "si la DB esta vacia y hace mas de 1h" del proyecto
original por un intervalo configurable (`SYNC_INTERVAL_MINUTES`), mas una pasada
diaria a una hora fija. Ademas dispara un sync en background en el arranque para
que la app no salga vacia.
"""

import asyncio
from collections.abc import Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import func, select

from src.core.logging_config import get_logger
from src.infrastructure.database.models import (
    GitHubRepoModel,
    GoogleNewsArticleModel,
    YouTubeVideoModel,
)
from src.infrastructure.database.session import AsyncSessionLocal
from src.infrastructure.database.settings import settings

logger = get_logger(__name__)

DAILY_SYNC_HOUR = 7
DAILY_SYNC_MINUTE = 0

scheduler = AsyncIOScheduler(timezone="UTC")

SyncFn = Callable[[], Awaitable[dict]]


async def _run_sync(name: str, sync_fn: SyncFn) -> None:
    """Ejecuta un sync en su propia sesion de DB, aislando los fallos."""
    logger.info("⏱  Scheduler: iniciando sync de %s", name)
    try:
        result = await sync_fn()
        logger.info("✅ Scheduler: %s -> %d items", name, result.get("items_synced", 0))
    except Exception as exc:  # noqa: BLE001 - un fallo no debe parar el scheduler
        logger.error("❌ Scheduler: fallo el sync de %s: %s", name, exc)


async def sync_youtube_job() -> None:
    from src.application.services.youtube_service import YouTubeService

    async def run() -> dict:
        async with AsyncSessionLocal() as session:
            return await YouTubeService(session).sync_videos()

    await _run_sync("youtube", run)


async def sync_news_job() -> None:
    from src.application.services.google_news_service import GoogleNewsService

    async def run() -> dict:
        async with AsyncSessionLocal() as session:
            return await GoogleNewsService(session).sync_articles()

    await _run_sync("news", run)


async def sync_github_job() -> None:
    from src.application.services.github_service import GitHubService

    async def run() -> dict:
        async with AsyncSessionLocal() as session:
            return await GitHubService(session).sync_repos()

    await _run_sync("github", run)


async def sync_all_job() -> None:
    """Sync de las tres fuentes, en serie (respetan el rate limit de cada API)."""
    for job in (sync_youtube_job, sync_news_job, sync_github_job):
        await job()


def start_scheduler() -> None:
    """Arranca los jobs periodicos. Idempotente."""
    if scheduler.running:
        return

    scheduler.add_job(
        sync_all_job,
        trigger=IntervalTrigger(minutes=settings.sync_interval_minutes),
        id="sync_interval",
        name="Sync periodico de todas las fuentes",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )

    scheduler.add_job(
        sync_all_job,
        trigger=CronTrigger(hour=DAILY_SYNC_HOUR, minute=DAILY_SYNC_MINUTE),
        id="sync_daily",
        name=f"Sync diario {DAILY_SYNC_HOUR:02d}:{DAILY_SYNC_MINUTE:02d} UTC",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    scheduler.start()
    logger.info(
        "Scheduler arrancado: cada %d min + diario %02d:%02d UTC",
        settings.sync_interval_minutes,
        DAILY_SYNC_HOUR,
        DAILY_SYNC_MINUTE,
    )


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler detenido")


async def _needs_initial_sync() -> tuple[bool, str]:
    """¿Alguna fuente esta vacia o su ultima sync es vieja?

    Devuelve (necesita_sync, descripcion). Cualquier error de DB se traduce a
    False: el bootstrap no debe impedir que la app arranque.
    """
    from src.core.use_cases.update_source_config import needs_initial_sync
    from src.infrastructure.database.repositories.github_pg_repo import GitHubRepository
    from src.infrastructure.database.repositories.google_news_pg_repo import (
        GoogleNewsRepository,
    )
    from src.infrastructure.database.repositories.youtube_pg_repo import YouTubeRepository

    stale_minutes = settings.sync_interval_minutes

    async with AsyncSessionLocal() as session:
        checks = (
            ("youtube", YouTubeVideoModel, YouTubeRepository),
            ("news", GoogleNewsArticleModel, GoogleNewsRepository),
            ("github", GitHubRepoModel, GitHubRepository),
        )

        for name, model, repo_factory in checks:
            total = (await session.execute(select(func.count()).select_from(model))).scalar_one()
            config = await repo_factory(session).get_config()

            if total == 0:
                return True, f"{name}: vacio (0 items)"
            if needs_initial_sync(config.last_search_at, stale_minutes):
                return True, (
                    f"{name}: last_search_at={config.last_search_at} "
                    f"antigua (>{stale_minutes} min)"
                )

    return False, "todas las fuentes estan al dia"


async def bootstrap_if_needed() -> None:
    """Al arrancar, sincroniza en background si alguna fuente lo necesita.

    No bloquea el arranque: /health responde de inmediato.
    """
    try:
        needed, reason = await _needs_initial_sync()
    except Exception as exc:  # noqa: BLE001
        logger.error("Bootstrap: no se pudo comprobar el estado: %s", exc)
        return

    if not needed:
        logger.info("Bootstrap: sin sync inicial necesario (%s)", reason)
        return

    logger.info("Bootstrap: sync inicial necesario -> %s", reason)
    asyncio.create_task(_delayed_sync_all())


async def _delayed_sync_all() -> None:
    """Espera unos segundos para no competir con el arranque de la app."""
    await asyncio.sleep(3)
    await sync_all_job()