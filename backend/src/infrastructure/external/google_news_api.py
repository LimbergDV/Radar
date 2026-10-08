"""Pipeline de Google News.

Se arman las consultas RSS (feed dual ES/EN si el `ceid` trae varios pares de
region/idioma), se descargan en paralelo y se deduplican. El cuerpo con
trafilatura se extrae solo de los articulos cuya URL real se pudo resolver: los
links de Google son paginas splash y rasparlas devuelve el logo de Google.
"""

import asyncio
from datetime import datetime, timezone

import httpx
import trafilatura

from src.core.entities.config import GoogleNewsConfig
from src.core.entities.google_news import GoogleNewsArticle
from src.core.logging_config import get_logger
from src.core.use_cases import sync_google_news as uc
from src.infrastructure.external.google_news_url import resolve_real_url

logger = get_logger(__name__)

# Limite porque trafilatura corre sincrono en threads y podria agotar el pool.
MAX_CONCURRENT_EXTRACTIONS = 8
RSS_TIMEOUT = 30.0
ARTICLE_TIMEOUT = 20.0


class GoogleNewsFetcher:
    """Cliente del RSS de Google News + enriquecimiento por scraping."""

    def __init__(self, max_concurrency: int = MAX_CONCURRENT_EXTRACTIONS):
        self.base_url = "https://news.google.com/rss/search"
        self._semaphore = asyncio.Semaphore(max(1, max_concurrency))

    async def _fetch_rss(self, query: uc.RssQuery) -> list[tuple[dict, str]]:
        """Descarga un feed RSS. Devuelve (entradas, idioma) de ese feed."""
        params = {"q": query.query, "hl": query.hl, "gl": query.gl, "ceid": query.ceid}

        try:
            async with httpx.AsyncClient(
                timeout=RSS_TIMEOUT,
                follow_redirects=True,
                headers={"User-Agent": "NewsRadar/1.0"},
            ) as client:
                response = await client.get(self.base_url, params=params)
                if response.status_code != 200:
                    logger.warning("RSS Google News %s devolvio %s", query.ceid, response.status_code)
                    return []

                feed = _parse_feed(response.text)
                entries = feed.entries[: query.limit]
                logger.info("RSS %s: %d entradas", query.ceid, len(entries))
                return [(entry, query.language) for entry in entries]
        except httpx.HTTPError as exc:
            logger.warning("Error de red en RSS %s: %s", query.ceid, exc)
            return []

    async def _resolve_and_extract(
        self,
        article: GoogleNewsArticle,
        client: httpx.AsyncClient,
    ) -> GoogleNewsArticle:
        """Intenta obtener la URL real y el cuerpo del articulo.

        Nunca lanza: si algo falla devuelve el articulo tal cual, porque un
        enrichment fallido no debe impedir guardar la noticia.
        """
        async with self._semaphore:
            resolved_url = None
            try:
                resolved_url = await resolve_real_url(article.original_link or article.link, client)
            except Exception as exc:  # noqa: BLE001 - enrichment es best-effort
                logger.debug("No se pudo resolver URL de %s: %s", article.id, exc)

            if not resolved_url:
                return article

            content, image_url = await self._scrape_article(resolved_url)

            article.link = resolved_url
            article.content = content
            article.image_url = image_url
            article.content_fetched = bool(content)
            return article

    async def _scrape_article(self, url: str) -> tuple[str | None, str | None]:
        """Descarga el HTML y extrae texto + imagen con trafilatura."""
        try:
            async with httpx.AsyncClient(
                timeout=ARTICLE_TIMEOUT,
                follow_redirects=True,
                headers={"User-Agent": "NewsRadar/1.0"},
            ) as client:
                response = await client.get(url)
                if response.status_code != 200:
                    return None, None
                html = response.text
        except httpx.HTTPError as exc:
            logger.debug("Fallo al descargar %s: %s", url, exc)
            return None, None

        return await asyncio.to_thread(_extract_from_html, html)

    async def sync_pipeline(self, config: GoogleNewsConfig) -> list[GoogleNewsArticle]:
        """Ejecuta el pipeline completo y devuelve los articulos listos para guardar."""
        fetched_at = datetime.now(timezone.utc)
        queries = uc.build_rss_queries(config)

        results = await asyncio.gather(*(self._fetch_rss(q) for q in queries))
        entries_with_lang = [pair for batch in results for pair in batch]
        if not entries_with_lang:
            logger.warning("Google News no devolvio ninguna entrada")
            return []

        articles = [
            article
            for entry, language in entries_with_lang
            if (article := uc.build_article(entry, language, fetched_at)) is not None
        ]

        articles = uc.deduplicate(articles)
        articles = uc.filter_by_window(articles, config.days_window)
        articles = articles[: config.max_results]

        logger.info(
            "Google News: %d entradas -> %d articulos unicos tras deduplicar y ventana de %sd",
            len(entries_with_lang),
            len(articles),
            config.days_window,
        )

        # Solo se raspa lo que tiene URL real: las paginas splash de Google
        # no contienen el articulo.
        candidates = [a for a in articles if uc.should_fetch_content(a)]
        if candidates:
            logger.info("Intentando resolver URL de %d articulos", len(candidates))
            shared_client = httpx.AsyncClient(
                timeout=ARTICLE_TIMEOUT,
                follow_redirects=True,
                headers={"User-Agent": "NewsRadar/1.0"},
            )
            try:
                enriched = await asyncio.gather(
                    *(self._resolve_and_extract(a, shared_client) for a in candidates)
                )
            finally:
                await shared_client.aclose()

            by_id = {a.id: a for a in enriched}
            articles = [by_id.get(a.id, a) for a in articles]

        resolved = sum(1 for a in articles if a.content_fetched)
        logger.info("Google News: %d/%d articulos con contenido extraido", resolved, len(articles))
        return articles


def _parse_feed(xml_text: str):
    """Parsea el XML del feed (envuelto en su propia funcion para testearlo)."""
    import feedparser

    return feedparser.parse(xml_text)


def _extract_from_html(html: str) -> tuple[str | None, str | None]:
    """Extraccion sincrona (se ejecuta en un thread) del cuerpo y la imagen."""
    try:
        content = trafilatura.extract(html) or None
        metadata = trafilatura.extract_metadata(html)
        image = getattr(metadata, "image", None) if metadata else None
        return content, image
    except Exception as exc:  # noqa: BLE001 - trafilatura puede fallar con HTML raro
        logger.debug("trafilatura fallo: %s", exc)
        return None, None