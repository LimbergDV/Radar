"""Endpoints de GitHub."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.dtos.github_dto import (
    GitHubConfigResponse,
    GitHubConfigUpdate,
    GitHubRepoDetail,
    GitHubRepoSummary,
)
from src.application.dtos.youtube_dto import SyncResponse
from src.application.services.github_service import GitHubService, GitHubServiceError
from src.presentation.dependencies import get_db

router = APIRouter()


@router.get("/repos", response_model=list[GitHubRepoSummary])
async def get_github_repos(
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    language: str | None = Query(None, description="Filtra por lenguaje: 'Python'"),
    topic: str | None = Query(None, description="Filtra por topic exacto"),
    min_stars: int | None = Query(None, ge=0, description="Minimo de estrellas"),
    db: AsyncSession = Depends(get_db),
):
    """Lista repositorios paginados, ordenados por estrellas."""
    repos = await GitHubService(db).get_repos(limit, offset, language, topic, min_stars)
    return [GitHubRepoSummary(**vars(r)) for r in repos]


@router.get("/repos/{repo_id}", response_model=GitHubRepoDetail)
async def get_github_repo(repo_id: int, db: AsyncSession = Depends(get_db)):
    """Detalle de un repositorio, con el README completo."""
    repo = await GitHubService(db).get_repo(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repositorio {repo_id} no encontrado")
    return GitHubRepoDetail(**vars(repo))


@router.post("/sync", response_model=SyncResponse)
async def sync_github_repos(db: AsyncSession = Depends(get_db)):
    """Dispara la sincronizacion manual desde el boton de la web."""
    try:
        return await GitHubService(db).sync_repos()
    except GitHubServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/config", response_model=GitHubConfigResponse)
async def get_github_config(db: AsyncSession = Depends(get_db)):
    """Configuracion de la busqueda (keywords, topics, umbrales)."""
    return GitHubConfigResponse(**vars(await GitHubService(db).get_config()))


@router.put("/config", response_model=GitHubConfigResponse)
async def update_github_config(
    payload: GitHubConfigUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Actualiza los filtros de busqueda. No dispara sync."""
    service = GitHubService(db)
    current = await service.get_config()

    current.keywords = payload.keywords
    current.days_active = payload.days_active
    current.min_stars = payload.min_stars
    current.min_forks = payload.min_forks
    current.require_license = payload.require_license
    current.selected_topics = payload.selected_topics
    current.selected_languages = payload.selected_languages
    current.max_results = payload.max_results

    saved = await service.update_config(current)
    return GitHubConfigResponse(**vars(saved))