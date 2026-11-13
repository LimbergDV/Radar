"""Cliente de la API pública de papers de Hugging Face.

Dos vías, ambas sin autenticación:

- `/api/daily_papers?date=YYYY-MM-DD`: feed curado del día.
- `/api/papers/search?q=...`: búsqueda por relevancia.

Ninguna entrega el PDF ni el texto completo, sólo abstract + AI summary +
metadatos, que es justo lo que Radar guarda y enlaza.
"""

from datetime import datetime, timedelta, timezone

import httpx

from src.core.entities.config import PaperConfig
from src.core.entities.paper import HuggingFacePaper
from src.core.logging_config import get_logger
from src.core.use_cases import sync_papers as uc

logger = get_logger(__name__)

BASE_URL = "https://huggingface.co"
REQUEST_TIMEOUT = 30.0
DAILY_PAGE_LIMIT = 100
SEARCH_PAGE_LIMIT = 30


class HuggingFacePapersFetcher:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url.rstrip("/")

    async def fetch_daily(
        self, client: httpx.AsyncClient, days_back: int
    ) -> tuple[list[dict], int, int]:
        """Entradas del Daily Papers para los últimos N días.

        Devuelve `(entradas, peticiones_ok, peticiones_fallidas)` para que el
        pipeline pueda distinguir "no hay papers" de "HF está caído".
        """
        today = datetime.now(timezone.utc).date()
        entries: list[dict] = []
        ok = failures = 0

        for offset in range(max(1, days_back)):
            day = (today - timedelta(days=offset)).isoformat()
            try:
                response = await client.get(
                    f"{self.base_url}/api/daily_papers",
                    params={"date": day, "limit": DAILY_PAGE_LIMIT},
                )
                if response.status_code != 200:
                    failures += 1
                    logger.warning(
                        "HF daily_papers %s devolvió %s", day, response.status_code
                    )
                    continue
                payload = response.json()
                if isinstance(payload, list):
                    entries.extend(payload)
                    ok += 1
            except (httpx.HTTPError, ValueError) as exc:
                failures += 1
                logger.warning("HF daily_papers %s falló: %s", day, exc)

        return entries, ok, failures

    async def fetch_search(
        self, client: httpx.AsyncClient, keywords: list[str], limit: int
    ) -> tuple[list[dict], int, int]:
        """Resultados de búsqueda por keyword (una petición por término)."""
        entries: list[dict] = []
        ok = failures = 0

        for term in keywords:
            try:
                response = await client.get(
                    f"{self.base_url}/api/papers/search",
                    params={"q": term, "limit": limit},
                )
                if response.status_code != 200:
                    failures += 1
                    logger.warning(
                        "HF papers/search %r devolvió %s", term, response.status_code
                    )
                    continue
                payload = response.json()
                if isinstance(payload, list):
                    entries.extend(payload)
                    ok += 1
            except (httpx.HTTPError, ValueError) as exc:
                failures += 1
                logger.warning("HF papers/search %r falló: %s", term, exc)

        return entries, ok, failures

    async def sync_pipeline(self, config: PaperConfig) -> list[HuggingFacePaper]:
        """Daily + búsqueda, deduplicado y recortado a la ventana configurada.

        Cuando las dos vías están activas se reserva la mitad del feed para la
        búsqueda por keywords. Sin eso, el Daily (curado y siempre sobre IA)
        acaparaba el ranking por votos y cambiar las keywords no tenía ningún
        efecto visible en el feed.
        """
        daily: list[HuggingFacePaper] = []
        search: list[HuggingFacePaper] = []
        ok = failures = 0

        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": "NewsRadar/1.0", "Accept": "application/json"},
            follow_redirects=True,
        ) as client:
            if config.include_daily:
                entries, daily_ok, daily_fail = await self.fetch_daily(
                    client, config.days_back
                )
                ok += daily_ok
                failures += daily_fail
                daily = uc.within_days(
                    uc.dedupe(self._map(entries, source="daily")), config.days_back
                )
                logger.info("HF Daily Papers: %d entradas", len(entries))

            if config.include_search:
                terms = uc.build_search_terms(config)
                limit = min(max(1, config.max_results), SEARCH_PAGE_LIMIT)
                entries, search_ok, search_fail = await self.fetch_search(
                    client, terms, limit
                )
                ok += search_ok
                failures += search_fail
                search = uc.within_days(
                    uc.dedupe(self._map(entries, source="search")), config.days_back
                )
                logger.info("HF papers/search %s: %d entradas", terms, len(entries))

        if ok == 0 and failures > 0:
            raise RuntimeError(
                "Hugging Face no respondió en ninguna de las peticiones "
                f"({failures} fallos). Revisa la conectividad del backend."
            )

        logger.info(
            "HF Papers: %d del daily y %d de la búsqueda, únicos y frescos",
            len(daily),
            len(search),
        )

        if config.include_daily and config.include_search:
            limit = max(1, config.max_results)
            # La búsqueda siempre tiene sitio: si no, el Daily la tapa.
            daily_slots = max(1, limit // 2)
            result = uc.dedupe(
                uc.rank(daily, daily_slots) + uc.rank(search, limit - daily_slots)
            )
            # Si una vía trajo menos de lo esperado, la otra completa el feed.
            if len(result) < limit:
                result = uc.dedupe(result + uc.rank(search, limit))
            if len(result) < limit:
                result = uc.dedupe(result + uc.rank(daily, limit))
            return result[:limit]

        only = daily if config.include_daily else search
        return uc.rank(only, config.max_results)

    @staticmethod
    def _map(entries: list[dict], *, source: str) -> list[HuggingFacePaper]:
        papers: list[HuggingFacePaper] = []
        for entry in entries:
            try:
                papers.append(uc.build_paper(entry, source=source))
            except (ValueError, TypeError, AttributeError) as exc:
                # Una entrada rara de HF no debe tumbar el sync completo.
                logger.debug("Entrada de paper ignorada: %s", exc)
        return papers
