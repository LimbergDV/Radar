import asyncio
import httpx
import feedparser
import trafilatura
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from src.core.entities.google_news import GoogleNewsArticle
from src.core.entities.config import GoogleNewsConfig


class GoogleNewsFetcher:
    def __init__(self):
        self.base_url = "https://news.google.com/rss/search"

    async def _fetch_rss(self, query: str, config: GoogleNewsConfig) -> list:
        params = {
            "q": query,
            "hl": config.hl,
            "gl": config.gl,
            "ceid": config.ceid
        }
        
        async with httpx.AsyncClient(follow_redirects=True) as client:
            try:
                res = await client.get(self.base_url, params=params)
                if res.status_code != 200:
                    print(f"Error RSS Google News: {res.status_code}")
                    return []
                    
                feed = feedparser.parse(res.text)
                return feed.entries[:config.max_results]
            except Exception as e:
                print(f"Excepción en RSS: {e}")
                return []

    async def _extract_content(self, url: str) -> tuple[str | None, str | None]:
        """Extrae el contenido limpio y la imagen principal de la noticia usando Trafilatura."""
        try:
            # Trafilatura es síncrono, lo corremos en un thread para no bloquear
            def fetch_and_extract():
                downloaded = trafilatura.fetch_url(url)
                if not downloaded:
                    return None, None
                
                # Extraer texto limpio
                content = trafilatura.extract(downloaded)
                # Extraer metadata (incluye la imagen)
                metadata = trafilatura.extract_metadata(downloaded)
                image_url = metadata.image if metadata else None
                
                return content, image_url
                
            return await asyncio.to_thread(fetch_and_extract)
        except Exception:
            return None, None

    async def sync_pipeline(self, config: GoogleNewsConfig) -> list[GoogleNewsArticle]:
        # Armar el query final
        query = config.q
        if config.site: query += f" site:{config.site}"
        if config.intitle: query += f" intitle:{config.intitle}"
        if config.when: query += f" when:{config.when}"

        # 1. Traer el feed RSS
        entries = await self._fetch_rss(query, config)
        if not entries:
            return []

        articles = []
        fetched_at = datetime.now(timezone.utc)

        # 2. Extraer contenido de cada artículo de forma concurrente
        async def process_entry(entry) -> GoogleNewsArticle | None:
            # Parsear la fecha del RSS
            try:
                pub_date = parsedate_to_datetime(entry.published)
            except Exception:
                pub_date = fetched_at
                
            guid = entry.get("id", entry.get("link", ""))
            source_name = entry.get("source", {}).get("title", "")
            
            # Extraer contenido real
            content, image_url = await self._extract_content(entry.link)
            
            return GoogleNewsArticle(
                id=guid,
                title=entry.title,
                link=entry.link,
                pub_date=pub_date,
                source_name=source_name,
                source_url=entry.get("source", {}).get("href", ""),
                language="es",
                fetched_at=fetched_at,
                image_url=image_url,
                content=content
            )

        tasks = [process_entry(entry) for entry in entries]
        results = await asyncio.gather(*tasks)
        
        # Filtrar nulos
        articles = [a for a in results if a is not None]
        
        return articles