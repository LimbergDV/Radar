"""Schemas de la API para papers de Hugging Face."""

from datetime import datetime

from pydantic import BaseModel, Field


class PaperSummary(BaseModel):
    """Versión ligera para cards y feed (sin el abstract completo)."""

    id: str
    title: str
    published_at: datetime
    submitted_on_daily_at: datetime | None = None
    upvotes: int = 0
    comments: int = 0
    thumbnail_url: str | None = None
    organization: str | None = None
    authors: list[str] = []
    ai_keywords: list[str] = []
    ai_summary: str = ""
    github_repo: str | None = None
    project_page: str | None = None
    arxiv_url: str
    pdf_url: str
    hf_url: str
    source: str = "daily"


class PaperDetail(PaperSummary):
    """Detalle con el abstract y los recursos enlazados en Hugging Face."""

    abstract: str = ""
    linked_models: list[str] = []
    linked_datasets: list[str] = []
    linked_spaces: list[str] = []
    synced_at: datetime


class PaperConfigResponse(BaseModel):
    keywords: list[str]
    max_results: int
    days_back: int
    include_daily: bool
    include_search: bool
    last_search_at: datetime | None = None


class PaperConfigUpdate(BaseModel):
    keywords: list[str] = Field(default=["agents", "reasoning", "llm"], max_length=10)
    max_results: int = Field(default=50, ge=1, le=100)
    days_back: int = Field(default=7, ge=1, le=365)
    include_daily: bool = True
    include_search: bool = True
