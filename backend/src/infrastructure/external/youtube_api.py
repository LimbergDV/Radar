import asyncio
import httpx
import re
from datetime import datetime, timedelta, timezone
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter

from src.core.entities.youtube import YouTubeVideo
from src.core.entities.config import YouTubeConfig

# Regex para detectar caracteres no latinos (asiáticos, cirílicos, etc.)
FOREIGN_CHARS_REGEX = re.compile(r'[\u0900-\u097F\u0E00-\u0E7F\u3040-\u30FF\u3400-\u4DBF\u4E00-\u9FFF\uAC00-\uD7AF\u0400-\u04FF\u0600-\u06FF]')


class YouTubeFetcher:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Falta configurar YOUTUBE_API_KEY en el archivo .env")
        self.api_key = api_key
        self.base_url = "https://youtube.googleapis.com/youtube/v3"

    async def _resolve_channel_handles(self, channel_ids: list[str]) -> list[str]:
        """Fase 1: Convierte @handles a channelIds reales."""
        if not channel_ids:
            return []

        resolved = []
        async with httpx.AsyncClient() as client:
            for raw_id in channel_ids:
                if raw_id.startswith("@"):
                    handle = raw_id.replace("@", "")
                    try:
                        res = await client.get(
                            f"{self.base_url}/channels",
                            params={"part": "id", "forHandle": handle, "key": self.api_key}
                        )
                        data = res.json()
                        if data.get("items"):
                            resolved.append(data["items"][0]["id"])
                    except Exception as e:
                        print(f"Error resolviendo canal {handle}: {e}")
                else:
                    resolved.append(raw_id)
        return resolved

    async def _fetch_search_candidates(self, config: YouTubeConfig, channel_ids: list[str]) -> list[dict]:
        """Fase 2: Búsqueda concurrente (idiomas + canales)."""
        query = " | ".join(config.keywords) if config.keywords else ""
        query = f"{query} -shorts -#shorts" if query else "-shorts -#shorts"

        two_days_ago = (datetime.now(timezone.utc) - timedelta(days=2)).strftime('%Y-%m-%dT%H:%M:%SZ')
        
        async with httpx.AsyncClient() as client:
            tasks = []
            
            # 1. Búsqueda por canales específicos
            for cid in channel_ids:
                url = f"{self.base_url}/search"
                params = {
                    "part": "snippet", "type": "video", "maxResults": 50,
                    "order": "date", "publishedAfter": two_days_ago,
                    "channelId": cid, "key": self.api_key
                }
                tasks.append(client.get(url, params=params))

            # 2. Búsqueda global por idiomas (si hay keywords)
            if config.keywords:
                langs = config.languages if config.languages else ["any"]
                for lang in langs:
                    params = {
                        "part": "snippet", "q": query, "type": "video",
                        "maxResults": 50, "order": "date",
                        "key": self.api_key
                    }
                    if lang != "any":
                        params["relevanceLanguage"] = lang
                        if lang == "en": params["regionCode"] = "US"
                        if lang == "es": params["regionCode"] = "MX"
                    
                    tasks.append(client.get(f"{self.base_url}/search", params=params))

            # Ejecutar todas las peticiones al mismo tiempo
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            
        items = []
        seen_ids = set()
        
        for res in responses:
            if isinstance(res, Exception):
                print(f"Excepción en petición a YouTube: {res}")
                continue
            if res.status_code != 200:
                print(f"Error de YouTube API: {res.status_code} - {res.text}")
                continue
                
            data = res.json()
            # ¡ESTO ERA LO QUE FALTABA! 👇
            for item in data.get("items", []):
                vid = item.get("id", {}).get("videoId")
                if vid and vid not in seen_ids:
                    seen_ids.add(vid)
                    items.append(item)

        # Ordenar cronológicamente (más nuevo primero)
        items.sort(key=lambda x: x["snippet"]["publishedAt"], reverse=True)
        return items

    async def _enrich_videos_batch(self, items: list[dict]) -> list[dict]:
        """Fase 3: Obtener estadísticas y duración en batches de 50."""
        valid_items = [i for i in items if i.get("id", {}).get("videoId")]
        if not valid_items:
            return []

        enriched = []
        chunk_size = 50
        
        async with httpx.AsyncClient() as client:
            for i in range(0, len(valid_items), chunk_size):
                chunk = valid_items[i:i + chunk_size]
                video_ids = ",".join(item["id"]["videoId"] for item in chunk)
                
                res = await client.get(
                    f"{self.base_url}/videos",
                    params={
                        "part": "statistics,contentDetails,snippet",
                        "id": video_ids,
                        "key": self.api_key
                    }
                )
                if res.status_code == 200:
                    enriched.extend(res.json().get("items", []))
                    
        return enriched

    def _parse_duration(self, iso_duration: str) -> int:
        """Convierte PT15M33S a segundos."""
        if not iso_duration: return 0
        match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso_duration)
        if not match: return 0
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        return hours * 3600 + minutes * 60 + seconds

    async def _filter_and_transcribe(self, videos: list[dict], config: YouTubeConfig) -> list[YouTubeVideo]:
        """Fase 4: Filtrado estricto (Shorts, Idiomas) y Extracción de Transcripción."""
        final_videos = []
        pushed_per_channel = {}
        total_pushed = 0
        
        is_global = not config.channel_ids
        langs_to_try = config.languages if config.languages else ["es", "en"]
        
        # Como obtener transcripciones es bloqueante/lento (usa requests síncronos), lo corremos en un threadpool
        def fetch_transcript(video_id: str) -> str:
            try:
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=langs_to_try)
                return TextFormatter().format_transcript(transcript_list).replace('\n', ' ')
            except Exception:
                return "Transcripción no disponible"

        for item in videos:
            vid = item["id"]
            snippet = item.get("snippet", {})
            channel_id = snippet.get("channelId")
            
            # 1. Validar límite
            if is_global:
                if total_pushed >= config.max_results: break
            else:
                if pushed_per_channel.get(channel_id, 0) >= config.max_results: continue

            # 2. Filtro estricto de Idioma
            audio_lang = snippet.get("defaultAudioLanguage") or snippet.get("defaultLanguage")
            if audio_lang:
                if not any(lang.lower() in audio_lang.lower() for lang in langs_to_try):
                    continue
            else:
                if FOREIGN_CHARS_REGEX.search(snippet.get("title", "")):
                    continue

            # 3. Filtro de Shorts (< 2 min)
            duration_secs = self._parse_duration(item.get("contentDetails", {}).get("duration", ""))
            if duration_secs <= 120:
                continue

            # 4. Transcripción (No bloqueante usando run_in_executor)
            transcript = await asyncio.to_thread(fetch_transcript, vid)
            
            stats = item.get("statistics", {})
            
            final_videos.append(
                YouTubeVideo(
                    id=vid,
                    title=snippet.get("title", ""),
                    channel=snippet.get("channelTitle", ""),
                    channel_id=channel_id,
                    published_at=datetime.fromisoformat(snippet["publishedAt"].replace('Z', '+00:00')),
                    url=f"https://www.youtube.com/watch?v={vid}",
                    thumbnail_url=snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                    transcript=transcript,
                    views=int(stats.get("viewCount", 0)),
                    likes=int(stats.get("likeCount", 0)),
                    comments=int(stats.get("commentCount", 0)),
                    duration_seconds=duration_secs,
                    language=audio_lang or "unknown",
                    synced_at=datetime.now(timezone.utc)
                )
            )
            
            pushed_per_channel[channel_id] = pushed_per_channel.get(channel_id, 0) + 1
            total_pushed += 1
            
        return final_videos

    async def sync_pipeline(self, config: YouTubeConfig) -> list[YouTubeVideo]:
        """Ejecuta el pipeline completo y retorna la lista de videos listos para guardar."""
        channel_ids = await self._resolve_channel_handles(config.channel_ids)
        search_items = await self._fetch_search_candidates(config, channel_ids)
        if not search_items:
            return []
            
        enriched_videos = await self._enrich_videos_batch(search_items)
        final_videos = await self._filter_and_transcribe(enriched_videos, config)
        
        return final_videos