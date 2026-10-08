"""Discovery de noticias vía Bing News RSS + extracción del cuerpo.

Por qué Bing y no Google News: el enlace de Google es un token opaco y desde
2026 su RPC de resolución devuelve `null`, así que nunca se podía traer el
texto del artículo. Bing mete la URL real en el `url=` de un wrapper
`apiclick.aspx`, que se desempaqueta sin nada más; con eso el scraping con
trafilatura vuelve a funcionar y las noticias se leen en la UI.

El resto del pipeline (deduplicar, ventana de antigüedad, trafilatura) es el
mismo que ya usaba Google News: vive en `core` y no se toca.
"""

import asyncio
from datetime import datetime, timezone

import httpx

from src.core.entities.config import GoogleNewsConfig
from src.core.entities.google_news import GoogleNewsArticle
from src.core.logging_config import get_logger
from src.core.use_cases import sync_bing_news as bing_uc
from src.core.use_cases import sync_google_news as uc
from src.infrastructure.external.google_news_api import _extract_from_html

logger = get_logger(__name__)

BING_NEWS_RSS = "https://www.bing.com/news/search"
# trafilatura corre sincrono en threads; sin tope puede agotar el pool.
MAX_CONCURRENT_EXTRACTIONS = 8
RSS_TIMEOUT = 30.0
ARTICLE_TIMEOUT = 20.0
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


class BingNewsFetcher:
    """Cliente del RSS de Bing News + enriquecimiento por scraping."""

    def __init__(self, max_concurrency: int = MAX_CONCURRENT_EXTRACTIONS):
        self.base_url = BING_NEWS_RSS
        self._semaphore = asyncio.Semaphore(max(1, max_concurrency))

    async def _fetch_rss(self, query: bing_uc.BingQuery) -> list[tuple[dict, str]]:
        """Descarga un feed. Devuelve (entradas normalizadas, idioma)."""
        params = {"q": query.query, "format": "RSS", "setmkt": query.setmkt}
        if query.setlang:
            params["setlang"] = query.setlang
        # Sin esto Bing devuelve su propio orden (no por fecha) y una mezcla de
        # artículos de meses atrás: medido, sin este parametro el RSS traia 5
        # items y ninguno de las ultimas 24h. Con el, trae ~11 y todos
        # recientes. El recorte exacto lo hace despues `filter_by_window`.
        params["qft"] = 'sortbydate="1"'

        try:
            async with httpx.AsyncClient(
                timeout=RSS_TIMEOUT,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            ) as client:
                response = await client.get(self.base_url, params=params)
                if response.status_code != 200:
                    logger.warning(
                        "Bing News [%s] devolvio %s para '%s'",
                        query.setmkt, response.status_code, query.query,
                    )
                    return []

                feed = _parse_feed(response.text)
                normalized = [_normalize_entry(e) for e in feed.entries]
                normalized = [e for e in normalized if e][: query.limit]
                logger.info("Bing News [%s] '%s': %d entradas", query.setmkt, query.query, len(normalized))
                return [(entry, query.language) for entry in normalized]
        except httpx.HTTPError as exc:
            logger.warning("Error de red en Bing News [%s]: %s", query.setmkt, exc)
            return []

    async def _scrape_article(self, url: str) -> tuple[str | None, str | None]:
        """Descarga el HTML del medio y extrae texto + imagen."""
        try:
            async with httpx.AsyncClient(
                timeout=ARTICLE_TIMEOUT,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            ) as client:
                response = await client.get(url)
                if response.status_code != 200:
                    return None, None
                html = response.text
        except httpx.HTTPError as exc:
            logger.debug("Fallo al descargar %s: %s", url, exc)
            return None, None

        return await asyncio.to_thread(_extract_from_html, html)

    async def _enrich(self, article: GoogleNewsArticle) -> GoogleNewsArticle:
        """Raspia el cuerpo. Nunca lanza: si falla, se guarda igual sin texto."""
        async with self._semaphore:
            if not uc.should_fetch_content(article):
                return article

            content, image_url = await self._scrape_article(article.link)
            if content:
                article.content = content
                article.content_fetched = True
                if image_url:
                    article.image_url = image_url
            return article

    async def sync_pipeline(self, config: GoogleNewsConfig) -> list[GoogleNewsArticle]:
        """Pipeline completo: discovery -> dedup -> ventana -> extracción."""
        fetched_at = datetime.now(timezone.utc)
        queries = bing_uc.build_bing_queries(config)

        results = await asyncio.gather(*(self._fetch_rss(q) for q in queries))
        entries_with_lang = [pair for batch in results for pair in batch]
        if not entries_with_lang:
            logger.warning("Bing News no devolvio ninguna entrada")
            return []

        articles = [
            article
            for entry, language in entries_with_lang
            if (article := uc.build_article(entry, language, fetched_at)) is not None
        ]

        articles = uc.deduplicate(articles)
        articles = uc.filter_by_window(articles, config.days_window)
        articles = articles[: config.max_results]

        if not articles:
            logger.warning("Bing News: 0 articulos tras deduplicar y ventana de %sd", config.days_window)
            return articles

        logger.info(
            "Bing News: %d entradas -> %d articulos tras deduplicar y ventana de %sd",
            len(entries_with_lang), len(articles), config.days_window,
        )

        # Todos los enlaces de Bing ya son del medio, asi que aqui no hay que
        # resolver nada: solo extraer el texto.
        enriched = await asyncio.gather(*(self._enrich(a) for a in articles))

        with_content = sum(1 for a in enriched if a.content_fetched)
        logger.info("Bing News: %d/%d articulos con contenido extraido", with_content, len(enriched))
        return list(enriched)


def _normalize_entry(entry: dict) -> dict | None:
    """Desenvuelve el apiclick y deja el link apuntando al medio.

    También rellena `source` a partir del dominio: el RSS de Bing no lo da y
    `build_article` lo usa para mostrar el medio.
    """
    link = bing_uc.decode_publisher_url(entry.get("link") or "")
    if not link:
        return None

    normalized = dict(entry)
    normalized["link"] = link
    normalized["original_link"] = entry.get("link") or ""

    if not entry.get("source"):
        from urllib.parse import urlparse

        host = (urlparse(link).hostname or "").removeprefix("www.")
        normalized["source"] = {"title": host, "href": link if host else ""}

    return normalized


def _parse_feed(xml_text: str):
    """Parsea el XML del feed (en su propia función para poder testearla)."""
    import feedparser

    return feedparser.parse(xml_text)