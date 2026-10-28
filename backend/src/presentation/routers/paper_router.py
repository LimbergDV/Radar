"""Endpoints de papers de Hugging Face."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.dtos.paper_dto import (
    PaperConfigResponse,
    PaperConfigUpdate,
    PaperDetail,
    PaperSummary,
)
from src.application.dtos.youtube_dto import SyncResponse
from src.application.services.paper_service import PaperService, PaperServiceError
from src.presentation.dependencies import get_db

router = APIRouter()

VALID_ORDERS = ("recent", "top")


@router.get("", response_model=list[PaperSummary])
async def get_papers(
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    q: str | None = Query(None, description="Busca en título y abstract"),
    since_days: int | None = Query(
        None, ge=1, le=365, description="Solo papers de los últimos N días"
    ),
    order: str = Query("recent", description="'recent' (fecha) o 'top' (votos)"),
    db: AsyncSession = Depends(get_db),
):
    """Lista papers paginados, con búsqueda y ventana temporal opcionales."""
    if order not in VALID_ORDERS:
        raise HTTPException(
            status_code=422, detail=f"order inválido: {order!r}. Usa recent o top."
        )

    since = None
    if since_days:
        since = datetime.now(timezone.utc) - timedelta(days=since_days)

    papers = await PaperService(db).get_papers(limit, offset, q, since, order)
    return [PaperSummary(**vars(paper)) for paper in papers]


@router.get("/config", response_model=PaperConfigResponse)
async def get_papers_config(db: AsyncSession = Depends(get_db)):
    """Configuración del sync (keywords, ventana y vías activas)."""
    return PaperConfigResponse(**vars(await PaperService(db).get_config()))


@router.put("/config", response_model=PaperConfigResponse)
async def update_papers_config(
    payload: PaperConfigUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Actualiza la configuración. No dispara sync."""
    service = PaperService(db)
    current = await service.get_config()

    current.keywords = payload.keywords
    current.max_results = payload.max_results
    current.days_back = payload.days_back
    current.include_daily = payload.include_daily
    current.include_search = payload.include_search

    saved = await service.update_config(current)
    return PaperConfigResponse(**vars(saved))


@router.post("/sync", response_model=SyncResponse)
async def sync_papers(db: AsyncSession = Depends(get_db)):
    """Dispara la sincronización manual desde el botón de la web."""
    try:
        return await PaperService(db).sync_papers()
    except PaperServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{paper_id}", response_model=PaperDetail)
async def get_paper(paper_id: str, db: AsyncSession = Depends(get_db)):
    """Detalle de un paper, con abstract y AI summary."""
    paper = await PaperService(db).get_paper(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail=f"Paper {paper_id} no encontrado")
    return PaperDetail(**vars(paper))
