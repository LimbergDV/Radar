"""Implementacion PostgreSQL del repositorio de GitHub."""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.entities.config import GitHubConfig
from src.core.entities.github import GitHubRepo
from src.core.repositories.github_repository import GitHubRepository as GitHubRepositoryBase
from src.core.use_cases.update_source_config import validate_github_config
from src.infrastructure.database.models import GitHubConfigModel, GitHubRepoModel

CONFIG_ID = 1


def _to_entity(model: GitHubRepoModel) -> GitHubRepo:
    return GitHubRepo(
        id=model.id,
        name=model.name,
        full_name=model.full_name,
        html_url=model.html_url,
        description=model.description or "",
        stargazers_count=model.stargazers_count,
        forks_count=model.forks_count,
        open_issues_count=model.open_issues_count,
        watchers_count=model.watchers_count,
        language=model.language or "",
        topics=list(model.topics or []),
        readme=model.readme or "",
        updated_at=model.updated_at,
        synced_at=model.synced_at,
        owner_avatar_url=model.owner_avatar_url,
        license=model.license,
        homepage=model.homepage,
        size_kb=model.size_kb,
        default_branch=model.default_branch,
    )


class GitHubRepository(GitHubRepositoryBase):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_repos(self, repos: list[GitHubRepo]) -> int:
        if not repos:
            return 0

        values = [
            {
                "id": r.id,
                "name": r.name,
                "full_name": r.full_name,
                "html_url": r.html_url,
                "description": r.description,
                "stargazers_count": r.stargazers_count,
                "forks_count": r.forks_count,
                "open_issues_count": r.open_issues_count,
                "watchers_count": r.watchers_count,
                "language": r.language,
                "license": r.license,
                "topics": r.topics,
                "readme": r.readme,
                "owner_avatar_url": r.owner_avatar_url,
                "homepage": r.homepage,
                "size_kb": r.size_kb,
                "default_branch": r.default_branch,
                "updated_at": r.updated_at,
                "synced_at": r.synced_at,
            }
            for r in repos
        ]

        stmt = insert(GitHubRepoModel).values(values)
        # Un README vacio no borra el que ya teniamos.
        stmt = stmt.on_conflict_do_update(
            index_elements=["id"],
            set_={
                "description": stmt.excluded.description,
                "stargazers_count": stmt.excluded.stargazers_count,
                "forks_count": stmt.excluded.forks_count,
                "open_issues_count": stmt.excluded.open_issues_count,
                "watchers_count": stmt.excluded.watchers_count,
                "topics": stmt.excluded.topics,
                "owner_avatar_url": stmt.excluded.owner_avatar_url,
                "homepage": stmt.excluded.homepage,
                "updated_at": stmt.excluded.updated_at,
                "synced_at": stmt.excluded.synced_at,
                "readme": func.coalesce(
                    func.nullif(stmt.excluded.readme, ""), GitHubRepoModel.readme
                ),
                "size_kb": stmt.excluded.size_kb,
                "default_branch": stmt.excluded.default_branch,
            },
        )

        await self.session.execute(stmt)
        await self.session.commit()
        return len(repos)

    async def get_repos(
        self,
        limit: int = 20,
        offset: int = 0,
        language: str | None = None,
        topic: str | None = None,
        min_stars: int | None = None,
    ) -> list[GitHubRepo]:
        stmt = select(GitHubRepoModel).order_by(GitHubRepoModel.stargazers_count.desc())

        if language:
            stmt = stmt.where(GitHubRepoModel.language.ilike(f"%{language}%"))
        if topic:
            # Operador de contencion (@>): busca el topic exacto en el array JSONB.
            stmt = stmt.where(GitHubRepoModel.topics.contains([topic]))
        if min_stars:
            stmt = stmt.where(GitHubRepoModel.stargazers_count >= min_stars)

        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return [_to_entity(m) for m in result.scalars().all()]

    async def get_repo_by_id(self, repo_id: int) -> GitHubRepo | None:
        result = await self.session.execute(
            select(GitHubRepoModel).where(GitHubRepoModel.id == repo_id)
        )
        model = result.scalar_one_or_none()
        return _to_entity(model) if model else None

    async def count_repos(
        self,
        language: str | None = None,
        since: datetime | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(GitHubRepoModel)
        if language:
            stmt = stmt.where(GitHubRepoModel.language.ilike(f"%{language}%"))
        if since:
            stmt = stmt.where(GitHubRepoModel.updated_at >= since)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def top_languages(self, limit: int = 5) -> list[tuple[str, int]]:
        stmt = (
            select(GitHubRepoModel.language, func.count().label("total"))
            .where(GitHubRepoModel.language != "")
            .group_by(GitHubRepoModel.language)
            .order_by(func.count().desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def latest_repo_date(self) -> datetime | None:
        result = await self.session.execute(select(func.max(GitHubRepoModel.updated_at)))
        return result.scalar_one_or_none()

    async def _get_config_model(self) -> GitHubConfigModel:
        result = await self.session.execute(
            select(GitHubConfigModel).where(GitHubConfigModel.id == CONFIG_ID)
        )
        model = result.scalar_one_or_none()

        if not model:
            model = GitHubConfigModel(id=CONFIG_ID)
            self.session.add(model)
            await self.session.commit()
            await self.session.refresh(model)

        return model

    async def get_config(self) -> GitHubConfig:
        model = await self._get_config_model()
        return GitHubConfig(
            keywords=list(model.keywords or []),
            days_active=model.days_active,
            min_stars=model.min_stars,
            min_forks=model.min_forks,
            require_license=model.require_license,
            selected_topics=list(model.selected_topics or []),
            selected_languages=list(model.selected_languages or []),
            max_results=model.max_results,
            last_search_at=model.last_search_at,
        )

    async def update_config(self, config: GitHubConfig) -> GitHubConfig:
        config = validate_github_config(config)
        model = await self._get_config_model()

        model.keywords = config.keywords
        model.days_active = config.days_active
        model.min_stars = config.min_stars
        model.min_forks = config.min_forks
        model.require_license = config.require_license
        model.selected_topics = config.selected_topics
        model.selected_languages = config.selected_languages
        model.max_results = config.max_results
        model.last_search_at = config.last_search_at
        model.updated_at = datetime.now(timezone.utc)

        await self.session.commit()
        await self.session.refresh(model)

        return GitHubConfig(
            keywords=list(model.keywords or []),
            days_active=model.days_active,
            min_stars=model.min_stars,
            min_forks=model.min_forks,
            require_license=model.require_license,
            selected_topics=list(model.selected_topics or []),
            selected_languages=list(model.selected_languages or []),
            max_results=model.max_results,
            last_search_at=model.last_search_at,
        )