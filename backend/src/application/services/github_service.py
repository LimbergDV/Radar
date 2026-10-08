"""Servicio de aplicacion para GitHub."""

import time
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.entities.github import GitHubRepo
from src.core.logging_config import get_logger
from src.infrastructure.database.repositories.github_pg_repo import GitHubRepository
from src.infrastructure.database.settings import settings
from src.infrastructure.external.github_api import GitHubFetcher

logger = get_logger(__name__)


class GitHubServiceError(Exception):
    """Fallo recuperable durante la sincronizacion."""


class GitHubService:
    def __init__(self, session: AsyncSession):
        self.repo = GitHubRepository(session)

    async def sync_repos(self) -> dict:
        started = time.perf_counter()
        config = await self.repo.get_config()

        if not settings.github_token:
            logger.warning(
                "GITHUB_TOKEN no configurado: el limite de la API baja a 60 req/h, "
                "lo que puede hacer fallar el sync de READMEs."
            )

        fetcher = GitHubFetcher(token=settings.github_token)
        try:
            new_repos: list[GitHubRepo] = await fetcher.sync_pipeline(config)
        except Exception as exc:  # noqa: BLE001 - queremos un 502, no un 500 crudo
            logger.exception("Fallo la sincronizacion de GitHub: %s", exc)
            raise GitHubServiceError(f"Error sincronizando con la API de GitHub: {exc}") from exc

        if new_repos:
            await self.repo.save_repos(new_repos)

        config.last_search_at = datetime.now(timezone.utc)
        await self.repo.update_config(config)

        duration = round(time.perf_counter() - started, 2)
        logger.info("GitHub: %d repos sincronizados en %ss", len(new_repos), duration)
        return {
            "status": "success",
            "source": "github",
            "items_synced": len(new_repos),
            "duration_seconds": duration,
        }

    async def get_repos(
        self,
        limit: int = 20,
        offset: int = 0,
        language: str | None = None,
        topic: str | None = None,
        min_stars: int | None = None,
    ) -> list[GitHubRepo]:
        return await self.repo.get_repos(limit, offset, language, topic, min_stars)

    async def get_repo(self, repo_id: int) -> GitHubRepo | None:
        return await self.repo.get_repo_by_id(repo_id)

    async def get_config(self):
        return await self.repo.get_config()

    async def update_config(self, config):
        return await self.repo.update_config(config)