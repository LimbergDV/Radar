"""Casos de uso de Google News: construccion de queries, mapeo y deduplicado.

Todo lo de este modulo es *puro*: no toca red ni base de datos. Recibe datos
crudos (entradas de feedparser) y devuelve entidades de dominio. Asi la logica
de negocio se puede testear sin mocks de red.
"""

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from src.core.entities.config import GoogleNewsConfig
from src.core.entities.google_news import GoogleNewsArticle

# El link de Google es un token opaco de ~800 chars: no sirve como PK.
_ID_LENGTH = 40


def build_article_id(link: str) -> str:
    """Id deterministico y compacto a partir del link del articulo."""
    return hashlib.sha1(link.strip().encode("utf-8")).hexdigest()[:_ID_LENGTH]


@dataclass(frozen=True)
class RssQuery:
    """Una consulta al feed RSS de Google News, con su idioma."""

    query: str
    hl: str
    gl: str
    ceid: str
    language: str
    limit: int


def build_rss_queries(config: GoogleNewsConfig) -> list[RssQuery]:
    """Arma las consultas RSS a partir de la configuracion.

    Si el usuario configuro `hl`/`ceid` de un solo idioma se devuelve una unica
    consulta. Si `ceid` trae varios pares separados por coma (p.ej.
    "MX:es-419,US:en") se genera una consulta concurrente por cada par, que es lo
    que hacia el proyecto original (feed dual ES/EN).
    """
    query = config.q or ""
    if config.site:
        query += f" site:{config.site}"
    if config.intitle:
        query += f" intitle:{config.intitle}"
    if config.when:
        query += f" when:{config.when}"
    query = query.strip()

    ceids = [c.strip() for c in (config.ceid or "").split(",") if c.strip()]

    if len(ceids) > 1:
        queries: list[RssQuery] = []
        for ceid in ceids:
            gl, _, hl = ceid.partition(":")
            queries.append(
                RssQuery(
                    query=query,
                    hl=hl or config.hl,
                    gl=gl or config.gl,
                    ceid=ceid,
                    language=_language_from_ceid(ceid),
                    limit=max(1, config.max_results),
                )
            )
        return queries

    return [
        RssQuery(
            query=query,
            hl=config.hl,
            gl=config.gl,
            ceid=config.ceid,
            language=_language_from_ceid(config.ceid or config.hl),
            limit=max(1, config.max_results),
        )
    ]


def _language_from_ceid(ceid: str) -> str:
    """'MX:es-419' -> 'es'."""
    _, _, hl = ceid.partition(":")
    return (hl or ceid or "es").split("-")[0].lower() or "es"


def parse_pub_date(entry: dict, fallback: datetime) -> datetime:
    """Fecha de publicacion normalizada a UTC."""
    raw = entry.get("published") or entry.get("updated")
    if raw:
        try:
            parsed = parsedate_to_datetime(raw)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except (TypeError, ValueError):
            pass
    return fallback


def _source_of(entry: dict) -> tuple[str, str]:
    source = entry.get("source") or {}
    if isinstance(source, dict):
        return source.get("title", "") or "", source.get("href", "") or ""
    return "", ""


def normalize_text(value: str) -> str:
    """Minusculas sin acentos ni signos, para comparar titulos."""
    decomposed = unicodedata.normalize("NFKD", value or "")
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", stripped.lower()).strip()


def build_article(
    entry: dict,
    language: str,
    fetched_at: datetime,
    resolved_url: str | None = None,
    content: str | None = None,
    image_url: str | None = None,
) -> GoogleNewsArticle | None:
    """Convierte una entrada de feedparser en entidad de dominio.

    Devuelve None si la entrada no tiene link o titulo, porque no es
    persistible. `resolved_url` es la URL real del medio (cuando se pudo
    decodificar); si no, se conserva el link de Google News que funciona igual
    en el navegador.
    """
    link = entry.get("link")
    title = (entry.get("title") or "").strip()
    if not link or not title:
        return None

    source_name, source_url = _source_of(entry)

    return GoogleNewsArticle(
        id=build_article_id(link),
        title=title,
        link=resolved_url or link,
        pub_date=parse_pub_date(entry, fetched_at),
        source_name=source_name,
        source_url=source_url,
        language=language,
        fetched_at=fetched_at,
        image_url=image_url,
        content=content,
        original_link=link,
    )


def deduplicate(articles: list[GoogleNewsArticle]) -> list[GoogleNewsArticle]:
    """Deduplica por id y, cuando el feed dual trae el mismo titular en dos
    idiomas, tambien por titulo normalizado (quedandose con el primero)."""
    seen_ids: set[str] = set()
    seen_titles: set[str] = set()
    unique: list[GoogleNewsArticle] = []

    for article in articles:
        if article.id in seen_ids:
            continue
        norm_title = normalize_text(article.title)
        if norm_title and norm_title in seen_titles:
            continue
        seen_ids.add(article.id)
        if norm_title:
            seen_titles.add(norm_title)
        unique.append(article)

    return unique


def filter_by_window(articles: list[GoogleNewsArticle], days: int) -> list[GoogleNewsArticle]:
    """Deja solo lo publicado dentro de la ventana de `days` dias.

    Es el filtro "de ese dia" que pide el producto: descarta articles viejos que
    Google News sigue sirviendo en el feed.
    """
    if days <= 0:
        return articles

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return [a for a in articles if a.pub_date >= cutoff]


def should_fetch_content(article: GoogleNewsArticle) -> bool:
    """Solo intentamos scraping si de verdad tenemos la URL del medio.

    Los links de Google News son paginas splash que no contienen el articulo, asi
    que gastar trafilatura en ellas solo produce el logo de Google.
    """
    return bool(article.link) and "news.google.com" not in article.link