"""Servicio de aplicacion para Google News."""

import time
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.entities.google_news import GoogleNewsArticle
from src.core.logging_config import get_logger
from src.infrastructure.database.repositories.google_news_pg_repo import GoogleNewsRepository
from src.infrastructure.external.google_news_api import GoogleNewsFetcher

logger = get_logger(__name__)


class GoogleNewsServiceError(Exception):
    """Fallo recuperable durante la sincronizacion."""


class GoogleNewsService:
    def __init__(self, session: AsyncSession):
        self.repo = GoogleNewsRepository(session)

    async def sync_articles(self) -> dict:
        started = time.perf_counter()
        config = await self.repo.get_config()

        fetcher = GoogleNewsFetcher()
        try:
            new_articles: list[GoogleNewsArticle] = await fetcher.sync_pipeline(config)
        except Exception as exc:  # noqa: BLE001 - queremos un 502, no un 500 crudo
            logger.exception("Fallo la sincronizacion de Google News: %s", exc)
            raise GoogleNewsServiceError(f"Error sincronizando con Google News: {exc}") from exc

        if new_articles:
            await self.repo.save_articles(new_articles)

        config.last_search_at = datetime.now(timezone.utc)
        await self.repo.update_config(config)

        duration = round(time.perf_counter() - started, 2)
        with_content = sum(1 for a in new_articles if a.content_fetched)
        logger.info(
            "Google News: %d articulos sincronizados (%d con contenido) en %ss",
            len(new_articles),
            with_content,
            duration,
        )
        return {
            "status": "success",
            "source": "news",
            "items_synced": len(new_articles),
            "duration_seconds": duration,
            "message": (
                None if with_content == len(new_articles)
                else f"{len(new_articles) - with_content} articulos guardados sin cuerpo: "
                     "Google News ya no expone la URL real del medio"
            ),
        }

    async def get_articles(
        self,
        limit: int = 20,
        offset: int = 0,
        language: str | None = None,
        source_name: str | None = None,
        since: datetime | None = None,
    ) -> list[GoogleNewsArticle]:
        return await self.repo.get_articles(limit, offset, language, source_name, since)

    async def get_article(self, article_id: str) -> GoogleNewsArticle | None:
        return await self.repo.get_article_by_id(article_id)

    async def get_config(self):
        return await self.repo.get_config()

    async def update_config(self, config):
        return await self.repo.update_config(config)