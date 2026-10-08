"""Casos de uso de GitHub: construccion de la query, filtros y mapeo.

De nuevo, modulo puro: recibe diccionarios de la API de GitHub y devuelve
entidades. Los filtros ("de ese dia, con al menos N stars, licencia, topics...")
viven aqui para poder testearlos sin pegarle a la red.
"""

from datetime import datetime, timedelta, timezone

from src.core.entities.config import GitHubConfig
from src.core.entities.github import GitHubRepo

_PUSHED_GREATER_EQUAL = "pushed:>="


def build_pushed_filter(config: GitHubConfig, now: datetime | None = None) -> str:
    """Fragmento de query con la ventana de actividad, p.ej. 'pushed:>=2026-10-04'."""
    days = max(1, config.days_active)
    reference = now or datetime.now(timezone.utc)
    return f"{_PUSHED_GREATER_EQUAL}{(reference - timedelta(days=days)).strftime('%Y-%m-%d')}"


def build_search_query(config: GitHubConfig, now: datetime | None = None) -> str:
    """Query completa para `GET /search/repositories`."""
    keywords = [k.strip() for k in (config.keywords or []) if k.strip()]
    terms = keywords or ["artificial intelligence"]
    query = " OR ".join(terms)

    qualifiers = [build_pushed_filter(config, now)]
    if config.min_stars > 0:
        qualifiers.append(f"stars:>={config.min_stars}")
    if config.min_forks > 0:
        qualifiers.append(f"forks:>={config.min_forks}")
    if config.require_license:
        qualifiers.append("license:*")
    if config.selected_languages:
        langs = "".join(f" language:{l.strip().lower()}" for l in config.selected_languages if l.strip())
        if langs:
            qualifiers.append(langs.strip())
    if config.selected_topics:
        topics = "".join(f" topic:{t.strip().lower()}" for t in config.selected_topics if t.strip())
        if topics:
            qualifiers.append(topics.strip())

    return f"{query} {' '.join(qualifiers)}"


def matches_filters(repo: dict, config: GitHubConfig) -> bool:
    """Verifica los criterios que GitHub no aplica (o no aplica bien) en la query.

    La busqueda de GitHub trata `stars:>=N` como OR cuando hay varios terms, asi
    que revalidamos en local para no guardar repos que no cumplen los filtros
    que el usuario configuro en la UI.
    """
    if config.min_stars > 0 and int(repo.get("stargazers_count") or 0) < config.min_stars:
        return False
    if config.min_forks > 0 and int(repo.get("forks_count") or 0) < config.min_forks:
        return False

    if config.require_license and not repo.get("license"):
        return False

    languages = {l.strip().lower() for l in (config.selected_languages or []) if l.strip()}
    if languages:
        repo_lang = (repo.get("language") or "").strip().lower()
        if repo_lang and repo_lang not in languages:
            return False

    topics = {t.strip().lower() for t in (config.selected_topics or []) if t.strip()}
    if topics:
        repo_topics = {t.lower() for t in (repo.get("topics") or [])}
        if not (repo_topics & topics):
            return False

    return True


def parse_iso_datetime(value: str | None) -> datetime:
    """Parsea el timestamp ISO-8601 de la API de GitHub (siempre UTC)."""
    if not value:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)


def build_repo(data: dict, readme: str = "", synced_at: datetime | None = None) -> GitHubRepo:
    """Mapea la respuesta de la API a entidad de dominio."""
    owner = data.get("owner") or {}
    return GitHubRepo(
        id=int(data["id"]),
        name=data.get("name", ""),
        full_name=data.get("full_name", ""),
        html_url=data.get("html_url", ""),
        description=data.get("description") or "",
        stargazers_count=int(data.get("stargazers_count") or 0),
        forks_count=int(data.get("forks_count") or 0),
        open_issues_count=int(data.get("open_issues_count") or 0),
        language=data.get("language") or "",
        license=(data.get("license") or {}).get("spdx_id") or None,
        topics=list(data.get("topics") or []),
        readme=readme or "",
        updated_at=parse_iso_datetime(data.get("updated_at")),
        synced_at=synced_at or datetime.now(timezone.utc),
        owner_avatar_url=owner.get("avatar_url") or None,
        watchers_count=int(data.get("watchers_count") or 0),
        homepage=data.get("homepage") or None,
        size_kb=int(data.get("size") or 0),
        default_branch=data.get("default_branch") or "main",
    )


def dedupe(repos: list[GitHubRepo]) -> list[GitHubRepo]:
    """Elimina duplicados por id conservando el primero (que trae el README)."""
    seen: set[int] = set()
    unique: list[GitHubRepo] = []
    for repo in repos:
        if repo.id in seen:
            continue
        seen.add(repo.id)
        unique.append(repo)
    return unique


def rank(repos: list[GitHubRepo], limit: int) -> list[GitHubRepo]:
    """Ordena por popularidad y recorta al maximo pedido."""
    ordered = sorted(repos, key=lambda r: (r.stargazers_count, r.forks_count), reverse=True)
    return ordered[:limit] if limit > 0 else ordered