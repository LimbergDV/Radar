"""Transcripciones de YouTube vía RapidAPI: el plan B del pipeline.

`youtube-transcript-api` es gratis y cubre la mayoría, pero desde las IPs de
datacenter (Railway) YouTube responde `IpBlocked` y el video se queda sin
transcripción. Este cliente existe para ese caso concreto.

Lo importante es el coste: el plan free son ~100 peticiones al mes. Por eso
nada lo llama en bucle — el pipeline intenta primero la vía gratuita y solo cae
aquí cuando falla, y `_consume()` corta en seco al llegar al tope configurado.

La cuota real la manda el proveedor (`x-ratelimit-requests-remaining`), pero se
lleva además un contador local en memoria: si la app se reinicia, el header de
la siguiente respuesta vuelve a decir la verdad, así que el contador local nunca
puede autorizar más de lo que queda de verdad.
"""

import html
import re
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from src.core.logging_config import get_logger
from src.infrastructure.database.settings import settings

logger = get_logger(__name__)

TRANSCRIPT_PATH = "/api/transcript"

# Texto de relleno que se guarda cuando no hay transcripción. Se repite aquí en
# vez de importarlo de `youtube_api` para no crear un ciclo de imports.
NO_TRANSCRIPT = "Transcripción no disponible"


@dataclass
class _Budget:
    """Contador de peticiones del mes en curso.

    `remaining` es lo que dice el proveedor en el último header; `used` es lo
    que hemos gastado nosotros desde el arranque. Se usan los dos porque cubren
    casos distintos: `used` protege de un bucle accidental dentro del mismo
    proceso, `remaining` protege de gastar la cuota real aunque el proceso se
    haya reiniciado.
    """

    month: str = ""
    used: int = 0
    remaining: int | None = None
    limit: int | None = None


_budget = _Budget()


def _current_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _state() -> _Budget:
    """Devuelve el contador del mes actual, reiniciándolo si cambió el mes."""
    month = _current_month()
    if _budget.month != month:
        _budget.month = month
        _budget.used = 0
    return _budget


def _consume() -> bool:
    """Reserva una petición. False si no queda presupuesto."""
    state = _state()

    if state.used >= max(0, settings.rapidapi_transcript_budget):
        return False
    if state.remaining is not None and state.remaining <= 0:
        return False

    # Se incrementa ANTES de la llamada: una petición que falla en el proveedor
    # también consume cuota, así que contarla después permitiría pasarse.
    state.used += 1
    return True


def _read_quota(headers) -> None:
    """Aprende la cuota real del header. Silencioso si no viene."""
    state = _state()
    for field in ("x-ratelimit-requests-remaining", "x-ratelimit-requests-limit"):
        raw = headers.get(field)
        if raw is None:
            continue
        try:
            value = int(raw)
        except ValueError:
            continue
        if field.endswith("remaining"):
            state.remaining = value
        else:
            state.limit = value


def budget_status() -> dict:
    """Estado de la cuota, para `/api/youtube/transcripts/status`.

    `remaining` es lo que reporta el proveedor (None si aún no se ha llamado en
    este proceso) y `used_by_app` lo gastado por esta app en el mes.
    """
    state = _state()
    return {
        "enabled": bool(settings.rapidapi_key),
        "used_by_app": state.used,
        "app_budget": settings.rapidapi_transcript_budget,
        "remaining": state.remaining,
        "provider_limit": state.limit,
        "month": state.month,
    }


def _clean(raw: str) -> str:
    """Normaliza el texto: entidades HTML (`&gt;&gt;`) y espacios repetidos."""
    text = html.unescape(raw or "")
    return re.sub(r"\s+", " ", text).strip()


# Punto de inyección para los tests: en producción vale None y httpx usa su
# transporte real. Mismo patrón que el `transport` del cliente del MCP.
_transport: httpx.AsyncBaseTransport | None = None


def _build_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=settings.rapidapi_timeout, transport=_transport)



async def fetch_transcript(
    video_id: str,
    lang: str | None = None,
) -> tuple[str | None, str | None]:
    """Pide la transcripción a RapidAPI. Devuelve `(texto, motivo_del_fallo)`.

    `lang` NO es opcional en la práctica: sin él el proveedor devuelve la
    primera pista que encuentra y un video en español acabó llegando en árabe.
    Con `lang` pide esa pista concreta (o su traducción) y falla limpio si no
    existe, que es preferible a guardar texto en un idioma que nadie pidió.

    Nunca lanza: un fallo aquí no puede tumbar el sync entero. El motivo sale
    como string corto para que el log agregado del pipeline diga qué pasó.
    """
    api_key = settings.rapidapi_key.strip()
    if not api_key:
        return None, "sin_api_key"

    if not _consume():
        return None, "cuota_agotada"

    # `flat_text` devuelve el texto ya unido en vez del JSON por fragmentos:
    # mismo precio, menos payload, y no se guardan segmentos de todas formas.
    url = f"https://{settings.rapidapi_host}{TRANSCRIPT_PATH}"
    params = {"videoId": video_id, "flat_text": "true"}
    if lang:
        params["lang"] = lang

    headers = {
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": settings.rapidapi_host,
    }

    try:
        async with _build_client() as client:
            response = await client.get(url, params=params, headers=headers)
    except httpx.HTTPError as exc:
        return None, type(exc).__name__

    _read_quota(response.headers)

    if response.status_code == 429:
        logger.warning("RapidAPI: cuota agotada (429)")
        return None, "http_429"
    if response.status_code in (401, 403):
        logger.error("RapidAPI: credenciales rechazadas (%s)", response.status_code)
        return None, f"http_{response.status_code}"
    if response.status_code != 200:
        return None, f"http_{response.status_code}"

    try:
        payload = response.json()
    except ValueError:
        return None, "json_invalido"

    # La API responde 200 con `success: false` cuando el video no tiene
    # subtítulos: no es un error de red, simplemente no hay transcripción.
    if not payload.get("success"):
        return None, "sin_transcripcion"

    raw = payload.get("transcript")
    if isinstance(raw, list):
        # Por si la API ignora `flat_text` y devuelve los fragmentos.
        raw = " ".join(str(item.get("text", "")) for item in raw)

    text = _clean(str(raw or ""))
    return (text, None) if text else (None, "vacia")
