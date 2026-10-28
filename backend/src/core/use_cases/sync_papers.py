"""Caso de uso de Hugging Face Papers: mapeo, deduplicación y frescura.

Módulo puro: recibe los diccionarios que devuelve la API de Hugging Face y
devuelve entidades. Todo lo que se puede testear sin red vive aquí (fechas,
autores, enlaces, filtros y orden), igual que en el resto de fuentes.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from src.core.entities.config import PaperConfig
from src.core.entities.paper import HuggingFacePaper

DEFAULT_KEYWORDS = ["agents", "reasoning", "llm"]
MAX_AUTHORS = 20
MAX_LINKED = 30
MAX_KEYWORDS = 30


def parse_datetime(value: Any, *, fallback: datetime | None = None) -> datetime | None:
    """Parsea los timestamps de HF (`2026-10-28T00:00:00.000Z` o fecha suelta)."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str) or not value.strip():
        return fallback

    raw = value.strip().replace("Z", "+00:00")
    try:
        moment = datetime.fromisoformat(raw)
    except ValueError:
        # La API a veces manda sólo la fecha (`2026-10-28`).
        try:
            moment = datetime.strptime(raw[:10], "%Y-%m-%d")
        except ValueError:
            return fallback

    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _as_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _clean_list(values: list[str] | None, *, limit: int) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values or []:
        item = (value or "").strip()
        if not item or item.lower() in seen:
            continue
        seen.add(item.lower())
        cleaned.append(item)
        if len(cleaned) >= limit:
            break
    return cleaned


def author_names(paper: dict) -> list[str]:
    """Nombres de autores, sin los objetos usuario que mete la API."""
    names: list[str] = []
    for author in paper.get("authors") or []:
        if isinstance(author, str):
            names.append(author)
            continue
        if not isinstance(author, dict):
            continue
        name = author.get("name") or (author.get("user") or {}).get("fullname")
        if name:
            names.append(str(name))
    return _clean_list(names, limit=MAX_AUTHORS)


def linked_ids(values: Any) -> list[str]:
    """Ids de modelos/datasets/spaces enlazados (`[{'id': '...'}]`)."""
    ids: list[str] = []
    for value in values or []:
        if isinstance(value, str):
            ids.append(value)
        elif isinstance(value, dict) and value.get("id"):
            ids.append(str(value["id"]))
    return _clean_list(ids, limit=MAX_LINKED)


def organization_name(paper: dict, entry: dict | None = None) -> str | None:
    """Nombre legible de la organización, si el paper tiene una."""
    for source in (paper.get("organization"), (entry or {}).get("organization")):
        if isinstance(source, str):
            return source.strip() or None
        if isinstance(source, dict):
            name = source.get("fullname") or source.get("name")
            if name:
                return str(name).strip() or None
    return None


def build_paper(
    entry: dict,
    *,
    source: str = "daily",
    synced_at: datetime | None = None,
) -> HuggingFacePaper:
    """Mapea una entrada de `/api/daily_papers` o `/api/papers/search`.

    Ambas envuelven los datos en `{"paper": {...}}`, pero el thumbnail y los
    comentarios viven fuera. Se acepta también el objeto plano para que el
    mapeo no dependa de esa envoltura.
    """
    paper = entry.get("paper") if isinstance(entry.get("paper"), dict) else entry
    paper_id = str(paper.get("id") or "").strip()
    if not paper_id:
        raise ValueError("Paper de Hugging Face sin id")

    now = synced_at or datetime.now(timezone.utc)
    published = parse_datetime(
        paper.get("publishedAt") or entry.get("publishedAt"), fallback=now
    ) or now

    return HuggingFacePaper(
        id=paper_id,
        title=(paper.get("title") or entry.get("title") or "").strip(),
        abstract=(paper.get("summary") or entry.get("summary") or "").strip(),
        published_at=published,
        submitted_on_daily_at=parse_datetime(paper.get("submittedOnDailyAt")),
        ai_summary=(paper.get("ai_summary") or "").strip(),
        ai_keywords=_clean_list(list(paper.get("ai_keywords") or []), limit=MAX_KEYWORDS),
        authors=author_names(paper),
        upvotes=_as_int(paper.get("upvotes")),
        comments=_as_int(entry.get("numComments") or paper.get("numComments")),
        thumbnail_url=(entry.get("thumbnail") or paper.get("thumbnail") or None),
        github_repo=(paper.get("githubRepo") or None),
        project_page=(paper.get("projectPage") or None),
        organization=organization_name(paper, entry),
        linked_models=linked_ids(paper.get("linkedModels")),
        linked_datasets=linked_ids(paper.get("linkedDatasets")),
        linked_spaces=linked_ids(paper.get("linkedSpaces")),
        hf_url=f"https://huggingface.co/papers/{paper_id}",
        arxiv_url=f"https://arxiv.org/abs/{paper_id}",
        pdf_url=f"https://arxiv.org/pdf/{paper_id}",
        source=source,
        synced_at=now,
    )


