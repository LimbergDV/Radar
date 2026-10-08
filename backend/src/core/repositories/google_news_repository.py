"""Contrato de persistencia para articulos de Google News."""

from abc import ABC, abstractmethod
from datetime import datetime

from src.core.entities.config import GoogleNewsConfig
from src.core.entities.google_news import GoogleNewsArticle


class GoogleNewsRepository(ABC):
    """Persistencia de articulos y de la configuracion singleton de la query RSS."""

    @abstractmethod
    async def save_articles(self, articles: list[GoogleNewsArticle]) -> int:
        """Guarda/actualiza articulos (upsert). Devuelve cuantos se procesaron."""

    @abstractmethod
    async def get_articles(
        self,
        limit: int = 20,
        offset: int = 0,
        language: str | None = None,
        source_name: str | None = None,
        since: datetime | None = None,
    ) -> list[GoogleNewsArticle]:
        """Lista articulos del mas nuevo al mas antiguo, con paginacion y filtros."""

    @abstractmethod
    async def get_article_by_id(self, article_id: str) -> GoogleNewsArticle | None:
        """Detalle de un articulo (incluye contenido extraido)."""

    @abstractmethod
    async def count_articles(
        self,
        language: str | None = None,
        since: datetime | None = None,
    ) -> int:
        """Total de articulos almacenados (para /api/feed/stats)."""

    @abstractmethod
    async def top_sources(self, limit: int = 5) -> list[tuple[str, int]]:
        """Fuentes mas activas como (nombre, total). Alimenta el dashboard."""

    @abstractmethod
    async def latest_article_date(self) -> datetime | None:
        """Fecha de publicacion del articulo mas reciente almacenado."""

    @abstractmethod
    async def get_config(self) -> GoogleNewsConfig:
        """Config singleton; la crea con defaults si no existe."""

    @abstractmethod
    async def update_config(self, config: GoogleNewsConfig) -> GoogleNewsConfig:
        """Persiste la configuracion y devuelve la version ya guardada."""