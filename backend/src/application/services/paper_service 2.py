"""Servicio de aplicación para papers de Hugging Face."""

import time
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.entities.paper import HuggingFacePaper
from src.core.logging_config import get_logger
from src.infrastructure.database.repositories.paper_pg_repo import PaperRepository
from src.infrastructure.external.huggingface_papers_api import HuggingFacePapersFetcher

logger = get_logger(__name__)


class PaperServiceError(Exception):
    """Fallo recuperable durante la sincronización de papers."""


class PaperService:
    def __init__(self, session: AsyncSession):
        self.repo = PaperRepository(session)

    async def sync_papers(self) -> dict:
        started = time.perf_counter()
        config = await self.repo.get_config()

        try:
            new_papers: list[HuggingFacePaper] = await HuggingFacePapersFetcher().sync_pipeline(
                config
            )
        except Exception as exc:  # noqa: BLE001 - queremos un 502, no un 500 crudo
            logger.exception("Falló la sincronización de papers: %s", exc)
            raise PaperServiceError(
                f"Error sincronizando papers con Hugging Face: {exc}"
            ) from exc

        if new_papers:
            await self.repo.save_papers(new_papers)

        config.last_search_at = datetime.now(timezone.utc)
        await self.repo.update_config(config)

        duration = round(time.perf_counter() - started, 2)
        daily = sum(1 for p in new_papers if p.source == "daily")
        logger.info(
            "Papers: %d sincronizados (%d del daily) en %ss",
            len(new_papers),
            daily,
            duration,
        )

        return {
            "status": "success",
            "source": "papers",
            "items_synced": len(new_papers),
            "duration_seconds": duration,
            "message": None,
        }

    async def get_papers(
        self,
        limit: int = 20,
        offset: int = 0,
        query: str | None = None,
        since: datetime | None = None,
        order: str = "recent",
    ) -> list[HuggingFacePaper]:
        return await self.repo.get_papers(limit, offset, query, since, order)

    async def get_paper(self, paper_id: str) -> HuggingFacePaper | None:
        return await self.repo.get_paper_by_id(paper_id)

    async def get_config(self):
        return await self.repo.get_config()

    async def update_config(self, config):
        return await self.repo.update_config(config)
