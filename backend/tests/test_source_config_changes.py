"""Regresion: cambiar la configuracion debe cambiar el feed.

Las fuentes guardaban lo que alguna vez devolvio una busqueda y nunca lo
borraban, asi que al cambiar keywords/consulta el contenido viejo seguia
mezclado con el nuevo. Estos tests fijan el contrato:

- Si cambian los criterios de busqueda, el feed de esa fuente se vacia.
- Si se guarda la misma config (aunque venga en otro orden), no se vacia.
- En el sync, los items que ya no devuelve la busqueda se podan.
"""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)


# --------------------------------------------------------------------------
# Noticias
# --------------------------------------------------------------------------


def _news_payload(**overrides):
    from src.application.dtos.google_news_dto import GoogleNewsConfigUpdate

    values = {
        "q": "Inteligencia Artificial OR IA",
        "hl": "es-419",
        "gl": "MX",
        "ceid": "MX:es-419",
        "when": "1d",
        "site": "",
        "intitle": "",
        "max_results": 50,
        "days_window": 1,
    }
    values.update(overrides)
    return GoogleNewsConfigUpdate(**values)


@pytest.mark.asyncio
async def test_news_query_change_clears_feed(monkeypatch):
    from src.core.entities.config import GoogleNewsConfig
    from src.presentation.routers import google_news_router as router

    calls = {"cleared": 0, "saved": None}

    class FakeService:
        def __init__(self, db):
            self.db = db

        async def get_config(self):
            return GoogleNewsConfig(q="Inteligencia Artificial OR IA", ceid="MX:es-419")

        async def update_config(self, config):
            calls["saved"] = config
            return config

        async def clear_articles(self):
            calls["cleared"] += 1
            return 248

    monkeypatch.setattr(router, "GoogleNewsService", FakeService)

    saved = await router.update_news_config(_news_payload(q="resultados futbol"), db=object())

    assert calls["cleared"] == 1
    assert saved.q == "resultados futbol"
    assert calls["saved"].q == "resultados futbol"


@pytest.mark.asyncio
async def test_news_saving_same_query_does_not_clear_feed(monkeypatch):
    from src.core.entities.config import GoogleNewsConfig
    from src.presentation.routers import google_news_router as router

    calls = {"cleared": 0}

    class FakeService:
        def __init__(self, db):
            self.db = db

        async def get_config(self):
            return GoogleNewsConfig(
                q="Inteligencia Artificial OR IA",
                ceid="MX:es-419",
                when="1d",
                site="",
                intitle="",
            )

        async def update_config(self, config):
            return config

        async def clear_articles(self):
            calls["cleared"] += 1
            return 0

    monkeypatch.setattr(router, "GoogleNewsService", FakeService)

    # Misma consulta, distinta capitalizacion/espacios.
    await router.update_news_config(
        _news_payload(q="  inteligencia artificial or ia  "), db=object()
    )

    assert calls["cleared"] == 0


@pytest.mark.asyncio
async def test_news_changing_only_max_results_does_not_clear(monkeypatch):
    """`max_results` recorta, no cambia QUE articulos devuelve la consulta."""
    from src.core.entities.config import GoogleNewsConfig
    from src.presentation.routers import google_news_router as router

    calls = {"cleared": 0}

    class FakeService:
        def __init__(self, db):
            self.db = db

        async def get_config(self):
            return GoogleNewsConfig(
                q="Inteligencia Artificial OR IA",
                ceid="MX:es-419",
                when="1d",
                site="",
                intitle="",
            )

        async def update_config(self, config):
            return config

        async def clear_articles(self):
            calls["cleared"] += 1
            return 0

    monkeypatch.setattr(router, "GoogleNewsService", FakeService)

    await router.update_news_config(_news_payload(max_results=10), db=object())

    assert calls["cleared"] == 0


# --------------------------------------------------------------------------
# GitHub
# --------------------------------------------------------------------------


