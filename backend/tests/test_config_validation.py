"""Tests de la validacion de configuracion.

Cubre el bug donde `update_config` de Google News ponia `last_search_at = now()`
incondicionalmente, haciendo que guardar la configuracion pareciera una
sincronizacion (y retrasando el auto-sync).
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.core.entities.config import GitHubConfig, GoogleNewsConfig, YouTubeConfig
from src.core.use_cases.update_source_config import (
    YouTubeConfigError,
    config_to_dict,
    ensure_youtube_searchable,
    needs_initial_sync,
    validate_github_config,
    validate_google_news_config,
    validate_youtube_config,
)

NOW = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)

def test_validate_youtube_removes_duplicates_and_blanks():
    config = YouTubeConfig(keywords=["  ia  ", "IA", "", "  "], channel_ids=["", "@x"])
    validated = validate_youtube_config(config)
    assert validated.keywords == ["ia"]
    assert validated.channel_ids == ["@x"]

def test_validate_youtube_defaults_languages_when_empty():
    config = validate_youtube_config(YouTubeConfig(languages=[]))
    assert config.languages == ["es", "en"]

def test_validate_youtube_clamps_max_results():
    assert validate_youtube_config(YouTubeConfig(max_results=9999)).max_results == 100
    assert validate_youtube_config(YouTubeConfig(max_results=0)).max_results == 1

def test_validate_youtube_handles_none_max_results():
    config = YouTubeConfig()
    config.max_results = None  # type: ignore[assignment]
    assert validate_youtube_config(config).max_results == 5

def test_validate_youtube_clamps_days_back():
    assert validate_youtube_config(YouTubeConfig(days_back=9999)).days_back == 365
    assert validate_youtube_config(YouTubeConfig(days_back=0)).days_back == 1

def test_validate_youtube_defaults_days_back():
    config = YouTubeConfig()
    config.days_back = None  # type: ignore[assignment]
    assert validate_youtube_config(config).days_back == 2

def test_ensure_youtube_searchable_accepts_keywords_only():
    ensure_youtube_searchable(YouTubeConfig(keywords=["ia"], channel_ids=[]))

def test_ensure_youtube_searchable_accepts_channels_only():
    ensure_youtube_searchable(YouTubeConfig(keywords=[], channel_ids=["@midudev"]))

def test_ensure_youtube_searchable_rejects_empty_config():
    # Sin esto el pipeline no hacia ninguna peticion y devolvia un sync
    # 'exitoso' con 0 videos, que en la UI parece un fallo de YouTube.
    with pytest.raises(YouTubeConfigError):
        ensure_youtube_searchable(YouTubeConfig(keywords=[], channel_ids=[]))

def test_validate_news_derives_ceid_when_missing():
    config = validate_google_news_config(GoogleNewsConfig(hl="en-US", gl="US", ceid=""))
    assert config.ceid == "US:en-US"

def test_validate_news_rejects_invalid_when_value():
    config = validate_google_news_config(GoogleNewsConfig(when="cuando-sea"))
    assert config.when == "1d"

def test_validate_news_keeps_valid_when_value():
    assert validate_google_news_config(GoogleNewsConfig(when="7d")).when == "7d"

def test_validate_news_empty_query_falls_back_to_default():
    config = validate_google_news_config(GoogleNewsConfig(q="   "))
    assert config.q == "Inteligencia Artificial OR IA"

def test_validate_news_clamps_days_window():
    assert validate_google_news_config(GoogleNewsConfig(days_window=999)).days_window == 365
    assert validate_google_news_config(GoogleNewsConfig(days_window=-1)).days_window == 0

def test_validate_github_clamps_thresholds():
    config = validate_github_config(
        GitHubConfig(days_active=0, min_stars=-5, min_forks=10**9, max_results=500)
    )
    assert config.days_active == 1
    assert config.min_stars == 0
    assert config.min_forks == 1_000_000
    assert config.max_results == 100

def test_validate_github_cleans_lists():
    config = validate_github_config(
        GitHubConfig(keywords=["ai", "AI", " llm "], selected_languages=["Python", " python "])
    )
    assert config.keywords == ["ai", "llm"]
    assert config.selected_languages == ["Python"]

def test_needs_initial_sync_when_never_synced():
    assert needs_initial_sync(None, 60) is True

def test_needs_initial_sync_when_recent():
    # `now` real: con una fecha fija el test empezaria a fallar solo.
    assert needs_initial_sync(datetime.now(timezone.utc), 60) is False

def test_needs_initial_sync_when_stale():
    old = datetime.now(timezone.utc) - timedelta(minutes=120)
    assert needs_initial_sync(old, 60) is True

def test_needs_initial_sync_handles_naive_datetime():
    naive = (datetime.now(timezone.utc) - timedelta(hours=5)).replace(tzinfo=None)
    assert needs_initial_sync(naive, 60) is True

def test_config_to_dict():
    data = config_to_dict(YouTubeConfig(keywords=["ia"], max_results=7))
    assert data["keywords"] == ["ia"]
    assert data["max_results"] == 7
    assert "last_search_at" in data