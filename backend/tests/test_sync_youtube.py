"""Tests del caso de uso de YouTube.

Regresion principal: la duracion ISO y el filtro de idioma/Shorts, que antes
vivian dentro del fetcher sin test y de los que dependia que el feed no se
llenara de Shorts de 30 segundos.
"""

from datetime import datetime, timezone

import pytest

from src.core.entities.config import YouTubeConfig
from src.core.use_cases import sync_youtube as uc

NOW = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)

@pytest.mark.parametrize(
    ("iso", "expected"),
    [
        ("PT30S", 30),
        ("PT2M", 120),
        ("PT2M30S", 150),
        ("PT1H", 3600),
        ("PT1H2M3S", 3723),
        ("PT15M33S", 933),
        ("", 0),
        ("lixo", 0),
    ],
)
def test_parse_duration(iso, expected):
    assert uc.parse_duration(iso) == expected

def test_is_short_below_two_minutes():
    assert uc.is_short(119) is True

def test_is_short_at_exactly_two_minutes():
    """El corte del original era 'duracion <= 120 se descarta'."""
    assert uc.is_short(120) is True

def test_is_short_above_two_minutes():
    assert uc.is_short(121) is False

def test_matches_language_by_audio_language():
    snippet = {"defaultAudioLanguage": "es-419", "title": "Hola"}
    assert uc.matches_language(snippet, ["es", "en"]) is True

def test_matches_language_rejects_other_audio_language():
    snippet = {"defaultAudioLanguage": "ja", "title": "こんにちは"}
    assert uc.matches_language(snippet, ["es", "en"]) is False

def test_matches_language_rejects_foreign_script_in_title():
    """Si no declara idioma de audio, el titulo con kanji/cyrillico se descarta."""
    snippet = {"title": "اكتشاف كوكب جديد"}
    assert uc.matches_language(snippet, ["es"]) is False

def test_matches_language_accepts_latin_title():
    snippet = {"title": "Inteligencia artificial"}
    assert uc.matches_language(snippet, ["es", "en"]) is True

def test_matches_language_passes_when_no_data():
    snippet = {}
    assert uc.matches_language(snippet, ["es"]) is True

def test_matches_language_allows_everything_when_no_languages_configured():
    snippet = {"defaultAudioLanguage": "ja"}
    assert uc.matches_language(snippet, []) is True

def test_normalize_language():
    assert uc.normalize_language("es-419") == "es"
    assert uc.normalize_language("EN") == "en"
    assert uc.normalize_language("") == ""

def _item(duration: str, audio_lang: str | None = "es", title: str = "Video de IA") -> dict:
    snippet = {"title": title, "channelId": "UC123", "channelTitle": "Canal"}
    if audio_lang:
        snippet["defaultAudioLanguage"] = audio_lang
    return {"id": "abc", "snippet": snippet, "contentDetails": {"duration": duration}}

def test_passes_filters_keeps_normal_video():
    assert uc.passes_filters(_item("PT5M"), YouTubeConfig(languages=["es"])) is True

def test_passes_filters_drops_short():
    assert uc.passes_filters(_item("PT1M"), YouTubeConfig(languages=["es"])) is False

def test_passes_filters_drops_wrong_language():
    assert uc.passes_filters(_item("PT5M", audio_lang="de"), YouTubeConfig(languages=["es"])) is False

def test_select_with_limits_global_cap():
    """Sin channel_ids, max_results es el tope global."""
    items = [_item("PT5M") | {"id": f"v{i}"} for i in range(10)]
    for i, item in enumerate(items):
        item["snippet"]["channelId"] = f"UC{i}"

    config = YouTubeConfig(channel_ids=[], max_results=3)
    assert len(uc.select_with_limits(items, config)) == 3

def test_select_with_limits_per_channel_when_channels_configured():
    """Con channel_ids, max_results es el tope POR CANAL."""
    items = []
    for channel in ("UC1", "UC1", "UC1", "UC2", "UC2"):
        item = _item("PT5M")
        item["id"] = f"{channel}-{len(items)}"
        item["snippet"]["channelId"] = channel
        items.append(item)

    config = YouTubeConfig(channel_ids=["UC1", "UC2"], max_results=2)
    selected = uc.select_with_limits(items, config)

    assert len(selected) == 4
    per_channel = {}
    for item in selected:
        channel = item["snippet"]["channelId"]
        per_channel[channel] = per_channel.get(channel, 0) + 1
    assert per_channel == {"UC1": 2, "UC2": 2}

def _full_item() -> dict:
    return {
        "id": "Pui2K4LNwBM",
        "snippet": {
            "title": "Trump y la IA",
            "channelTitle": "Candres Peredo",
            "channelId": "UCjQglRblUgJa2jshLaQSIjA",
            "publishedAt": "2026-09-24T21:30:38Z",
            "defaultAudioLanguage": "es-419",
            "thumbnails": {
                "default": {"url": "http://low.jpg"},
                "medium": {"url": "http://medium.jpg"},
                "maxres": {"url": "http://max.jpg"},
            },
        },
        "statistics": {"viewCount": "2880", "likeCount": "194", "commentCount": "7"},
        "contentDetails": {"duration": "PT2M56S"},
    }

def test_build_video_maps_everything():
    video = uc.build_video(_full_item(), "transcripcion completa", NOW)

    assert video.id == "Pui2K4LNwBM"
    assert video.title == "Trump y la IA"
    assert video.channel == "Candres Peredo"
    assert video.views == 2880
    assert video.likes == 194
    assert video.comments == 7
    assert video.duration_seconds == 176
    assert video.transcript == "transcripcion completa"
    assert video.language == "es-419"
    assert video.url == "https://www.youtube.com/watch?v=Pui2K4LNwBM"
    assert video.synced_at == NOW

def test_build_video_prefers_maxres_thumbnail():
    video = uc.build_video(_full_item(), "")
    assert video.thumbnail_url == "http://max.jpg"

def test_build_video_falls_back_through_thumbnails():
    item = _full_item()
    del item["snippet"]["thumbnails"]["maxres"]
    del item["snippet"]["thumbnails"]["medium"]
    video = uc.build_video(item, "")
    assert video.thumbnail_url == "http://low.jpg"

def test_build_video_handles_missing_statistics():
    item = _full_item()
    del item["statistics"]
    video = uc.build_video(item, "")
    assert video.views == 0

def test_build_video_returns_none_without_published_at():
    item = _full_item()
    del item["snippet"]["publishedAt"]
    assert uc.build_video(item, "") is None

def test_build_video_returns_none_without_id():
    item = _full_item()
    del item["id"]
    assert uc.build_video(item, "") is None