def _github_payload(**overrides):
    from src.application.dtos.github_dto import GitHubConfigUpdate

    values = {
        "keywords": ["openai", "claude", "langchain"],
        "days_active": 2,
        "min_stars": 50,
        "min_forks": 10,
        "require_license": False,
        "selected_topics": ["ai", "llm"],
        "selected_languages": ["python", "typescript"],
        "max_results": 50,
    }
    values.update(overrides)
    return GitHubConfigUpdate(**values)


@pytest.mark.asyncio
async def test_github_criteria_change_clears_feed(monkeypatch):
    from src.core.entities.config import GitHubConfig
    from src.presentation.routers import github_router as router

    calls = {"cleared": 0}

    class FakeService:
        def __init__(self, db):
            self.db = db

        async def get_config(self):
            return GitHubConfig(
                keywords=["openai", "claude", "langchain"],
                selected_topics=["ai", "llm"],
                selected_languages=["python", "typescript"],
                days_active=2,
                min_stars=50,
                min_forks=10,
            )

        async def update_config(self, config):
            return config

        async def clear_repos(self):
            calls["cleared"] += 1
            return 50

    monkeypatch.setattr(router, "GitHubService", FakeService)

    saved = await router.update_github_config(
        _github_payload(keywords=["django", "flask"]), db=object()
    )

    assert calls["cleared"] == 1
    assert saved.keywords == ["django", "flask"]


@pytest.mark.asyncio
async def test_github_same_criteria_in_other_order_does_not_clear(monkeypatch):
    from src.core.entities.config import GitHubConfig
    from src.presentation.routers import github_router as router

    calls = {"cleared": 0}

    class FakeService:
        def __init__(self, db):
            self.db = db

        async def get_config(self):
            return GitHubConfig(
                keywords=["openai", "claude", "langchain"],
                selected_topics=["ai", "llm"],
                selected_languages=["python", "typescript"],
                days_active=2,
                min_stars=50,
                min_forks=10,
            )

        async def update_config(self, config):
            return config

        async def clear_repos(self):
            calls["cleared"] += 1
            return 0

    monkeypatch.setattr(router, "GitHubService", FakeService)

    await router.update_github_config(
        _github_payload(
            keywords=["LangChain", "claude", "openai"],
            selected_topics=["llm", "ai"],
            selected_languages=["typescript", "python"],
        ),
        db=object(),
    )

    assert calls["cleared"] == 0


@pytest.mark.asyncio
async def test_github_sync_prunes_repos_outside_current_search(monkeypatch):
    from src.application.services import github_service
    from src.core.entities.config import GitHubConfig

    calls = {"deleted": None, "saved": 0}

    class FakeRepo:
        async def get_config(self):
            return GitHubConfig(keywords=["django"])

        async def update_config(self, config):
            return config

        async def save_repos(self, repos):
            calls["saved"] = len(repos)
            return len(repos)

        async def delete_repos_not_in(self, ids):
            calls["deleted"] = list(ids)
            return 3

    class FakeFetcher:
        def __init__(self, token=""):
            pass

        async def sync_pipeline(self, config):
            return [SimpleNamespace(id=1), SimpleNamespace(id=2)]

    monkeypatch.setattr(github_service, "GitHubFetcher", FakeFetcher)

    service = github_service.GitHubService(session=object())
    service.repo = FakeRepo()

    result = await service.sync_repos()

    assert result["items_synced"] == 2
    assert calls["saved"] == 2
    assert calls["deleted"] == [1, 2]


@pytest.mark.asyncio
async def test_github_sync_without_results_does_not_prune(monkeypatch):
    """Un rate limit devuelve []: no puede vaciar el feed."""
    from src.application.services import github_service
    from src.core.entities.config import GitHubConfig

    calls = {"deleted": []}

    class FakeRepo:
        async def get_config(self):
            return GitHubConfig(keywords=["django"])

        async def update_config(self, config):
            return config

        async def save_repos(self, repos):
            return 0

        async def delete_repos_not_in(self, ids):
            calls["deleted"].append(list(ids))
            return 0

    class FakeFetcher:
        def __init__(self, token=""):
            pass

        async def sync_pipeline(self, config):
            return []

    monkeypatch.setattr(github_service, "GitHubFetcher", FakeFetcher)

    service = github_service.GitHubService(session=object())
    service.repo = FakeRepo()

    await service.sync_repos()

    assert calls["deleted"] == []


