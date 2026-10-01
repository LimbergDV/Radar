from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.external.youtube_api import YouTubeFetcher
from src.infrastructure.database.repositories.youtube_pg_repo import YouTubeRepository
from src.infrastructure.database.settings import settings


class YouTubeService:
    @staticmethod
    async def sync_videos(session: AsyncSession) -> dict:
        repo = YouTubeRepository(session)
        config = await repo.get_config()
        
        fetcher = YouTubeFetcher(api_key=settings.youtube_api_key)
        
        print("Iniciando sincronización de YouTube...")
        new_videos = await fetcher.sync_pipeline(config)
        
        if new_videos:
            await repo.save_videos(new_videos)
            
        # Actualizamos la fecha de última sincronización
        config.last_search_at = datetime.now(timezone.utc)
        await repo.update_config(config)
        
        return {"status": "success", "videos_synced": len(new_videos)}

    @staticmethod
    async def get_feed(session: AsyncSession, limit: int = 20, offset: int = 0) -> list:
        repo = YouTubeRepository(session)
        return await repo.get_videos(limit, offset)