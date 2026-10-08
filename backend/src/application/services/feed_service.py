"""Servicio del feed unificado: junta las tres fuentes en un solo formato.

El frontend (Fase 3) consume esto para pintar un feed homogeneo con tabs, en
lugar de hitear tres endpoints distintos y normalizar en el cliente.
"""

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.application.dtos.feed_dto import (
    FeedItem,
    FeedResponse,
    FeedStats,
    SourceStats,
)
from src.core.logging_config import get_logger
from src.infrastructure.database.repositories.github_pg_repo import GitHubRepository
from src.infrastructure.database.repositories.google_news_pg_repo import GoogleNewsRepository
from src.infrastructure.database.repositories.youtube_pg_repo import YouTubeRepository

logger = get_logger(__name__)

VALID_SOURCES = ("youtube", "news", "github")


class FeedService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_feed(
        self,
        limit: int = 20,
        offset: int = 0,
        source: str | None = None,
        language: str | None = None,
        query: str | None = None,
    ) -> FeedResponse:
        """Feed combinado, ordenado por fecha de publicacion descendente."""
        if source and source not in VALID_SOURCES:
            raise ValueError(f"Fuente no valida: {source}. Usa una de {', '.join(VALID_SOURCES)}.")

        selected = [source] if source else list(VALID_SOURCES)
        items: list[FeedItem] = []

        # Pedimos limit+offset por fuente: si no, la pagina combined se corta.
        per_source = limit + offset if not source else limit

        if "youtube" in selected:
            items.extend(await self._youtube_items(per_source, language, query))
        if "news" in selected:
            items.extend(await self._news_items(per_source, language, query))
        if "github" in selected:
            items.extend(await self._github_items(per_source, query))

        items.sort(key=lambda i: i.published_at, reverse=True)

        has_more = len(items) > offset + limit
        page = items[offset:offset + limit]

        return FeedResponse(
            total=len(items),
            limit=limit,
            offset=offset,
            has_more=has_more,
            items=page,
        )

    async def _youtube_items(self, limit, language, query) -> list[FeedItem]:
        repo = YouTubeRepository(self.session)
        videos = await repo.get_videos(limit=limit, language=language)
        return [
            FeedItem(
                source="youtube",
                source_id=video.id,
                title=video.title,
                url=video.url,
                published_at=video.published_at,
                description=video.transcript[:280] if video.transcript else "",
                image_url=video.thumbnail_url or None,
                author=video.channel,
                language=video.language,
                stats={
                    "views": video.views,
                    "likes": video.likes,
                    "comments": video.comments,
                    "duration_seconds": video.duration_seconds,
                },
                extra={"channel_id": video.channel_id, "has_transcript": bool(video.transcript)},
            )
            for video in videos
            if _matches_query(video.title, query)
        ]

    async def _news_items(self, limit, language, query) -> list[FeedItem]:
        repo = GoogleNewsRepository(self.session)
        articles = await repo.get_articles(limit=limit, language=language)
        return [
            FeedItem(
                source="news",
                source_id=article.id,
                title=article.title,
                url=article.link,
                published_at=article.pub_date,
                description=(article.content or "")[:280],
                image_url=article.image_url,
                author=article.source_name,
                language=article.language,
                stats={"has_content": bool(article.content)},
                extra={
                    "source_url": article.source_url,
                    "content_fetched": article.content_fetched,
                },
            )
            for article in articles
            if _matches_query(article.title, query)
        ]

    async def _github_items(self, limit, query) -> list[FeedItem]:
        repo = GitHubRepository(self.session)
        repos = await repo.get_repos(limit=limit)
        return [
            FeedItem(
                source="github",
                source_id=str(repo.id),
                title=repo.full_name,
                url=repo.html_url,
                published_at=repo.updated_at,
                description=repo.description,
                image_url=repo.owner_avatar_url,
                author=repo.full_name.split("/")[0] if "/" in repo.full_name else None,
                language=repo.language,
                stats={
                    "stars": repo.stargazers_count,
                    "forks": repo.forks_count,
                    "issues": repo.open_issues_count,
                },
                extra={
                    "topics": repo.topics,
                    "license": repo.license,
                    "has_readme": bool(repo.readme),
                },
            )
            for repo in repos
            if _matches_query(f"{repo.full_name} {repo.description}", query)
        ]

    async def get_stats(self) -> FeedStats:
        """Totales, ultima sync y rankings para el dashboard."""
        yt_repo = YouTubeRepository(self.session)
        news_repo = GoogleNewsRepository(self.session)
        gh_repo = GitHubRepository(self.session)

        yt_config = await yt_repo.get_config()
        news_config = await news_repo.get_config()
        gh_config = await gh_repo.get_config()

        youtube = SourceStats(
            total=await yt_repo.count_videos(),
            last_sync_at=yt_config.last_search_at,
            latest_item_at=await yt_repo.latest_video_date(),
        )
        news = SourceStats(
            total=await news_repo.count_articles(),
            last_sync_at=news_config.last_search_at,
            latest_item_at=await news_repo.latest_article_date(),
        )
        github = SourceStats(
            total=await gh_repo.count_repos(),
            last_sync_at=gh_config.last_search_at,
            latest_item_at=await gh_repo.latest_repo_date(),
        )

        return FeedStats(
            total_items=youtube.total + news.total + github.total,
            youtube=youtube,
            news=news,
            github=github,
            top_news_sources=[
                {"name": name, "count": count}
                for name, count in await news_repo.top_sources(5)
            ],
            top_github_languages=[
                {"language": language, "count": count}
                for language, count in await gh_repo.top_languages(5)
            ],
            generated_at=datetime.now(timezone.utc),
        )


def _matches_query(text: str, query: str | None) -> bool:
    if not query:
        return True
    return query.strip().lower() in (text or "").lower()