from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.session import get_db
from src.application.services.youtube_service import YouTubeService
from src.infrastructure.database.repositories.youtube_pg_repo import YouTubeRepository

# 1. Agrega esta nueva importación:
from src.application.dtos.youtube_dto import YouTubeConfigUpdate

router = APIRouter()

@router.get("/videos")
async def get_youtube_videos(
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    return await YouTubeService.get_feed(db, limit, offset)


@router.post("/sync")
async def sync_youtube_videos(db: AsyncSession = Depends(get_db)):
    return await YouTubeService.sync_videos(db)


# ----- NUEVOS ENDPOINTS PARA LA CONFIGURACIÓN -----

@router.get("/config")
async def get_youtube_config(db: AsyncSession = Depends(get_db)):
    repo = YouTubeRepository(db)
    return await repo.get_config()


@router.put("/config")
async def update_youtube_config(
    payload: YouTubeConfigUpdate, 
    db: AsyncSession = Depends(get_db)
):
    repo = YouTubeRepository(db)
    config = await repo.get_config()
    
    config.keywords = payload.keywords
    config.channel_ids = payload.channel_ids
    config.languages = payload.languages
    config.max_results = payload.max_results
    
    await repo.update_config(config)
    return {"status": "success", "config": config}