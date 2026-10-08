"""Modelos SQLAlchemy (capa de infraestructura).

Los longitudes de columna se eligieron a partir de medidas reales del RSS de
Google News: su `guid` opaco llega a ~800 caracteres, asi que `id` es un hash y
los links son `Text` (el link opaco + query string no entra en VARCHAR(512)).
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class YouTubeVideoModel(Base):
    __tablename__ = "youtube_videos"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(String(255))
    channel_id: Mapped[str] = mapped_column(String(255))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    url: Mapped[str] = mapped_column(String(512))
    thumbnail_url: Mapped[str] = mapped_column(String(512))
    transcript: Mapped[str] = mapped_column(Text, default="")
    views: Mapped[int] = mapped_column(Integer, default=0)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    language: Mapped[str] = mapped_column(String(10), default="")
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class YouTubeConfigModel(Base):
    __tablename__ = "youtube_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    keywords: Mapped[list] = mapped_column(JSONB, default=list)
    channel_ids: Mapped[list] = mapped_column(JSONB, default=list)
    languages: Mapped[list] = mapped_column(JSONB, default=lambda: ["es", "en"])
    max_results: Mapped[int] = mapped_column(Integer, default=5)
    days_back: Mapped[int] = mapped_column(Integer, default=2)
    last_search_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)


class GoogleNewsArticleModel(Base):
    __tablename__ = "google_news_articles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    link: Mapped[str] = mapped_column(Text)
    pub_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_name: Mapped[str] = mapped_column(String(255), default="")
    source_url: Mapped[str] = mapped_column(Text, default="")
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="es")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    original_link: Mapped[str] = mapped_column(Text, default="")
    content_fetched: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        Index("ix_google_news_articles_pub_date", "pub_date"),
        Index("ix_google_news_articles_language", "language"),
        Index("ix_google_news_articles_fetched_at", "fetched_at"),
    )


class GoogleNewsConfigModel(Base):
    __tablename__ = "google_news_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    q: Mapped[str] = mapped_column(Text, default="Inteligencia Artificial OR IA")
    hl: Mapped[str] = mapped_column(String(20), default="es-419")
    gl: Mapped[str] = mapped_column(String(10), default="MX")
    ceid: Mapped[str] = mapped_column(String(120), default="MX:es-419")
    when: Mapped[str] = mapped_column(String(10), default="1d")
    site: Mapped[str] = mapped_column(String(255), default="")
    intitle: Mapped[str] = mapped_column(String(255), default="")
    max_results: Mapped[int] = mapped_column(Integer, default=50)
    days_window: Mapped[int] = mapped_column(Integer, default=1)
    last_search_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)



class GitHubRepoModel(Base):
    __tablename__ = "github_repos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(512))
    html_url: Mapped[str] = mapped_column(String(512))
    description: Mapped[str] = mapped_column(Text, default="")
    stargazers_count: Mapped[int] = mapped_column(Integer, default=0)
    forks_count: Mapped[int] = mapped_column(Integer, default=0)
    open_issues_count: Mapped[int] = mapped_column(Integer, default=0)
    language: Mapped[str] = mapped_column(String(100), default="")
    license: Mapped[str | None] = mapped_column(String(100), nullable=True)
    topics: Mapped[list] = mapped_column(JSONB, default=list)
    readme: Mapped[str] = mapped_column(Text, default="")
    owner_avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    watchers_count: Mapped[int] = mapped_column(Integer, default=0)
    homepage: Mapped[str | None] = mapped_column(String(512), nullable=True)
    size_kb: Mapped[int] = mapped_column(Integer, default=0)
    default_branch: Mapped[str] = mapped_column(String(255), default="main")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    __table_args__ = (
        Index("ix_github_repos_updated_at", "updated_at"),
        Index("ix_github_repos_stargazers", "stargazers_count"),
        Index("ix_github_repos_synced_at", "synced_at"),
    )


class GitHubConfigModel(Base):
    __tablename__ = "github_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    keywords: Mapped[list] = mapped_column(JSONB, default=lambda: ["openai", "claude", "langchain"])
    days_active: Mapped[int] = mapped_column(Integer, default=2)
    min_stars: Mapped[int] = mapped_column(Integer, default=50)
    min_forks: Mapped[int] = mapped_column(Integer, default=10)
    require_license: Mapped[bool] = mapped_column(Boolean, default=False)
    selected_topics: Mapped[list] = mapped_column(JSONB, default=lambda: ["ai", "llm"])
    selected_languages: Mapped[list] = mapped_column(JSONB, default=lambda: ["python", "typescript"])
    max_results: Mapped[int] = mapped_column(Integer, default=50)
    last_search_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)