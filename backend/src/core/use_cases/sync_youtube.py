"""Casos de uso de YouTube: duracion, filtro de idioma/Shorts y construccion del video.

La parte que antes vivia dentro de `youtube_api.py` y no era testeable. Aqui la
logica de negocio queda en `core`, y el fetcher solo se ocupa de la red.
"""

import re
from datetime import datetime, timezone

from src.core.entities.config import YouTubeConfig
from src.core.entities.youtube import YouTubeVideo

# Alfabetos no latinos: si el titulo los tiene y no hay idioma de audio,
# casi seguro no es español/ingles.
FOREIGN_CHARS_REGEX = re.compile(
    r'[\u0900-\u097F\u0E00-\u0E7F\u3040-\u30FF\u3400-\u4DBF\u4E00-\u9FFF'
    r'\uAC00-\uD7AF\u0400-\u04FF\u0600-\u06FF]'
)

MIN_DURATION_SECONDS = 120  # por debajo de esto es un Short
_DURATION_REGEX = re.compile(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?')


def parse_duration(iso_duration: str) -> int:
    """Convierte una duracion ISO-8601 de YouTube ('PT1H2M3S') a segundos."""
    if not iso_duration:
        return 0
    match = _DURATION_REGEX.match(iso_duration)
    if not match:
        return 0
    hours, minutes, seconds = (int(g or 0) for g in match.groups())
    return hours * 3600 + minutes * 60 + seconds


def normalize_language(code: str) -> str:
    """'es-419' / 'ES' -> 'es'."""
    return (code or "").strip().lower().split("-")[0]


def is_short(duration_seconds: int, minimum: int = MIN_DURATION_SECONDS) -> bool:
    """Los Shorts se descartan: duracion <= 120s, igual que el original."""
    return duration_seconds <= minimum


def matches_language(snippet: dict, languages: list[str]) -> bool:
    """El video debe estar en alguno de los idiomas configurados.

    Si YouTube declara el idioma de audio nos fiamos de el; si no, usamos el
    titulo como heuristica. Si el snippet no trae nada, lo dejamos pasar: es
    preferible un video valido sin confirmar a perder contenido.
    """
    if not languages:
        return True

    allowed = {normalize_language(lang) for lang in languages if lang.strip()}
    if not allowed:
        return True

    audio_lang = snippet.get("defaultAudioLanguage") or snippet.get("defaultLanguage")
    if audio_lang:
        return normalize_language(audio_lang) in allowed

    title = snippet.get("title") or ""
    if not title:
        return True

    if FOREIGN_CHARS_REGEX.search(title):
        return False

    lowered = title.lower()
    return any(lang in lowered for lang in allowed)


def video_channel_id(snippet: dict) -> str:
    return snippet.get("channelId", "") or ""


def passes_filters(item: dict, config: YouTubeConfig) -> bool:
    """Aplica idioma y duracion minima a un item ya enriquecido."""
    snippet = item.get("snippet", {})
    if not matches_language(snippet, config.languages):
        return False

    duration = parse_duration((item.get("contentDetails") or {}).get("duration", ""))
    return not is_short(duration)


def build_video(item: dict, transcript: str, synced_at: datetime | None = None) -> YouTubeVideo | None:
    """Mapea un item de `videos.list` a entidad de dominio."""
    snippet = item.get("snippet") or {}
    stats = item.get("statistics") or {}

    video_id = item.get("id")
    published_at = snippet.get("publishedAt")
    if not video_id or not published_at:
        return None

    try:
        published = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None

    thumbnails = snippet.get("thumbnails") or {}

    return YouTubeVideo(
        id=video_id,
        title=snippet.get("title", "") or "",
        channel=snippet.get("channelTitle", "") or "",
        channel_id=snippet.get("channelId", "") or "",
        published_at=published,
        url=f"https://www.youtube.com/watch?v={video_id}",
        # maxres > standard > high > medium > default
        thumbnail_url=(
            thumbnails.get("maxres", {}).get("url")
            or thumbnails.get("standard", {}).get("url")
            or thumbnails.get("high", {}).get("url")
            or thumbnails.get("medium", {}).get("url")
            or thumbnails.get("default", {}).get("url")
            or ""
        ),
        transcript=transcript or "",
        views=int(stats.get("viewCount", 0) or 0),
        likes=int(stats.get("likeCount", 0) or 0),
        comments=int(stats.get("commentCount", 0) or 0),
        duration_seconds=parse_duration((item.get("contentDetails") or {}).get("duration", "")),
        language=snippet.get("defaultAudioLanguage") or snippet.get("defaultLanguage") or "unknown",
        synced_at=synced_at or datetime.now(timezone.utc),
    )


def select_with_limits(
    items: list[dict],
    config: YouTubeConfig,
) -> list[dict]:
    """Aplica el limite de resultados con la semantica del proyecto original.

    - Sin `channel_ids`: `max_results` es el tope global.
    - Con `channel_ids`: `max_results` es el tope *por canal*.
    """
    is_global = not config.channel_ids
    per_channel: dict[str, int] = {}
    total = 0
    selected: list[dict] = []

    for item in items:
        channel_id = video_channel_id(item.get("snippet") or {})

        if is_global:
            if total >= config.max_results:
                break
        elif per_channel.get(channel_id, 0) >= config.max_results:
            continue

        selected.append(item)
        per_channel[channel_id] = per_channel.get(channel_id, 0) + 1
        total += 1

    return selected