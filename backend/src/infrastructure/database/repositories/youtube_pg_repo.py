from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
from datetime import datetime, timezone

from src.infrastructure.database.models import YouTubeVideoModel, YouTubeConfigModel
from src.core.entities.youtube import YouTubeVideo
from src.core.entities.config import YouTubeConfig


class YouTubeRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_videos(self, videos: list[YouTubeVideo]) -> None:
        if not videos:
            return

        # Preparamos los diccionarios para el bulk insert
        values = [
            {
                "id": v.id,
                "title": v.title,
                "channel": v.channel,
                "channel_id": v.channel_id,
                "published_at": v.published_at,
                "url": v.url,
                "thumbnail_url": v.thumbnail_url,
                "transcript": v.transcript,
                "views": v.views,
                "likes": v.likes,
                "comments": v.comments,
                "duration_seconds": v.duration_seconds,
                "language": v.language,
                "synced_at": v.synced_at
            }
            for v in videos
        ]

        stmt = insert(YouTubeVideoModel).values(values)
        
        # Upsert: Si el ID ya existe, actualiza las estadísticas
        stmt = stmt.on_conflict_do_update(
            index_elements=['id'],
            set_={
                'views': stmt.excluded.views,
                'likes': stmt.excluded.likes,
                'comments': stmt.excluded.comments,
                'synced_at': stmt.excluded.synced_at
            }
        )
        
        await self.session.execute(stmt)
        await self.session.commit()

    async def get_videos(self, limit: int = 20, offset: int = 0) -> list[YouTubeVideoModel]:
        stmt = select(YouTubeVideoModel).order_by(YouTubeVideoModel.published_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_config(self) -> YouTubeConfig:
        stmt = select(YouTubeConfigModel).where(YouTubeConfigModel.id == 1)
        result = await self.session.execute(stmt)
        config_model = result.scalar_one_or_none()
        
        if not config_model:
            # Si no existe, creamos una por defecto
            config_model = YouTubeConfigModel(id=1)
            self.session.add(config_model)
            await self.session.commit()
            
        return YouTubeConfig(
            keywords=config_model.keywords,
            channel_ids=config_model.channel_ids,
            languages=config_model.languages,
            max_results=config_model.max_results,
            last_search_at=config_model.last_search_at
        )

    async def update_config(self, config: YouTubeConfig) -> None:
        stmt = select(YouTubeConfigModel).where(YouTubeConfigModel.id == 1)
        result = await self.session.execute(stmt)
        config_model = result.scalar_one()
        
        config_model.keywords = config.keywords
        config_model.channel_ids = config.channel_ids
        config_model.languages = config.languages
        config_model.max_results = config.max_results
        config_model.last_search_at = config.last_search_at
        config_model.updated_at = datetime.now(timezone.utc)
        
        await self.session.commit()