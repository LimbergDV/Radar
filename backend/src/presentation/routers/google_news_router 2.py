"""Endpoints de Google News."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.dtos.google_news_dto import (
    GoogleNewsArticleDetail,
    GoogleNewsArticleSummary,
    GoogleNewsConfigResponse,
    GoogleNewsConfigUpdate,
)
from src.application.dtos.youtube_dto import SyncResponse
from src.application.services.google_news_service import (
    GoogleNewsService,
    GoogleNewsServiceError,
)
from src.presentation.dependencies import get_db

router = APIRouter()


@router.get("/articles", response_model=list[GoogleNewsArticleSummary])
async def get_news_articles(
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    language: str | None = Query(None, description="Filtra por idioma: 'es', 'en'"),
    source: str | None = Query(None, description="Filtra por nombre del medio"),
    since_days: int | None = Query(
        None, ge=1, le=365, description="Solo articulos de los ultimos N dias"
    ),
    db: AsyncSession = Depends(get_db),
):
    """Lista articulos paginados, con filtros opcionales."""
    since = None
    if since_days:
        from datetime import timedelta, timezone

        since = datetime.now(timezone.utc) - timedelta(days=since_days)

    articles = await GoogleNewsService(db).get_articles(limit, offset, language, source, since)
    return [GoogleNewsArticleSummary(**vars(a)) for a in articles]


@router.get("/articles/{article_id}", response_model=GoogleNewsArticleDetail)
async def get_news_article(article_id: str, db: AsyncSession = Depends(get_db)):
    """Detalle de un articulo, con el cuerpo si se pudo extraer."""
    article = await GoogleNewsService(db).get_article(article_id)
    if not article:
        raise HTTPException(status_code=404, detail=f"Articulo {article_id} no encontrado")
    return GoogleNewsArticleDetail(**vars(article))


@router.post("/sync", response_model=SyncResponse)
async def sync_news_articles(db: AsyncSession = Depends(get_db)):
    """Dispara la sincronizacion manual desde el boton de la web."""
    try:
        return await GoogleNewsService(db).sync_articles()
    except GoogleNewsServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/config", response_model=GoogleNewsConfigResponse)
async def get_news_config(db: AsyncSession = Depends(get_db)):
    """Configuracion de la query RSS."""
    return GoogleNewsConfigResponse(**vars(await GoogleNewsService(db).get_config()))


@router.put("/config", response_model=GoogleNewsConfigResponse)
async def update_news_config(
    payload: GoogleNewsConfigUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Actualiza la query RSS. No dispara sync."""
    service = GoogleNewsService(db)
    current = await service.get_config()

    current.q = payload.q
    current.hl = payload.hl
    current.gl = payload.gl
    current.ceid = payload.ceid
    current.when = payload.when
    current.site = payload.site
    current.intitle = payload.intitle
    current.max_results = payload.max_results
    current.days_window = payload.days_window

    saved = await service.update_config(current)
    return GoogleNewsConfigResponse(**vars(saved))