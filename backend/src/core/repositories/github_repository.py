"""Contrato de persistencia para repositorios de GitHub."""

from abc import ABC, abstractmethod
from datetime import datetime

from src.core.entities.config import GitHubConfig
from src.core.entities.github import GitHubRepo


class GitHubRepository(ABC):
    """Persistencia de repos y de la configuracion singleton de busqueda."""

    @abstractmethod
    async def save_repos(self, repos: list[GitHubRepo]) -> int:
        """Guarda/actualiza repos (upsert). Devuelve cuantos se procesaron."""

    @abstractmethod
    async def get_repos(
        self,
        limit: int = 20,
        offset: int = 0,
        language: str | None = None,
        topic: str | None = None,
        min_stars: int | None = None,
    ) -> list[GitHubRepo]:
        """Lista repos ordenados por popularidad, con paginacion y filtros."""

    @abstractmethod
    async def get_repo_by_id(self, repo_id: int) -> GitHubRepo | None:
        """Detalle de un repo (incluye README completo)."""

    @abstractmethod
    async def count_repos(
        self,
        language: str | None = None,
        since: datetime | None = None,
    ) -> int:
        """Total de repos almacenados (para /api/feed/stats)."""

    @abstractmethod
    async def top_languages(self, limit: int = 5) -> list[tuple[str, int]]:
        """Lenguajes mas frecuentes como (lenguaje, total). Alimenta el dashboard."""

    @abstractmethod
    async def latest_repo_date(self) -> datetime | None:
        """Fecha de actualizacion del repo mas reciente almacenado."""

    @abstractmethod
    async def get_config(self) -> GitHubConfig:
        """Config singleton; la crea con defaults si no existe."""

    @abstractmethod
    async def update_config(self, config: GitHubConfig) -> GitHubConfig:
        """Persiste la configuracion y devuelve la version ya guardada."""