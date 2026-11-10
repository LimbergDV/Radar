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
    async def get_transcripts(self, video_ids: list[str]) -> dict[str, str]:
        """Transcripciones ya guardadas (`id -> texto`) para no volver a pedirlas.

        Sin esto cada sync vuelve a llamar a YouTube/RapidAPI para los mismos
        videos y agota la cuota de transcripciones en pocas pasadas.
        """

    @abstractmethod
    async def delete_videos_not_in(self, video_ids: list[str]) -> int:
        """Borra los videos que la busqueda actual ya no devuelve.

        El feed de YouTube representa lo que piden las keywords activas, no un
        historico: al cambiarlas, el contenido viejo tiene que desaparecer.
        Devuelve cuantos se borraron.
        """

    @abstractmethod
    async def delete_all_videos(self) -> int:
        """Vacia el feed de YouTube (se usa al cambiar los criterios de busqueda)."""

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
    async def list_videos_missing_transcript(self, limit: int = 20) -> list[YouTubeVideo]:
        """Videos sin transcripción real, del más nuevo al más antiguo.

        El orden importa: la cuota de RapidAPI es escasa, así que se rellena
        primero lo que el usuario ve en el feed.
        """

    @abstractmethod
    async def count_missing_transcripts(self) -> int:
        """Cuántos videos siguen sin transcripción."""

    @abstractmethod
    async def update_transcript(self, video_id: str, transcript: str) -> bool:
        """Guarda la transcripción de un video. True si el video existía."""

    @abstractmethod
    async def latest_video_date(self) -> datetime | None:
        """Fecha de publicacion del video mas reciente almacenado."""

    @abstractmethod
    async def get_config(self) -> YouTubeConfig:
        """Config singleton; la crea con defaults si no existe."""

    @abstractmethod
    async def update_config(self, config: YouTubeConfig) -> YouTubeConfig:
        """Persiste la configuracion y devuelve la version ya guardada."""