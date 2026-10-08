"""Servicio de aplicacion para YouTube: orquesta config -> pipeline -> repo."""

import time

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.entities.youtube import YouTubeVideo
from src.core.logging_config import get_logger
from src.core.use_cases.sync_youtube import YouTubeApiError
from src.core.use_cases.update_source_config import YouTubeConfigError
from src.infrastructure.database.repositories.youtube_pg_repo import YouTubeRepository
from src.infrastructure.database.settings import settings
from src.infrastructure.external.youtube_api import sync_pipeline

logger = get_logger(__name__)


class YouTubeServiceError(Exception):
    """Fallo recuperable durante la sincronizacion (se traduce a HTTP 502)."""


class YouTubeService:
    def __init__(self, session: AsyncSession):
        self.repo = YouTubeRepository(session)

    async def sync_videos(self) -> dict:
        """Sincroniza videos. Lanza YouTubeServiceError si falla la fuente externa."""
        started = time.perf_counter()
        config = await self.repo.get_config()

        if not settings.youtube_api_key:
            message = "YOUTUBE_API_KEY no esta configurada en el backend"
            logger.error(message)
            raise YouTubeServiceError(message)

        try:
            new_videos: list[YouTubeVideo] = await sync_pipeline(config, settings.youtube_api_key)
        except YouTubeConfigError as exc:
            # Config sin objetivos de busqueda. No es un fallo de la API de
            # YouTube sino de setup, y el usuario tiene que poder leerlo.
            logger.warning("Sincronizacion de YouTube cancelada: %s", exc)
            raise YouTubeServiceError(str(exc)) from exc
        except YouTubeApiError as exc:
            # Cuota/credenciales/red. Sin esto el sync devolveria 'exitoso' con 0
            # videos y pareceria que no hay contenido nuevo.
            logger.error("Fallo la API de YouTube: %s", exc)
            raise YouTubeServiceError(str(exc)) from exc
        except ValueError:
            raise
        except Exception as exc:  # noqa: BLE001 - queremos un 502, no un 500 crudo
            logger.exception("Fallo la sincronizacion de YouTube: %s", exc)
            raise YouTubeServiceError(f"Error sincronizando con la API de YouTube: {exc}") from exc

        if new_videos:
            await self.repo.save_videos(new_videos)

        # La fecha se actualiza solo si el pipeline llego al final: asi un fallo
        # no evita que se reintente en la proxima pasada del scheduler.
        config.last_search_at = _now()
        await self.repo.update_config(config)

        duration = round(time.perf_counter() - started, 2)
        logger.info("YouTube: %d videos sincronizados en %ss", len(new_videos), duration)
        return {
            "status": "success",
            "source": "youtube",
            "items_synced": len(new_videos),
            "duration_seconds": duration,
        }

    async def get_videos(
        self,
        limit: int = 20,
        offset: int = 0,
        language: str | None = None,
    ) -> list[YouTubeVideo]:
        return await self.repo.get_videos(limit, offset, language)

    async def get_video(self, video_id: str) -> YouTubeVideo | None:
        return await self.repo.get_video_by_id(video_id)

    async def get_config(self):
        return await self.repo.get_config()

    async def update_config(self, config):
        return await self.repo.update_config(config)


def _now():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)