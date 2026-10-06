"""Schemas de la API para videos de YouTube.

Hasta ahora los routers devolvian los modelos ORM directamente: FastAPI los
serializaba "como saliera" y el schema OpenAPI no describia nada util. Con estos
DTOs el contrato es explicito y el frontend puede tipar contra el.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class YouTubeVideoSummary(BaseModel):
    """Version ligera para las cards del feed (sin transcripcion)."""

    id: str
    title: str
    channel: str
    channel_id: str
    published_at: datetime
    url: str
    thumbnail_url: str
    views: int
    likes: int
    comments: int
    duration_seconds: int
    language: str
    synced_at: datetime


class YouTubeVideoDetail(YouTubeVideoSummary):
    """Detalle con la transcripcion completa."""

    transcript: str = ""


class YouTubeConfigResponse(BaseModel):
    keywords: list[str]
    channel_ids: list[str]
    languages: list[str]
    max_results: int
    last_search_at: datetime | None = None


class YouTubeConfigUpdate(BaseModel):
    keywords: list[str] = Field(default_factory=list, max_length=30)
    channel_ids: list[str] = Field(default_factory=list, max_length=50)
    languages: list[str] = Field(default_factory=lambda: ["es", "en"], max_length=10)
    max_results: int = Field(default=5, ge=1, le=100)


class SyncResponse(BaseModel):
    status: str
    source: str
    items_synced: int
    duration_seconds: float | None = None
    message: str | None = None