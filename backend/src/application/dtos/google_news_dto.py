"""Schemas de la API para articulos de Google News."""

from datetime import datetime

from pydantic import BaseModel, Field


class GoogleNewsArticleSummary(BaseModel):
    """Version ligera para las cards del feed (sin el cuerpo del articulo)."""

    id: str
    title: str
    link: str
    pub_date: datetime
    source_name: str
    source_url: str
    image_url: str | None = None
    language: str


class GoogleNewsArticleDetail(GoogleNewsArticleSummary):
    """Detalle con el contenido extraido del medio (puede venir null)."""

    content: str | None = None
    content_fetched: bool = False
    fetched_at: datetime


class GoogleNewsConfigResponse(BaseModel):
    q: str
    hl: str
    gl: str
    ceid: str
    when: str
    site: str
    intitle: str
    max_results: int
    days_window: int
    last_search_at: datetime | None = None


class GoogleNewsConfigUpdate(BaseModel):
    q: str = Field(default="Inteligencia Artificial OR IA", max_length=500)
    hl: str = Field(default="es-419", max_length=20)
    gl: str = Field(default="MX", max_length=10)
    ceid: str = Field(default="MX:es-419", max_length=120)
    when: str = Field(default="1d", max_length=10)
    site: str = Field(default="", max_length=255)
    intitle: str = Field(default="", max_length=255)
    max_results: int = Field(default=50, ge=1, le=100)
    days_window: int = Field(default=1, ge=0, le=365)