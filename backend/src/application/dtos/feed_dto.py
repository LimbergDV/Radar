"""Schemas del feed unificado y de las estadisticas del dashboard."""

from datetime import datetime

from pydantic import BaseModel


class FeedItem(BaseModel):
    """Item normalizado de cualquier fuente, para pintar un feed homogeneo."""

    source: str  # 'youtube' | 'news' | 'github'
    source_id: str
    title: str
    url: str
    published_at: datetime
    description: str = ""
    image_url: str | None = None
    # Campos especificos por fuente (opcionales para no ensuciar la vista comun)
    author: str | None = None
    language: str | None = None
    stats: dict = {}
    extra: dict = {}


class FeedResponse(BaseModel):
    total: int
    limit: int
    offset: int
    has_more: bool
    items: list[FeedItem]


class SourceStats(BaseModel):
    """Totales y ultima sync de una fuente."""

    total: int
    last_sync_at: datetime | None = None
    latest_item_at: datetime | None = None


class FeedStats(BaseModel):
    """Payload de /api/feed/stats para el dashboard."""

    total_items: int
    youtube: SourceStats
    news: SourceStats
    github: SourceStats
    top_news_sources: list[dict] = []
    top_github_languages: list[dict] = []
    generated_at: datetime