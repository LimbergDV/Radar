"""Schemas de la API para repositorios de GitHub."""

from datetime import datetime

from pydantic import BaseModel, Field


class GitHubRepoSummary(BaseModel):
    """Version ligera para las cards del feed (sin README)."""

    id: int
    name: str
    full_name: str
    html_url: str
    description: str
    stargazers_count: int
    forks_count: int
    open_issues_count: int
    watchers_count: int = 0
    language: str
    license: str | None = None
    topics: list[str]
    owner_avatar_url: str | None = None
    homepage: str | None = None
    updated_at: datetime
    synced_at: datetime


class GitHubRepoDetail(GitHubRepoSummary):
    """Detalle con el README completo."""

    readme: str = ""
    size_kb: int = 0
    default_branch: str = "main"


class GitHubConfigResponse(BaseModel):
    keywords: list[str]
    days_active: int
    min_stars: int
    min_forks: int
    require_license: bool
    selected_topics: list[str]
    selected_languages: list[str]
    max_results: int
    last_search_at: datetime | None = None


class GitHubConfigUpdate(BaseModel):
    keywords: list[str] = Field(default_factory=list, max_length=30)
    days_active: int = Field(default=2, ge=1, le=365)
    min_stars: int = Field(default=50, ge=0, le=1_000_000)
    min_forks: int = Field(default=10, ge=0, le=1_000_000)
    require_license: bool = False
    selected_topics: list[str] = Field(default_factory=list, max_length=30)
    selected_languages: list[str] = Field(default_factory=list, max_length=30)
    max_results: int = Field(default=50, ge=1, le=100)