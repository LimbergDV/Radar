"""Validacion y normalizacion de la configuracion de cada fuente.

Centraliza los limites (cuanto puede traer cada fuente, que valores son
sensatos) para que los services y los routers no repitan validacion.
"""

from dataclasses import fields

from src.core.entities.config import GitHubConfig, GoogleNewsConfig, YouTubeConfig

MAX_RESULTS_CEILING = 100
MIN_RESULTS_FLOOR = 1

VALID_WHEN_VALUES = {"1h", "1d", "7d", "1w", "1m", "1y", ""}


def _clean_list(values: list[str] | None, *, limit: int = 30) -> list[str]:
    """Quita vacios/duplicados y recorta, preservando el orden."""
    if not values:
        return []
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values:
        item = (value or "").strip()
        if not item or item.lower() in seen:
            continue
        seen.add(item.lower())
        cleaned.append(item)
        if len(cleaned) >= limit:
            break
    return cleaned


def _clamp(value: int | None, default: int, minimum: int, maximum: int) -> int:
    if value is None:
        return default
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


def validate_youtube_config(config: YouTubeConfig) -> YouTubeConfig:
    """Normaliza keywords, canales, idiomas y el limite de resultados."""
    config.keywords = _clean_list(config.keywords)
    config.channel_ids = _clean_list(config.channel_ids)
    config.languages = _clean_list(config.languages) or ["es", "en"]
    config.max_results = _clamp(config.max_results, 5, 1, MAX_RESULTS_CEILING)
    return config


def validate_google_news_config(config: GoogleNewsConfig) -> GoogleNewsConfig:
    """Normaliza la query RSS y valida los parametros de region/ventana."""
    config.q = (config.q or "").strip() or "Inteligencia Artificial OR IA"
    config.hl = (config.hl or "es-419").strip() or "es-419"
    config.gl = (config.gl or "MX").strip() or "MX"
    config.site = (config.site or "").strip()
    config.intitle = (config.intitle or "").strip()
    config.ceid = (config.ceid or "").strip() or f"{config.gl}:{config.hl}"

    when = (config.when or "").strip().lower()
    if when not in VALID_WHEN_VALUES:
        when = "1d"
    config.when = when

    config.max_results = _clamp(config.max_results, 50, 1, MAX_RESULTS_CEILING)
    config.days_window = _clamp(config.days_window, 1, 0, 365)
    return config


def validate_github_config(config: GitHubConfig) -> GitHubConfig:
    """Normaliza keywords, topics, lenguajes y umbrales de popularidad."""
    config.keywords = _clean_list(config.keywords)
    config.selected_topics = _clean_list(config.selected_topics)
    config.selected_languages = _clean_list(config.selected_languages)

    config.days_active = _clamp(config.days_active, 2, 1, 365)
    config.min_stars = _clamp(config.min_stars, 50, 0, 1_000_000)
    config.min_forks = _clamp(config.min_forks, 10, 0, 1_000_000)
    config.max_results = _clamp(config.max_results, 50, 1, MAX_RESULTS_CEILING)
    config.require_license = bool(config.require_license)
    return config


def needs_initial_sync(last_search_at, stale_after_minutes: int) -> bool:
    """¿Hace falta sincronizar?

    Replica el auto-sync del proyecto original: dispara si nunca se ha
    sincronizado, o si la ultima sync fue hace mas de N minutos.
    """
    if last_search_at is None:
        return True

    from datetime import datetime, timedelta, timezone

    if last_search_at.tzinfo is None:
        last_search_at = last_search_at.replace(tzinfo=timezone.utc)

    return last_search_at <= datetime.now(timezone.utc) - timedelta(minutes=stale_after_minutes)


def config_to_dict(config) -> dict:
    """Serializa cualquier config dataclass a dict (para respuestas y logs)."""
    return {f.name: getattr(config, f.name) for f in fields(config)}