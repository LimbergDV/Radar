"""Endpoints del feed unificado y de las estadisticas del dashboard."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.dtos.feed_dto import FeedResponse, FeedStats
from src.application.services.feed_service import FeedService, VALID_SOURCES
from src.presentation.dependencies import get_db

router = APIRouter()


@router.get("/feed", response_model=FeedResponse)
async def get_unified_feed(
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    source: str | None = Query(None, description=f"Una de: {', '.join(VALID_SOURCES)}"),
    language: str | None = Query(None, description="Filtra por idioma: 'es', 'en'"),
    q: str | None = Query(None, description="Busqueda por texto en el titulo"),
    db: AsyncSession = Depends(get_db),
):
    """Feed homogeneo con items de las tres fuentes, del mas nuevo al mas viejo.

    Cada item trae `source` ('youtube' | 'news' | 'github') y un `stats` con las
    metricas propias de esa fuente, para que el frontend pueda pintar la card
    correcta sin saber de donde viene el dato.
    """
    try:
        return await FeedService(db).get_feed(limit, offset, source, language, q)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/feed/stats", response_model=FeedStats)
async def get_feed_stats(db: AsyncSession = Depends(get_db)):
    """Totales por fuente, ultima sincronizacion y rankings para el dashboard."""
    return await FeedService(db).get_stats()