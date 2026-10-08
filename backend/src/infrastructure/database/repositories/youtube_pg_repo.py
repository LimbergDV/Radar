"""Implementacion PostgreSQL del repositorio de YouTube."""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.entities.config import YouTubeConfig
from src.core.entities.youtube import YouTubeVideo
from src.core.repositories.youtube_repository import YouTubeRepository as YouTubeRepositoryBase
from src.core.use_cases.update_source_config import validate_youtube_config
from src.infrastructure.database.models import YouTubeConfigModel, YouTubeVideoModel

CONFIG_ID = 1

# Repetido (no importado) para no acoplar la capa de datos al cliente externo.
NO_TRANSCRIPT = "Transcripción no disponible"


def _to_config_entity(model: YouTubeConfigModel) -> YouTubeConfig:
    """Proyecta el modelo de configuracion a la entidad de dominio.

    `get_config` y `update_config` devuelven las dos la misma entidad; duplicar
    el mapeo hacia que se desincronicen al anadir un campo.
    """
    return YouTubeConfig(
        keywords=list(model.keywords or []),
        channel_ids=list(model.channel_ids or []),
        languages=list(model.languages or []),
        max_results=model.max_results,
        days_back=model.days_back,
        last_search_at=model.last_search_at,
    )


def _to_entity(model: YouTubeVideoModel) -> YouTubeVideo:
    return YouTubeVideo(
        id=model.id,
        title=model.title,
        channel=model.channel,
        channel_id=model.channel_id,
        published_at=model.published_at,
        url=model.url,
        thumbnail_url=model.thumbnail_url,
        transcript=model.transcript or "",
        views=model.views,
        likes=model.likes,
        comments=model.comments,
        duration_seconds=model.duration_seconds,
        language=model.language,
        synced_at=model.synced_at,
    )


class YouTubeRepository(YouTubeRepositoryBase):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_videos(self, videos: list[YouTubeVideo]) -> int:
        if not videos:
            return 0

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
                "synced_at": v.synced_at,
            }
            for v in videos
        ]

        stmt = insert(YouTubeVideoModel).values(values)
        # No pisamos una transcripcion real, pero el placeholder si se reintenta
        # (YouTube a veces habilita la transcripcion despues).
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "views": stmt.excluded.views,
                "likes": stmt.excluded.likes,
                "comments": stmt.excluded.comments,
                "transcript": stmt.excluded.transcript,
                "synced_at": stmt.excluded.synced_at,
            },
            where=YouTubeVideoModel.transcript.in_(["", NO_TRANSCRIPT]),
        )

        await self.session.execute(stmt)
        await self.session.commit()
        return len(videos)

    async def get_videos(
        self,
        limit: int = 20,
        offset: int = 0,
        language: str | None = None,
    ) -> list[YouTubeVideo]:
        stmt = select(YouTubeVideoModel).order_by(YouTubeVideoModel.published_at.desc())

        if language:
            # Coincidencia por prefijo: 'es' trae tambien 'es-419', 'es-MX'.
            stmt = stmt.where(YouTubeVideoModel.language.ilike(f"{language}%"))

        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return [_to_entity(m) for m in result.scalars().all()]

    async def get_video_by_id(self, video_id: str) -> YouTubeVideo | None:
        result = await self.session.execute(
            select(YouTubeVideoModel).where(YouTubeVideoModel.id == video_id)
        )
        model = result.scalar_one_or_none()
        return _to_entity(model) if model else None

    async def count_videos(self, language: str | None = None) -> int:
        stmt = select(func.count()).select_from(YouTubeVideoModel)
        if language:
            stmt = stmt.where(YouTubeVideoModel.language.ilike(f"{language}%"))
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def latest_video_date(self) -> datetime | None:
        result = await self.session.execute(select(func.max(YouTubeVideoModel.published_at)))
        return result.scalar_one_or_none()

    async def _get_config_model(self) -> YouTubeConfigModel:
        result = await self.session.execute(
            select(YouTubeConfigModel).where(YouTubeConfigModel.id == CONFIG_ID)
        )
        model = result.scalar_one_or_none()

        if not model:
            model = YouTubeConfigModel(id=CONFIG_ID)
            self.session.add(model)
            await self.session.commit()
            await self.session.refresh(model)

        return model

    async def get_config(self) -> YouTubeConfig:
        return _to_config_entity(await self._get_config_model())

    async def update_config(self, config: YouTubeConfig) -> YouTubeConfig:
        config = validate_youtube_config(config)
        model = await self._get_config_model()

        model.keywords = config.keywords
        model.channel_ids = config.channel_ids
        model.languages = config.languages
        model.max_results = config.max_results
        model.days_back = config.days_back
        model.last_search_at = config.last_search_at
        model.updated_at = datetime.now(timezone.utc)

        await self.session.commit()
        await self.session.refresh(model)

        return _to_config_entity(model)