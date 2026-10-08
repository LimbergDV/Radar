"""Casos de uso del discovery de noticias vía Bing News RSS.

Por qué existe esto: el RSS de Google News entrega un enlace opaco
(`news.google.com/rss/articles/CBMi...`) que no apunta al medio. Desde 2026 la
RPC `batchexecute` que lo desencriptaba devuelve `null`, así que la URL real es
irrecuperable y el articulo se guardaba sin cuerpo: título y medio sí, texto no.

Bing News RSS publica el enlace real dentro del `url=` de un wrapper
`apiclick.aspx`, que es trivial de desempaquetar. Trae menos resultados por
consulta que Google, pero son enlaces reales y por tanto el pipeline de
extracción con trafilatura (que ya existía y funcionaba) vuelve a tener entrada.

Este modulo es *puro*: no toca red. Solo arma consultas y normaliza enlaces.
"""

import re
from dataclasses import dataclass

from src.core.entities.config import GoogleNewsConfig

# El wrapper de Bing del que sacamos la URL del medio.
_APPCLICK_MARKER = "bing.com/news/apiclick.aspx"
# "Inteligencia Artificial OR IA" son dos consultas, no una con operador OR:
# Bing (igual que YouTube antes) trata el OR como texto y devuelve basura.
_OR_SPLIT = re.compile(r"\s+OR\s+", re.IGNORECASE)
_MAX_TERMS = 8


@dataclass(frozen=True)
class BingQuery:
    """Una consulta al RSS de Bing News, con su mercado."""

    query: str
    setmkt: str
    setlang: str
    language: str
    limit: int


def split_query_terms(query: str) -> list[str]:
    """'Inteligencia Artificial OR IA' -> ['Inteligencia Artificial', 'IA'].

    Se hace una peticion por termino porque un OR de Bing no filtra: devuelve
    de todo. Sin esto, una sola consulta con OR baja el pool de resultados.
    """
    parts = [p.strip() for p in _OR_SPLIT.split(query or "")]
    seen: set[str] = set()
    terms: list[str] = []
    for part in parts:
        key = part.lower()
        if part and key not in seen:
            seen.add(key)
            terms.append(part)
        if len(terms) >= _MAX_TERMS:
            break
    return terms


def build_bing_queries(config: GoogleNewsConfig) -> list[BingQuery]:
    """Una consulta por (termino x mercado).

    Los mercados salen de `ceid` con varios pares separados por coma
    ("MX:es-419,US:en"), igual que hacia el feed dual de Google News.
    """
    base = (config.q or "").strip()
    if config.site:
        base = f"{base} site:{config.site}".strip()
    if config.intitle:
        base = f"{base} intitle:{config.intitle}".strip()

    terms = split_query_terms(base)
    if not terms:
        terms = [""]

    markets = _markets_from_ceid(config.ceid, config.gl, config.hl)
    limit = max(1, config.max_results)

    return [
        BingQuery(
            query=term,
            setmkt=setmkt,
            setlang=setlang,
            language=language,
            limit=limit,
        )
        for term in terms
        for setmkt, setlang, language in markets
    ]


def _markets_from_ceid(ceid: str, gl: str, hl: str) -> list[tuple[str, str, str]]:
    """'MX:es-419,US:en' -> [('es-MX','es','es'), ('en-US','en','en')].

    Bing usa `setmkt` de tipo 'es-MX' (idioma-PAIS), no el 'es-419' de Google.
    """
    pairs = [c.strip() for c in (ceid or "").split(",") if c.strip()]

    markets: list[tuple[str, str, str]] = []
    seen: set[str] = set()

    for pair in pairs or [f"{gl or 'MX'}:{hl or 'es'}"]:
        country, _, lang = pair.partition(":")
        lang = (lang or hl or "es").split("-")[0].lower()
        country = (country or gl or "MX").upper()
        setmkt = f"{lang}-{country}"

        if setmkt in seen:
            continue
        seen.add(setmkt)
        markets.append((setmkt, lang, lang))

    return markets or [("es-MX", "es", "es")]


def decode_publisher_url(link: str) -> str:
    """Saca la URL real del medio del wrapper `apiclick.aspx` de Bing.

    Si no es un wrapper, devuelve el enlace tal cual. Nunca lanza: un link
    raro no debe tumbar la sincronizacion.
    """
    if not link:
        return ""

    if _APPCLICK_MARKER not in link:
        return link.strip()

    from urllib.parse import parse_qs, unquote, urlparse

    try:
        query = parse_qs(urlparse(link).query)
    except ValueError:
        return link.strip()

    candidates = query.get("url") or []
    for candidate in candidates:
        real = unquote(candidate).strip()
        if real.startswith(("http://", "https://")) and "bing.com" not in real:
            return real

    return link.strip()


def has_real_publisher_link(link: str) -> bool:
    """¿El enlace ya apunta al medio (o al menos no al wrapper de Bing)?"""
    return bool(link) and _APPCLICK_MARKER not in link