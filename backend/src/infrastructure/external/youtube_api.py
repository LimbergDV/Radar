"""Pipeline de YouTube: resolver handles, buscar candidatos, enriquecer en lotes
de 50 y filtrar/transcribir.

Los criterios de filtrado viven en `core/use_cases/sync_youtube.py`; aqui solo
hay red.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import httpx

from src.core.entities.config import YouTubeConfig
from src.core.entities.youtube import YouTubeVideo
from src.core.logging_config import get_logger
from src.core.use_cases import sync_youtube as uc

logger = get_logger(__name__)

REQUEST_TIMEOUT = 30.0
# 50 de 100: deja margen al filtro de idioma/Shorts.
SEARCH_MAX_RESULTS = 50
ENRICH_BATCH_SIZE = 50
DAYS_BACK = 2
NO_TRANSCRIPT = "Transcripción no disponible"


class YouTubeFetcher:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Falta configurar YOUTUBE_API_KEY en el archivo .env")
        self.api_key = api_key
        self.base_url = "https://youtube.googleapis.com/youtube/v3"

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": "NewsRadar/1.0"},
        )

    async def _resolve_channel_handles(self, channel_ids: list[str]) -> list[str]:
        """Convierte @handles a channelIds reales, concurrente."""
        if not channel_ids:
            return []

        async with self._client() as client:
            async def resolve(raw_id: str) -> str | None:
                if not raw_id.startswith("@"):
                    return raw_id

                handle = raw_id.lstrip("@")
                try:
                    response = await client.get(
                        f"{self.base_url}/channels",
                        params={"part": "id", "forHandle": handle, "key": self.api_key},
                    )
                    if response.status_code != 200:
                        logger.warning("No se pudo resolver @%s: HTTP %s", handle, response.status_code)
                        return None
                    items = response.json().get("items", [])
                    if items:
                        return items[0]["id"]
                    logger.warning("El handle @%s no existe", handle)
                except httpx.HTTPError as exc:
                    logger.warning("Error resolviendo @%s: %s", handle, exc)
                return None

            resolved = await asyncio.gather(*(resolve(cid) for cid in channel_ids))

        return [cid for cid in resolved if cid]

    async def _fetch_search_candidates(
        self,
        config: YouTubeConfig,
        channel_ids: list[str],
    ) -> list[dict]:
        """Busqueda concurrente por canal y por keyword/idioma."""
        query = " | ".join(config.keywords) if config.keywords else ""
        query = f"{query} -shorts -#shorts" if query else "-shorts -#shorts"

        published_after = (
            datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

        requests_to_make: list[dict] = []

        for channel_id in channel_ids:
            requests_to_make.append({
                "part": "snippet",
                "type": "video",
                "maxResults": SEARCH_MAX_RESULTS,
                "order": "date",
                "publishedAfter": published_after,
                "channelId": channel_id,
            })

        if config.keywords:
            for language in (config.languages or ["any"]):
                params = {
                    "part": "snippet",
                    "q": query,
                    "type": "video",
                    "maxResults": SEARCH_MAX_RESULTS,
                    "order": "date",
                }
                if language != "any":
                    params["relevanceLanguage"] = language
                    params["regionCode"] = "US" if language == "en" else "MX"
                requests_to_make.append(params)

        if not requests_to_make:
            return []

        async with self._client() as client:
            responses = await asyncio.gather(
                *(client.get(f"{self.base_url}/search", params={**p, "key": self.api_key})
                  for p in requests_to_make),
                return_exceptions=True,
            )

        items: list[dict] = []
        seen_ids: set[str] = set()

        for response in responses:
            if isinstance(response, Exception):
                logger.warning("Excepcion en busqueda de YouTube: %s", response)
                continue
            if response.status_code != 200:
                logger.warning("YouTube API devolvio %s: %s", response.status_code, response.text[:200])
                continue

            for item in response.json().get("items", []):
                video_id = (item.get("id") or {}).get("videoId")
                if video_id and video_id not in seen_ids:
                    seen_ids.add(video_id)
                    items.append(item)

        items.sort(key=lambda x: (x.get("snippet") or {}).get("publishedAt", ""), reverse=True)
        logger.info("YouTube: %d candidatos unicos", len(items))
        return items

    async def _enrich_videos_batch(self, items: list[dict]) -> list[dict]:
        """Añade estadisticas y duracion con videos.list (max 50 ids por llamada)."""
        valid_items = [i for i in items if (i.get("id") or {}).get("videoId")]
        if not valid_items:
            return []

        enriched: list[dict] = []

        async with self._client() as client:
            for start in range(0, len(valid_items), ENRICH_BATCH_SIZE):
                chunk = valid_items[start:start + ENRICH_BATCH_SIZE]
                ids = ",".join(item["id"]["videoId"] for item in chunk)

                try:
                    response = await client.get(
                        f"{self.base_url}/videos",
                        params={
                            "part": "statistics,contentDetails,snippet",
                            "id": ids,
                            "key": self.api_key,
                        },
                    )
                except httpx.HTTPError as exc:
                    logger.warning("Error enriqueciendo lote: %s", exc)
                    continue

                if response.status_code == 200:
                    enriched.extend(response.json().get("items", []))
                else:
                    logger.warning("YouTube videos.list devolvio %s", response.status_code)

        logger.info("YouTube: %d videos enriquecidos", len(enriched))
        return enriched

    async def _filter_and_transcribe(
        self,
        videos: list[dict],
        config: YouTubeConfig,
    ) -> list[YouTubeVideo]:
        """Aplica filtros y obtiene la transcripcion de cada video."""
        candidates = [item for item in videos if uc.passes_filters(item, config)]

        if not candidates:
            return []

        selected = uc.select_with_limits(candidates, config)
        logger.info(
            "YouTube: %d pasan los filtros -> %d seleccionados (limite %d)",
            len(candidates),
            len(selected),
            config.max_results,
        )

        languages = config.languages or ["es", "en"]
        synced_at = datetime.now(timezone.utc)

        async def process(item: dict) -> tuple[YouTubeVideo | None, str | None]:
            video_id = item["id"]
            transcript, error = await asyncio.to_thread(fetch_transcript, video_id, languages)
            return uc.build_video(item, transcript, synced_at), error

        results = await asyncio.gather(*(process(item) for item in selected))

        videos = [video for video, _error in results if video is not None]
        self._log_transcript_summary([error for _video, error in results])

        return videos

    @staticmethod
    def _log_transcript_summary(errors: list[str | None]) -> None:
        """Reporta cuantas transcripciones se obtuvieron y por que fallaron.

        Sin esto el fallo se tragaba en silencio y parecia que los videos no
        tienen transcripcion, cuando lo habitual es que YouTube este limitando
        la IP (IpBlocked).
        """
        total = len(errors)
        if not total:
            return

        obtained = sum(1 for error in errors if error is None)
        if obtained == total:
            logger.info("Transcripciones: %d/%d obtenidas", obtained, total)
            return

        counts: dict[str, int] = {}
        for error in errors:
            if error:
                counts[error] = counts.get(error, 0) + 1

        detalle = ", ".join(f"{reason} x{n}" for reason, n in sorted(counts.items()))
        logger.warning(
            "Transcripciones: solo %d/%d obtenidas (%s). Si aparece IpBlocked, "
            "YouTube esta limitando esta IP; se reintentan en la proxima sincronizacion.",
            obtained,
            total,
            detalle,
        )


def fetch_transcript(video_id: str, languages: list[str]) -> tuple[str, str | None]:
    """Devuelve (texto, error); el texto es el placeholder si no se pudo obtener.

    OJO: en `youtube-transcript-api` 1.x el metodo de clase `get_transcript` ya
    no existe y la API es instancia + `.fetch(...)`. Antes se llamaba al viejo y
    un `except Exception` convertia el fallo en "no disponible" para todos los
    videos.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        fetched = YouTubeTranscriptApi().fetch(video_id, languages=languages)
        snippets = getattr(fetched, "snippets", None)
        if snippets is None:
            snippets = list(fetched)
        text = " ".join(snippet.text for snippet in snippets).strip()
        return (text, None) if text else (NO_TRANSCRIPT, "vacia")
    except Exception as exc:  # noqa: BLE001 - sin transcripcion no es un fallo del sync
        return NO_TRANSCRIPT, type(exc).__name__


async def sync_pipeline(config: YouTubeConfig, api_key: str) -> list[YouTubeVideo]:
    """Ejecuta el pipeline completo y devuelve los videos listos para guardar."""
    fetcher = YouTubeFetcher(api_key=api_key)

    channel_ids = await fetcher._resolve_channel_handles(config.channel_ids)
    search_items = await fetcher._fetch_search_candidates(config, channel_ids)
    if not search_items:
        logger.warning("YouTube no devolvio candidatos")
        return []

    enriched = await fetcher._enrich_videos_batch(search_items)
    return await fetcher._filter_and_transcribe(enriched, config)