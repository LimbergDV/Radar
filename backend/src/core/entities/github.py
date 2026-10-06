from dataclasses import dataclass
from datetime import datetime


@dataclass
class GitHubRepo:
    """Repositorio de GitHub trending, enriquecido con su README."""

    id: int
    name: str
    full_name: str
    html_url: str
    description: str
    stargazers_count: int
    forks_count: int
    open_issues_count: int
    language: str
    topics: list[str]
    readme: str
    updated_at: datetime
    synced_at: datetime
    owner_avatar_url: str | None = None
    license: str | None = None
    watchers_count: int = 0
    homepage: str | None = None
    size_kb: int = 0
    default_branch: str = "main"