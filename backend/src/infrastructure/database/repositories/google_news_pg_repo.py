from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
from datetime import datetime, timezone

from src.infrastructure.database.models import GoogleNewsArticleModel, GoogleNewsConfigModel
from src.core.entities.google_news import GoogleNewsArticle
from src.core.entities.config import GoogleNewsConfig

class GoogleNewsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_articles(self, articles: list[GoogleNewsArticle]) -> None:
        if not articles: return

        values = [
            {
                "id": a.id, "title": a.title, "link": a.link,
                "pub_date": a.pub_date, "source_name": a.source_name,
                "source_url": a.source_url, "image_url": a.image_url,
                "content": a.content, "language": a.language,
                "fetched_at": a.fetched_at
            }
            for a in articles
        ]

        stmt = insert(GoogleNewsArticleModel).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=['id'],
            set_={
                'title': stmt.excluded.title,
                'image_url': stmt.excluded.image_url,
                'content': stmt.excluded.content,
                'fetched_at': stmt.excluded.fetched_at
            }
        )
        
        await self.session.execute(stmt)
        await self.session.commit()

    async def get_articles(self, limit: int = 20, offset: int = 0) -> list[GoogleNewsArticleModel]:
        stmt = select(GoogleNewsArticleModel).order_by(GoogleNewsArticleModel.pub_date.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_config(self) -> GoogleNewsConfig:
        stmt = select(GoogleNewsConfigModel).where(GoogleNewsConfigModel.id == 1)
        result = await self.session.execute(stmt)
        config_model = result.scalar_one_or_none()
        
        if not config_model:
            config_model = GoogleNewsConfigModel(id=1)
            self.session.add(config_model)
            await self.session.commit()
            
        return GoogleNewsConfig(
            q=config_model.q, hl=config_model.hl, gl=config_model.gl,
            ceid=config_model.ceid, when=config_model.when,
            site=config_model.site, intitle=config_model.intitle,
            max_results=config_model.max_results, last_search_at=config_model.last_search_at
        )

    async def update_config(self, config: GoogleNewsConfig) -> None:
        stmt = select(GoogleNewsConfigModel).where(GoogleNewsConfigModel.id == 1)
        result = await self.session.execute(stmt)
        config_model = result.scalar_one()
        
        config_model.q = config.q
        config_model.hl = config.hl
        config_model.gl = config.gl
        config_model.ceid = config.ceid
        config_model.when = config.when
        config_model.site = config.site
        config_model.intitle = config.intitle
        config_model.max_results = config.max_results
        config_model.last_search_at = datetime.now(timezone.utc)
        
        await self.session.commit()