def _merge(existing: HuggingFacePaper, incoming: HuggingFacePaper) -> HuggingFacePaper:
    """Fusiona el mismo paper visto en daily y en búsqueda.

    Ninguna de las dos vistas trae todo: la búsqueda a veces omite el
    thumbnail y el daily a veces omite modelos enlazados. Se queda el valor más
    rico en cada campo en vez de descartar uno de los dos.
    """
    existing.abstract = max((existing.abstract, incoming.abstract), key=len)
    existing.ai_summary = max((existing.ai_summary, incoming.ai_summary), key=len)
    existing.thumbnail_url = existing.thumbnail_url or incoming.thumbnail_url
    existing.github_repo = existing.github_repo or incoming.github_repo
    existing.project_page = existing.project_page or incoming.project_page
    existing.organization = existing.organization or incoming.organization
    existing.ai_keywords = _clean_list(
        existing.ai_keywords + incoming.ai_keywords, limit=MAX_KEYWORDS
    )
    existing.authors = _clean_list(existing.authors + incoming.authors, limit=MAX_AUTHORS)
    existing.linked_models = _clean_list(
        existing.linked_models + incoming.linked_models, limit=MAX_LINKED
    )
    existing.linked_datasets = _clean_list(
        existing.linked_datasets + incoming.linked_datasets, limit=MAX_LINKED
    )
    existing.linked_spaces = _clean_list(
        existing.linked_spaces + incoming.linked_spaces, limit=MAX_LINKED
    )
    existing.upvotes = max(existing.upvotes, incoming.upvotes)
    existing.comments = max(existing.comments, incoming.comments)
    existing.submitted_on_daily_at = (
        existing.submitted_on_daily_at or incoming.submitted_on_daily_at
    )
    existing.published_at = min(existing.published_at, incoming.published_at)
    # El Daily Papers es curado: si apareció ahí, esa es la fuente que mostramos.
    if incoming.source == "daily":
        existing.source = "daily"
    return existing


def dedupe(papers: list[HuggingFacePaper]) -> list[HuggingFacePaper]:
    """Un paper por id, conservando todos los campos que traiga cada vista."""
    by_id: dict[str, HuggingFacePaper] = {}
    for paper in papers:
        current = by_id.get(paper.id)
        by_id[paper.id] = _merge(current, paper) if current else paper
    return list(by_id.values())


def within_days(
    papers: list[HuggingFacePaper],
    days_back: int,
    *,
    now: datetime | None = None,
) -> list[HuggingFacePaper]:
    """Sólo papers frescos según su fecha efectiva (daily o publicación)."""
    if days_back <= 0:
        return papers

    reference = now or datetime.now(timezone.utc)
    cutoff = reference - timedelta(days=days_back)
    kept: list[HuggingFacePaper] = []
    for paper in papers:
        moment = paper.effective_date
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        if moment >= cutoff:
            kept.append(paper)
    return kept


def rank(papers: list[HuggingFacePaper], limit: int) -> list[HuggingFacePaper]:
    """Los más votados primero; a igualdad, los más recientes."""
    ordered = sorted(
        papers,
        key=lambda p: (p.upvotes, p.effective_date.timestamp()),
        reverse=True,
    )
    return ordered[:limit] if limit > 0 else ordered


def build_search_terms(config: PaperConfig) -> list[str]:
    """Keywords limpias para `/api/papers/search`; defaults si no hay ninguna."""
    terms = _clean_list(config.keywords, limit=10)
    return terms or list(DEFAULT_KEYWORDS)
