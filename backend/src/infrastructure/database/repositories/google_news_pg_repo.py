"""Implementacion PostgreSQL del repositorio de Google News."""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.entities.config import GoogleNewsConfig
from src.core.entities.google_news import GoogleNewsArticle
from src.core.repositories.google_news_repository import (
    GoogleNewsRepository as GoogleNewsRepositoryBase,
)
from src.core.use_cases.update_source_config import validate_google_news_config
from src.infrastructure.database.models import (
    GoogleNewsArticleModel,
    GoogleNewsConfigModel,
)

CONFIG_ID = 1


def _to_entity(model: GoogleNewsArticleModel) -> GoogleNewsArticle:
    return GoogleNewsArticle(
        id=model.id,
        title=model.title,
        link=model.link,
        pub_date=model.pub_date,
        source_name=model.source_name,
        source_url=model.source_url,
        language=model.language,
        fetched_at=model.fetched_at,
        image_url=model.image_url,
        content=model.content,
        original_link=model.original_link or "",
        content_fetched=bool(model.content_fetched),
    )


class GoogleNewsRepository(GoogleNewsRepositoryBase):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_articles(self, articles: list[GoogleNewsArticle]) -> int:
        if not articles:
            return 0

        values = [
            {
                "id": a.id,
                "title": a.title,
                "link": a.link,
                "pub_date": a.pub_date,
                "source_name": a.source_name,
                "source_url": a.source_url,
                "image_url": a.image_url,
                "content": a.content,
                "language": a.language,
                "fetched_at": a.fetched_at,
                "original_link": a.original_link,
                "content_fetched": a.content_fetched,
            }
            for a in articles
        ]

        stmt = insert(GoogleNewsArticleModel).values(values)
        # Solo se refresca el enriquecimiento si aun no hay contenido.
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "image_url": func.coalesce(stmt.excluded.image_url, GoogleNewsArticleModel.image_url),
                "content": func.coalesce(stmt.excluded.content, GoogleNewsArticleModel.content),
                "content_fetched": GoogleNewsArticleModel.content_fetched | stmt.excluded.content_fetched,
                "fetched_at": stmt.excluded.fetched_at,
            },
            where=GoogleNewsArticleModel.content_fetched.is_(False),
        )

        await self.session.execute(stmt)
        await self.session.commit()
        return len(articles)

    async def get_articles(
        self,
        limit: int = 20,
        offset: int = 0,
        language: str | None = None,
        source_name: str | None = None,
        since: datetime | None = None,
    ) -> list[GoogleNewsArticle]:
        stmt = select(GoogleNewsArticleModel).order_by(GoogleNewsArticleModel.pub_date.desc())

        if language:
            stmt = stmt.where(GoogleNewsArticleModel.language.ilike(f"{language}%"))
        if source_name:
            stmt = stmt.where(GoogleNewsArticleModel.source_name.ilike(f"%{source_name}%"))
        if since:
            stmt = stmt.where(GoogleNewsArticleModel.pub_date >= since)

        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return [_to_entity(m) for m in result.scalars().all()]

    async def get_article_by_id(self, article_id: str) -> GoogleNewsArticle | None:
        result = await self.session.execute(
            select(GoogleNewsArticleModel).where(GoogleNewsArticleModel.id == article_id)
        )
        model = result.scalar_one_or_none()
        return _to_entity(model) if model else None

    async def count_articles(
        self,
        language: str | None = None,
        since: datetime | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(GoogleNewsArticleModel)
        if language:
            stmt = stmt.where(GoogleNewsArticleModel.language.ilike(f"{language}%"))
        if since:
            stmt = stmt.where(GoogleNewsArticleModel.pub_date >= since)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def top_sources(self, limit: int = 5) -> list[tuple[str, int]]:
        stmt = (
            select(GoogleNewsArticleModel.source_name, func.count().label("total"))
            .where(GoogleNewsArticleModel.source_name != "")
            .group_by(GoogleNewsArticleModel.source_name)
            .order_by(func.count().desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def latest_article_date(self) -> datetime | None:
        result = await self.session.execute(select(func.max(GoogleNewsArticleModel.pub_date)))
        return result.scalar_one_or_none()

    async def _get_config_model(self) -> GoogleNewsConfigModel:
        result = await self.session.execute(
            select(GoogleNewsConfigModel).where(GoogleNewsConfigModel.id == CONFIG_ID)
        )
        model = result.scalar_one_or_none()

        if not model:
            model = GoogleNewsConfigModel(id=CONFIG_ID)
            self.session.add(model)
            await self.session.commit()
            await self.session.refresh(model)

        return model

    async def get_config(self) -> GoogleNewsConfig:
        model = await self._get_config_model()
        return GoogleNewsConfig(
            q=model.q,
            hl=model.hl,
            gl=model.gl,
            ceid=model.ceid,
            when=model.when,
            site=model.site,
            intitle=model.intitle,
            max_results=model.max_results,
            days_window=model.days_window,
            last_search_at=model.last_search_at,
        )

    async def update_config(self, config: GoogleNewsConfig) -> GoogleNewsConfig:
        config = validate_google_news_config(config)
        model = await self._get_config_model()

        model.q = config.q
        model.hl = config.hl
        model.gl = config.gl
        model.ceid = config.ceid
        model.when = config.when
        model.site = config.site
        model.intitle = config.intitle
        model.max_results = config.max_results
        model.days_window = config.days_window
        # No pisamos last_search_at: antes se hacia con now() y guardar la
        # configuracion parecia una sincronizacion (retrasaba el auto-sync).
        model.last_search_at = config.last_search_at
        model.updated_at = datetime.now(timezone.utc)

        await self.session.commit()
        await self.session.refresh(model)

        return GoogleNewsConfig(
            q=model.q,
            hl=model.hl,
            gl=model.gl,
            ceid=model.ceid,
            when=model.when,
            site=model.site,
            intitle=model.intitle,
            max_results=model.max_results,
            days_window=model.days_window,
            last_search_at=model.last_search_at,
        )