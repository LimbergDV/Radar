from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.session import get_db
from src.application.services.google_news_service import GoogleNewsService
from src.infrastructure.database.repositories.google_news_pg_repo import GoogleNewsRepository
from src.application.dtos.google_news_dto import GoogleNewsConfigUpdate

router = APIRouter()

@router.get("/articles")
async def get_news_articles(limit: int = Query(20, ge=1, le=50), offset: int = Query(0, ge=0), db: AsyncSession = Depends(get_db)):
    return await GoogleNewsService.get_feed(db, limit, offset)

@router.post("/sync")
async def sync_news_articles(db: AsyncSession = Depends(get_db)):
    return await GoogleNewsService.sync_articles(db)

@router.get("/config")
async def get_news_config(db: AsyncSession = Depends(get_db)):
    repo = GoogleNewsRepository(db)
    return await repo.get_config()

@router.put("/config")
async def update_news_config(payload: GoogleNewsConfigUpdate, db: AsyncSession = Depends(get_db)):
    repo = GoogleNewsRepository(db)
    config = await repo.get_config()
    
    config.q = payload.q
    config.hl = payload.hl
    config.gl = payload.gl
    config.ceid = payload.ceid
    config.when = payload.when
    config.site = payload.site
    config.intitle = payload.intitle
    config.max_results = payload.max_results
    
    await repo.update_config(config)
    return {"status": "success", "config": config}