"""Endpoints de YouTube."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.dtos.youtube_dto import (
    SyncResponse,
    YouTubeConfigResponse,
    YouTubeConfigUpdate,
    YouTubeVideoDetail,
    YouTubeVideoSummary,
)
from src.application.services.youtube_service import YouTubeService, YouTubeServiceError
from src.presentation.dependencies import get_db

router = APIRouter()


@router.get("/videos", response_model=list[YouTubeVideoSummary])
async def get_youtube_videos(
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    language: str | None = Query(None, description="Filtra por prefijo: 'es', 'en'"),
    db: AsyncSession = Depends(get_db),
):
    """Lista videos paginados (sin transcripcion, para no inflar la respuesta)."""
    service = YouTubeService(db)
    videos = await service.get_videos(limit, offset, language)
    return [YouTubeVideoSummary(**vars(v)) for v in videos]


@router.get("/videos/{video_id}", response_model=YouTubeVideoDetail)
async def get_youtube_video(video_id: str, db: AsyncSession = Depends(get_db)):
    """Detalle de un video, incluida la transcripcion completa."""
    video = await YouTubeService(db).get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail=f"Video {video_id} no encontrado")
    return YouTubeVideoDetail(**vars(video))


@router.post("/sync", response_model=SyncResponse)
async def sync_youtube_videos(db: AsyncSession = Depends(get_db)):
    """Dispara la sincronizacion manual (lo usa el boton de la web)."""
    try:
        return await YouTubeService(db).sync_videos()
    except YouTubeServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/config", response_model=YouTubeConfigResponse)
async def get_youtube_config(db: AsyncSession = Depends(get_db)):
    """Configuracion de busqueda (keywords, canales, idiomas, limite)."""
    return YouTubeConfigResponse(**vars(await YouTubeService(db).get_config()))


@router.put("/config", response_model=YouTubeConfigResponse)
async def update_youtube_config(
    payload: YouTubeConfigUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Actualiza la configuracion de busqueda. No dispara sync."""
    service = YouTubeService(db)
    current = await service.get_config()

    current.keywords = payload.keywords
    current.channel_ids = payload.channel_ids
    current.languages = payload.languages
    current.max_results = payload.max_results

    saved = await service.update_config(current)
    return YouTubeConfigResponse(**vars(saved))