"""Contrato de persistencia para videos de YouTube.

Vive en `core` porque la logica de negocio depende de esta abstraccion, no de
SQLAlchemy. La implementacion concreta esta en
`infrastructure/database/repositories/youtube_pg_repo.py`.
"""

from abc import ABC, abstractmethod
from datetime import datetime

from src.core.entities.config import YouTubeConfig
from src.core.entities.youtube import YouTubeVideo


class YouTubeRepository(ABC):
    """Persistencia de videos y de la configuracion singleton de busqueda."""

    @abstractmethod
    async def save_videos(self, videos: list[YouTubeVideo]) -> int:
        """Guarda/actualiza videos (upsert). Devuelve cuantos se procesaron."""

    @abstractmethod
    async def get_videos(
        self,
        limit: int = 20,
        offset: int = 0,
        language: str | None = None,
    ) -> list[YouTubeVideo]:
        """Lista videos del mas nuevo al mas antiguo, con paginacion."""

    @abstractmethod
    async def get_video_by_id(self, video_id: str) -> YouTubeVideo | None:
        """Detalle de un video (incluye transcripcion)."""

    @abstractmethod
    async def count_videos(self, language: str | None = None) -> int:
        """Total de videos almacenados (para /api/feed/stats)."""

    @abstractmethod
    async def latest_video_date(self) -> datetime | None:
        """Fecha de publicacion del video mas reciente almacenado."""

    @abstractmethod
    async def get_config(self) -> YouTubeConfig:
        """Config singleton; la crea con defaults si no existe."""

    @abstractmethod
    async def update_config(self, config: YouTubeConfig) -> YouTubeConfig:
        """Persiste la configuracion y devuelve la version ya guardada."""