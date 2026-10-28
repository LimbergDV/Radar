"""Contrato de persistencia para papers de Hugging Face.

Vive en `core` porque el servicio depende de esta abstracción, no de
SQLAlchemy. La implementación concreta está en
`infrastructure/database/repositories/paper_pg_repo.py`.
"""

from abc import ABC, abstractmethod
from datetime import datetime

from src.core.entities.config import PaperConfig
from src.core.entities.paper import HuggingFacePaper


class PaperRepository(ABC):
    """Persistencia de papers y de la configuración singleton del sync."""

    @abstractmethod
    async def save_papers(self, papers: list[HuggingFacePaper]) -> int:
        """Guarda/actualiza papers (upsert). Devuelve cuántos se procesaron."""

    @abstractmethod
    async def get_papers(
        self,
        limit: int = 20,
        offset: int = 0,
        query: str | None = None,
        since: datetime | None = None,
        order: str = "recent",
    ) -> list[HuggingFacePaper]:
        """Lista papers paginados, por fecha o por votos."""

    @abstractmethod
    async def get_paper_by_id(self, paper_id: str) -> HuggingFacePaper | None:
        """Detalle de un paper (incluye abstract y AI summary)."""

    @abstractmethod
    async def count_papers(self, since: datetime | None = None) -> int:
        """Total de papers almacenados (para /api/feed/stats)."""

    @abstractmethod
    async def latest_paper_date(self) -> datetime | None:
        """Fecha efectiva del paper más reciente."""

    @abstractmethod
    async def get_config(self) -> PaperConfig:
        """Config singleton; la crea con defaults si no existe."""

    @abstractmethod
    async def update_config(self, config: PaperConfig) -> PaperConfig:
        """Persiste la configuración y devuelve la versión ya guardada."""
