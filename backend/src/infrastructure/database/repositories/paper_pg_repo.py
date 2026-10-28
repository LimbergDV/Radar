"""Implementación PostgreSQL del repositorio de papers."""

from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.entities.config import PaperConfig
from src.core.entities.paper import HuggingFacePaper
from src.core.repositories.paper_repository import PaperRepository as PaperRepositoryBase
from src.core.use_cases.update_source_config import validate_paper_config
from src.infrastructure.database.models import PaperConfigModel, PaperModel

CONFIG_ID = 1


def _effective_date():
    """Fecha de orden: la entrada al Daily si existe, si no la publicación."""
    return func.coalesce(PaperModel.submitted_on_daily_at, PaperModel.published_at)


def _to_entity(model: PaperModel) -> HuggingFacePaper:
    return HuggingFacePaper(
        id=model.id,
        title=model.title or "",
        abstract=model.abstract or "",
        ai_summary=model.ai_summary or "",
        ai_keywords=list(model.ai_keywords or []),
        authors=list(model.authors or []),
        published_at=model.published_at,
        submitted_on_daily_at=model.submitted_on_daily_at,
        upvotes=model.upvotes,
        comments=model.comments,
        thumbnail_url=model.thumbnail_url,
        github_repo=model.github_repo,
        project_page=model.project_page,
        organization=model.organization,
        linked_models=list(model.linked_models or []),
        linked_datasets=list(model.linked_datasets or []),
        linked_spaces=list(model.linked_spaces or []),
        hf_url=model.hf_url,
        arxiv_url=model.arxiv_url,
        pdf_url=model.pdf_url,
        source=model.source,
        synced_at=model.synced_at,
    )


class PaperRepository(PaperRepositoryBase):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_papers(self, papers: list[HuggingFacePaper]) -> int:
        if not papers:
            return 0

        values = [
            {
                "id": p.id,
                "title": p.title,
                "abstract": p.abstract,
                "ai_summary": p.ai_summary,
                "ai_keywords": p.ai_keywords,
                "authors": p.authors,
                "published_at": p.published_at,
                "submitted_on_daily_at": p.submitted_on_daily_at,
                "upvotes": p.upvotes,
                "comments": p.comments,
                "thumbnail_url": p.thumbnail_url,
                "github_repo": p.github_repo,
                "project_page": p.project_page,
                "organization": p.organization,
                "linked_models": p.linked_models,
                "linked_datasets": p.linked_datasets,
                "linked_spaces": p.linked_spaces,
                "hf_url": p.hf_url,
                "arxiv_url": p.arxiv_url,
                "pdf_url": p.pdf_url,
                "source": p.source,
                "synced_at": p.synced_at,
            }
            for p in papers
        ]

        stmt = insert(PaperModel).values(values)
        # Un abstract o AI summary vacío no debe borrar el que ya teníamos: la
        # búsqueda a veces devuelve menos campos que el Daily Papers.
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "title": stmt.excluded.title,
                "abstract": func.coalesce(
                    func.nullif(stmt.excluded.abstract, ""), PaperModel.abstract
                ),
                "ai_summary": func.coalesce(
                    func.nullif(stmt.excluded.ai_summary, ""), PaperModel.ai_summary
                ),
                "ai_keywords": stmt.excluded.ai_keywords,
                "authors": stmt.excluded.authors,
                "published_at": stmt.excluded.published_at,
                "submitted_on_daily_at": func.coalesce(
                    stmt.excluded.submitted_on_daily_at, PaperModel.submitted_on_daily_at
                ),
                "upvotes": func.greatest(stmt.excluded.upvotes, PaperModel.upvotes),
                "comments": func.greatest(stmt.excluded.comments, PaperModel.comments),
                "thumbnail_url": func.coalesce(
                    stmt.excluded.thumbnail_url, PaperModel.thumbnail_url
                ),
                "github_repo": func.coalesce(stmt.excluded.github_repo, PaperModel.github_repo),
                "project_page": func.coalesce(
                    stmt.excluded.project_page, PaperModel.project_page
                ),
                "organization": func.coalesce(
                    stmt.excluded.organization, PaperModel.organization
                ),
                "linked_models": stmt.excluded.linked_models,
                "linked_datasets": stmt.excluded.linked_datasets,
                "linked_spaces": stmt.excluded.linked_spaces,
                "hf_url": stmt.excluded.hf_url,
                "arxiv_url": stmt.excluded.arxiv_url,
                "pdf_url": stmt.excluded.pdf_url,
                "source": stmt.excluded.source,
                "synced_at": stmt.excluded.synced_at,
            },
        )

        await self.session.execute(stmt)
        await self.session.commit()
        return len(papers)

    async def get_papers(
        self,
        limit: int = 20,
        offset: int = 0,
        query: str | None = None,
        since: datetime | None = None,
        order: str = "recent",
    ) -> list[HuggingFacePaper]:
        stmt = select(PaperModel)

        if query:
            like = f"%{query.strip()}%"
            stmt = stmt.where(
                or_(PaperModel.title.ilike(like), PaperModel.abstract.ilike(like))
            )
        if since:
            stmt = stmt.where(_effective_date() >= since)

        if order == "top":
            stmt = stmt.order_by(PaperModel.upvotes.desc(), _effective_date().desc())
        else:
            stmt = stmt.order_by(_effective_date().desc(), PaperModel.upvotes.desc())

        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return [_to_entity(model) for model in result.scalars().all()]

    async def get_paper_by_id(self, paper_id: str) -> HuggingFacePaper | None:
        result = await self.session.execute(
            select(PaperModel).where(PaperModel.id == paper_id)
        )
        model = result.scalar_one_or_none()
        return _to_entity(model) if model else None

    async def count_papers(self, since: datetime | None = None) -> int:
        stmt = select(func.count()).select_from(PaperModel)
        if since:
            stmt = stmt.where(_effective_date() >= since)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def latest_paper_date(self) -> datetime | None:
        result = await self.session.execute(select(func.max(_effective_date())))
        return result.scalar_one_or_none()

    async def _get_config_model(self) -> PaperConfigModel:
        result = await self.session.execute(
            select(PaperConfigModel).where(PaperConfigModel.id == CONFIG_ID)
        )
        model = result.scalar_one_or_none()

        if not model:
            model = PaperConfigModel(id=CONFIG_ID)
            self.session.add(model)
            await self.session.commit()
            await self.session.refresh(model)

        return model

    async def get_config(self) -> PaperConfig:
        model = await self._get_config_model()
        return PaperConfig(
            keywords=list(model.keywords or []),
            max_results=model.max_results,
            days_back=model.days_back,
            include_daily=model.include_daily,
            include_search=model.include_search,
            last_search_at=model.last_search_at,
        )

    async def update_config(self, config: PaperConfig) -> PaperConfig:
        config = validate_paper_config(config)
        model = await self._get_config_model()

        model.keywords = config.keywords
        model.max_results = config.max_results
        model.days_back = config.days_back
        model.include_daily = config.include_daily
        model.include_search = config.include_search
        model.last_search_at = config.last_search_at
        model.updated_at = datetime.now(timezone.utc)

        await self.session.commit()
        await self.session.refresh(model)

        return PaperConfig(
            keywords=list(model.keywords or []),
            max_results=model.max_results,
            days_back=model.days_back,
            include_daily=model.include_daily,
            include_search=model.include_search,
            last_search_at=model.last_search_at,
        )