@pytest.mark.asyncio
async def test_github_delete_not_in_with_empty_ids_is_noop():
    from src.infrastructure.database.repositories.github_pg_repo import GitHubRepository

    class BoomSession:
        async def execute(self, *args, **kwargs):
            raise AssertionError("no deberia consultar la DB")

        async def commit(self):
            raise AssertionError("no deberia commitear")

    repo = GitHubRepository(BoomSession())

    assert await repo.delete_repos_not_in([]) == 0


# --------------------------------------------------------------------------
# Papers
# --------------------------------------------------------------------------


def _papers_payload(**overrides):
    from src.application.dtos.paper_dto import PaperConfigUpdate

    values = {
        "keywords": ["agents", "reasoning", "llm"],
        "max_results": 50,
        "days_back": 7,
        "include_daily": True,
        "include_search": True,
    }
    values.update(overrides)
    return PaperConfigUpdate(**values)


@pytest.mark.asyncio
async def test_papers_keywords_change_clears_feed(monkeypatch):
    from src.core.entities.config import PaperConfig
    from src.presentation.routers import paper_router as router

    calls = {"cleared": 0}

    class FakeService:
        def __init__(self, db):
            self.db = db

        async def get_config(self):
            return PaperConfig(keywords=["agents", "reasoning", "llm"], days_back=7)

        async def update_config(self, config):
            return config

        async def clear_papers(self):
            calls["cleared"] += 1
            return 50

    monkeypatch.setattr(router, "PaperService", FakeService)

    saved = await router.update_papers_config(
        _papers_payload(keywords=["genomics"]), db=object()
    )

    assert calls["cleared"] == 1
    assert saved.keywords == ["genomics"]


@pytest.mark.asyncio
async def test_papers_toggling_search_clears_feed(monkeypatch):
    """Apagar la busqueda cambia QUE papers entran, asi que el feed se reinicia."""
    from src.core.entities.config import PaperConfig
    from src.presentation.routers import paper_router as router

    calls = {"cleared": 0}

    class FakeService:
        def __init__(self, db):
            self.db = db

        async def get_config(self):
            return PaperConfig(
                keywords=["agents", "reasoning", "llm"],
                days_back=7,
                include_daily=True,
                include_search=True,
            )

        async def update_config(self, config):
            return config

        async def clear_papers(self):
            calls["cleared"] += 1
            return 50

    monkeypatch.setattr(router, "PaperService", FakeService)

    await router.update_papers_config(_papers_payload(include_search=False), db=object())

    assert calls["cleared"] == 1


@pytest.mark.asyncio
async def test_papers_sync_prunes_papers_outside_current_search(monkeypatch):
    from src.application.services import paper_service
    from src.core.entities.config import PaperConfig

    calls = {"deleted": None}

    class FakeRepo:
        async def get_config(self):
            return PaperConfig(keywords=["genomics"])

        async def update_config(self, config):
            return config

        async def save_papers(self, papers):
            return len(papers)

        async def delete_papers_not_in(self, ids):
            calls["deleted"] = list(ids)
            return 4

    class FakeFetcher:
        async def sync_pipeline(self, config):
            return [
                SimpleNamespace(id="p1", source="daily"),
                SimpleNamespace(id="p2", source="search"),
            ]

    monkeypatch.setattr(paper_service, "HuggingFacePapersFetcher", FakeFetcher)

    service = paper_service.PaperService(session=object())
    service.repo = FakeRepo()

    await service.sync_papers()

    assert calls["deleted"] == ["p1", "p2"]
