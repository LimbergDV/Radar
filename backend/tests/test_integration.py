"""Tests de integracion contra PostgreSQL.

Se saltan solos si `RUN_DB_TESTS` no esta en 1, para que `pytest` siga siendo
util sin la base de datos levantada.

    RUN_DB_TESTS=1 pytest tests/test_integration.py

Cada test limpia lo que inserta, para no dejar basura en la base de datos.
"""

import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, func, select

from src.infrastructure.database.models import GitHubRepoModel, GoogleNewsArticleModel

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_TESTS") != "1",
    reason="Requiere PostgreSQL. Activa con RUN_DB_TESTS=1",
)

@pytest.fixture
async def session():
    from src.infrastructure.database.session import AsyncSessionLocal, dispose_engine

    async with AsyncSessionLocal() as s:
        yield s

    # Los ids usados aqui no colisionan con datos reales.
    async with AsyncSessionLocal() as s:
        await s.execute(delete(GitHubRepoModel).where(GitHubRepoModel.id < 0))
        await s.execute(
            delete(GoogleNewsArticleModel).where(GoogleNewsArticleModel.id.like("testid%"))
        )
        await s.commit()

    # Sin cerrar el pool, asyncpg cancela conexiones en un loop ya cerrado.
    await dispose_engine()

async def test_config_is_created_on_first_access(session):
    from src.infrastructure.database.repositories.youtube_pg_repo import YouTubeRepository

    repo = YouTubeRepository(session)
    config = await repo.get_config()

    assert isinstance(config.max_results, int)
    assert config.languages

async def test_update_config_preserves_last_search_at(session):
    """Regresion: antes `update_config` ponia last_search_at=now() siempre,
    asi que guardar la configuracion parecia una sincronizacion."""
    from src.infrastructure.database.repositories.google_news_pg_repo import (
        GoogleNewsRepository,
    )

    repo = GoogleNewsRepository(session)
    original = await repo.get_config()

    try:
        marca = datetime(2020, 1, 1, tzinfo=timezone.utc)
        config = await repo.get_config()
        config.last_search_at = marca
        config.q = "TEST unico 12345"
        saved = await repo.update_config(config)

        assert saved.last_search_at == marca, "update_config no debe tocar last_search_at"

        reread = await repo.get_config()
        assert reread.last_search_at == marca
    finally:
        restore = await repo.get_config()
        restore.q = original.q
        restore.last_search_at = original.last_search_at
        await repo.update_config(restore)

async def test_update_config_validates_values(session):
    from src.infrastructure.database.repositories.github_pg_repo import GitHubRepository

    repo = GitHubRepository(session)
    original = await repo.get_config()

    try:
        config = await repo.get_config()
        config.keywords = ["  openai  ", "openai", ""]
        config.max_results = 9999
        saved = await repo.update_config(config)

        assert saved.keywords == ["openai"], "debe limpiar duplicados y vacios"
        assert saved.max_results == 100, "debe aplicar el techo de max_results"
    finally:
        restore = await repo.get_config()
        restore.keywords = original.keywords
        restore.max_results = original.max_results
        await repo.update_config(restore)

async def test_save_repos_upserts_without_duplicating(session):
    """Sincronizar dos veces no debe duplicar filas ni perder el README."""
    from src.core.entities.github import GitHubRepo
    from src.infrastructure.database.repositories.github_pg_repo import GitHubRepository

    repo = GitHubRepository(session)
    now = datetime.now(timezone.utc)

    def make(stars: int, readme: str) -> GitHubRepo:
        return GitHubRepo(
            id=-1,  # id negativo: nunca choca con repos reales
            name="test-repo",
            full_name="test-owner/test-repo",
            html_url="https://github.com/test-owner/test-repo",
            description="Repo de prueba",
            stargazers_count=stars,
            forks_count=1,
            open_issues_count=0,
            language="Python",
            topics=["ai"],
            readme=readme,
            updated_at=now,
            synced_at=now,
            license="MIT",
        )

    await repo.save_repos([make(100, "README original")])
    await repo.save_repos([make(250, "")])  # segunda sync: stats suben, README vacio

    count = (
        await session.execute(select(func.count()).select_from(GitHubRepoModel).where(GitHubRepoModel.id == -1))
    ).scalar_one()
    assert count == 1, "el upsert debe actualizar, no duplicar"

    stored = (await session.execute(select(GitHubRepoModel).where(GitHubRepoModel.id == -1))).scalar_one()
    assert stored.stargazers_count == 250, "las stats deben refrescarse"
    assert stored.readme == "README original", "un README vacio no debe borrar el existente"

    await repo.save_repos([])  # lista vacia no debe fallar

async def test_get_repos_filters_by_topic(session):
    from src.infrastructure.database.repositories.github_pg_repo import GitHubRepository

    repo = GitHubRepository(session)
    results = await repo.get_repos(topic="llm")
    # Sin datos: solo comprobamos que no rompe.
    assert isinstance(results, list)

async def test_count_and_top_helpers(session):
    from src.infrastructure.database.repositories.github_pg_repo import GitHubRepository

    repo = GitHubRepository(session)
    assert await repo.count_repos() >= 0
    assert isinstance(await repo.top_languages(3), list)
    assert isinstance(await repo.latest_repo_date(), (datetime, type(None)))

async def test_news_article_roundtrip(session):
    from src.core.entities.google_news import GoogleNewsArticle
    from src.infrastructure.database.repositories.google_news_pg_repo import (
        GoogleNewsRepository,
    )

    repo = GoogleNewsRepository(session)
    now = datetime.now(timezone.utc)

    # Link largo tipo Google: el caso que reventaba VARCHAR(512).
    link = "https://news.google.com/rss/articles/" + "A" * 700 + "?oc=5"
    article = GoogleNewsArticle(
        id="testid" + "0" * 34,
        title="Articulo de prueba",
        link=link,
        pub_date=now,
        source_name="Medio de prueba",
        source_url="https://medio.example",
        language="es",
        fetched_at=now,
        original_link=link,
    )

    await repo.save_articles([article])
    stored = await repo.get_article_by_id(article.id)

    assert stored is not None
    assert stored.link == link, "el link largo debe guardarse completo"
    assert stored.original_link == link

    await session.execute(
        delete(GoogleNewsArticleModel).where(GoogleNewsArticleModel.id == article.id)
    )
    await session.commit()