from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.external.google_news_api import GoogleNewsFetcher
from src.infrastructure.database.repositories.google_news_pg_repo import GoogleNewsRepository

class GoogleNewsService:
    @staticmethod
    async def sync_articles(session: AsyncSession) -> dict:
        repo = GoogleNewsRepository(session)
        config = await repo.get_config()
        
        fetcher = GoogleNewsFetcher()
        print("Iniciando sincronización de Google News...")
        new_articles = await fetcher.sync_pipeline(config)
        
        if new_articles:
            await repo.save_articles(new_articles)
            
        config.last_search_at = datetime.now(timezone.utc)
        await repo.update_config(config)
        
        return {"status": "success", "articles_synced": len(new_articles)}

    @staticmethod
    async def get_feed(session: AsyncSession, limit: int = 20, offset: int = 0) -> list:
        repo = GoogleNewsRepository(session)
        return await repo.get_articles(limit, offset)