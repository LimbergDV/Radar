"""Tests del caso de uso de GitHub y del cliente de transcripciones.

Regresion principal de la transcripcion: `youtube-transcript-api` 1.x elimino
`YouTubeTranscriptApi.get_transcript`, y el `except Exception` de antes lo
convertia silenciosamente en "Transcripcion no disponible" para todos los videos.
"""

from datetime import datetime, timezone

from src.core.entities.config import GitHubConfig
from src.core.use_cases import sync_github as uc
from src.infrastructure.external.youtube_api import fetch_transcript

NOW = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)

def test_build_search_query_includes_all_filters(sample_config_github):
    query = uc.build_search_query(sample_config_github, NOW)
    assert "openai OR claude" in query
    assert "stars:>=50" in query
    assert "forks:>=10" in query
    assert "language:python" in query
    assert "topic:ai" in query
    assert "pushed:>=" in query

def test_build_pushed_filter_uses_days_active(sample_config_github):
    sample_config_github.days_active = 3
    assert uc.build_pushed_filter(sample_config_github, NOW) == "pushed:>=2026-10-02"

def test_build_search_query_requires_license(sample_config_github):
    sample_config_github.require_license = True
    assert "license:*" in uc.build_search_query(sample_config_github, NOW)

def test_build_search_query_defaults_keywords():
    config = GitHubConfig(keywords=[])
    query = uc.build_search_query(config, NOW)
    assert "artificial intelligence" in query

def test_build_search_query_clamps_days_active():
    config = GitHubConfig(days_active=0)
    assert "pushed:>=" in uc.build_search_query(config, NOW)

def _repo(**overrides) -> dict:
    repo = {
        "id": 1,
        "name": "repo",
        "full_name": "user/repo",
        "html_url": "https://github.com/user/repo",
        "description": "desc",
        "stargazers_count": 100,
        "forks_count": 20,
        "open_issues_count": 5,
        "language": "Python",
        "topics": ["ai", "llm"],
        "license": {"spdx_id": "MIT"},
        "updated_at": "2026-10-05T10:00:00Z",
    }
    repo.update(overrides)
    return repo

def test_matches_filters_passes_valid_repo(sample_config_github):
    assert uc.matches_filters(_repo(), sample_config_github) is True

def test_matches_filters_rejects_low_stars(sample_config_github):
    assert uc.matches_filters(_repo(stargazers_count=10), sample_config_github) is False

def test_matches_filters_rejects_low_forks(sample_config_github):
    assert uc.matches_filters(_repo(forks_count=1), sample_config_github) is False

def test_matches_filters_requires_license(sample_config_github):
    sample_config_github.require_license = True
    assert uc.matches_filters(_repo(license=None), sample_config_github) is False

def test_matches_filters_accepts_repo_with_license(sample_config_github):
    sample_config_github.require_license = True
    assert uc.matches_filters(_repo(), sample_config_github) is True

def test_matches_filters_rejects_other_language(sample_config_github):
    assert uc.matches_filters(_repo(language="Ruby"), sample_config_github) is False

def test_matches_filters_allows_repo_without_language(sample_config_github):
    """GitHub no siempre devuelve language; no queremos perder el repo por eso."""
    assert uc.matches_filters(_repo(language=None), sample_config_github) is True

def test_matches_filters_rejects_missing_topic(sample_config_github):
    assert uc.matches_filters(_repo(topics=["web"]), sample_config_github) is False

def test_build_repo_maps_api_response():
    repo = uc.build_repo(_repo(), "Contenido del README", NOW)

    assert repo.id == 1
    assert repo.full_name == "user/repo"
    assert repo.license == "MIT"
    assert repo.topics == ["ai", "llm"]
    assert repo.readme == "Contenido del README"
    assert repo.updated_at == datetime(2026, 10, 5, 10, 0, tzinfo=timezone.utc)
    assert repo.synced_at == NOW

def test_build_repo_handles_null_description_and_license():
    repo = uc.build_repo(_repo(description=None, license=None), "", NOW)
    assert repo.description == ""
    assert repo.license is None

def test_build_repo_extracts_owner_avatar():
    repo = uc.build_repo(_repo(owner={"avatar_url": "https://avatars/x.png"}), "", NOW)
    assert repo.owner_avatar_url == "https://avatars/x.png"

def test_parse_iso_datetime_invalid_falls_back():
    assert uc.parse_iso_datetime("no-es-fecha") is not None

def test_rank_sorts_by_stars_and_limits():
    repos = [
        uc.build_repo(_repo(id=i, stargazers_count=stars), "", NOW)
        for i, stars in enumerate([10, 500, 100])
    ]
    ranked = uc.rank(repos, 2)
    assert [r.stargazers_count for r in ranked] == [500, 100]

def test_dedupe_keeps_first():
    repos = [uc.build_repo(_repo(id=1), "README", NOW), uc.build_repo(_repo(id=1), "otro", NOW)]
    deduped = uc.dedupe(repos)
    assert len(deduped) == 1
    assert deduped[0].readme == "README"

def test_fetch_transcript_uses_v1_api(monkeypatch):
    """Si el codigo volviera a get_transcript, este test lo detecta."""
    calls = {}

    class FakeSnippet:
        def __init__(self, text):
            self.text = text

    class FakeTranscript:
        snippets = [FakeSnippet("Hola"), FakeSnippet("mundo")]

    class FakeApi:
        def fetch(self, video_id, languages=("en",)):
            calls["video_id"] = video_id
            calls["languages"] = languages
            return FakeTranscript()

    import youtube_transcript_api

    monkeypatch.setattr(youtube_transcript_api, "YouTubeTranscriptApi", FakeApi)

    text, error = fetch_transcript("abc123", ["es", "en"])

    assert text == "Hola mundo"
    assert error is None
    assert calls["video_id"] == "abc123"
    assert calls["languages"] == ["es", "en"]

def test_fetch_transcript_reports_error_type(monkeypatch):
    """El motivo del fallo se reporta para poder diagnosticarlo en los logs."""

    class FakeApi:
        def fetch(self, video_id, languages=("en",)):
            raise RuntimeError("sin permisos")

    import youtube_transcript_api

    monkeypatch.setattr(youtube_transcript_api, "YouTubeTranscriptApi", FakeApi)

    text, error = fetch_transcript("abc123", ["es"])

    assert text == "Transcripción no disponible"
    assert error == "RuntimeError"

def test_fetch_transcript_handles_empty_transcript(monkeypatch):
    class FakeTranscript:
        snippets = []

    class FakeApi:
        def fetch(self, video_id, languages=("en",)):
            return FakeTranscript()

    import youtube_transcript_api

    monkeypatch.setattr(youtube_transcript_api, "YouTubeTranscriptApi", FakeApi)

    text, error = fetch_transcript("abc123", ["es"])
    assert text == "Transcripción no disponible"
    assert error == "vacia"