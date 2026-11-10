"""Resolucion de la URL real de un articulo de Google News.

El RSS entrega links que no apuntan al medio, sino a un token opaco
(`news.google.com/rss/articles/CBMi...AU_yqL...`) que no redirige por HTTP: la
pagina es una app que lo resuelve en el cliente via RPC. A 2026-10 ese RPC
(`batchexecute`) devuelve `null` en todas sus variantes, asi que la decodificacion
no es fiable.

Probamos las dos tecnicas conocidas (payload base64 de los GUIDs antiguos, y el
RPC actual) por si Google revierte el bloqueo. Si ninguna funciona devolvemos
None y el pipeline guarda el link de Google, que abre en el navegador.
"""

import base64
import binascii
import json
import re

import httpx

from src.core.logging_config import get_logger

logger = get_logger(__name__)

_ARTICLE_PATH_RE = re.compile(r"news\.google\.com/(?:rss/)?articles/([^?&#]+)")
_SIG_RE = re.compile(r'data-n-a-sg="([^"]+)"')
_TS_RE = re.compile(r'data-n-a-ts="([^"]+)"')
_URL_IN_BYTES_RE = re.compile(rb"https?://[\x20-\x7e]{8,}")

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
_BATCHEXECUTE_URL = "https://news.google.com/_/DotsSplashUi/data/batchexecute"
_TIMEOUT = 15.0


def extract_token(google_news_url: str) -> str | None:
    """Saca el token del link de Google News."""
    match = _ARTICLE_PATH_RE.search(google_news_url or "")
    return match.group(1) if match else None


def _looks_like_real_url(candidate: str) -> bool:
    """Filtra el ruido del payload (logos de Google, etc.)."""
    if not candidate or "news.google." in candidate or "gstatic." in candidate:
        return False
    return candidate.startswith(("http://", "https://"))


def _decode_legacy_payload(token: str) -> str | None:
    """GUIDs antiguos: la URL real venia embebida en el payload base64."""
    try:
        raw = base64.urlsafe_b64decode(token + "===")
    except (binascii.Error, ValueError):
        return None

    for match in _URL_IN_BYTES_RE.findall(raw):
        candidate = match.decode("ascii", errors="ignore").rstrip("\x00")
        if _looks_like_real_url(candidate):
            return candidate.rstrip("/") if len(candidate) > 30 else candidate

    return None


def _decode_via_batchexecute(token: str) -> str | None:
    """RPC actual de Google: pide la URL real usando la firma de la pagina.

    Se abre su propio `httpx.Client` sincrono a proposito: esta funcion corre en
    un thread (`asyncio.to_thread`), asi que no puede usar el cliente asincrono
    que le pasa `resolve_real_url`. Antes se recibia ese cliente asincrono aqui y
    `page.status_code` reventaba con AttributeError sobre una corrutina, o sea
    que este decoder nunca funciono.
    """
    try:
        with httpx.Client(
            headers={"User-Agent": _USER_AGENT},
            timeout=_TIMEOUT,
            follow_redirects=True,
        ) as client:
            page = client.get(f"https://news.google.com/rss/articles/{token}")
            if page.status_code != 200:
                return None

            signature = _SIG_RE.search(page.text)
            timestamp = _TS_RE.search(page.text)
            if not signature or not timestamp:
                return None

            inner = json.dumps([
                "garturlreq",
                [
                    [
                        "X", "X", ["X"], None, None, 1, 1, "X", None, 1,
                        None, None, None, None, None, 0, None, None,
                        [int(timestamp.group(1)), signature.group(1)],
                    ],
                    "X", "X", 1, [1, 2, 3], 1, 0, "655000234", 0, 0, None, 0,
                ],
                token,
            ])
            payload = json.dumps([[["Fbv4je", inner, None, "generic"]]])

            response = client.post(
                _BATCHEXECUTE_URL,
                data={"f.req": payload},
                headers={
                    "content-type": "application/x-www-form-urlencoded;charset=UTF-8",
                    "referer": f"https://news.google.com/rss/articles/{token}",
                    "origin": "https://news.google.com",
                },
            )

        # La respuesta viene en marcos separados por doble salto de linea.
        for chunk in response.text.split("\n\n"):
            chunk = chunk.strip()
            if not chunk.startswith("[["):
                continue
            try:
                parsed = json.loads(chunk)
            except json.JSONDecodeError:
                continue
            for frame in parsed:
                if not (isinstance(frame, list) and len(frame) > 2):
                    continue
                if frame[0] == "wrb.fr" and isinstance(frame[2], str):
                    decoded = json.loads(frame[2])
                    url = decoded[1] if isinstance(decoded, list) and len(decoded) > 1 else None
                    if _looks_like_real_url(url or ""):
                        return url
        return None
    except (httpx.HTTPError, json.JSONDecodeError, ValueError, KeyError) as exc:
        logger.debug("batchexecute fallo para %s: %s", token[:16], exc)
        return None


async def resolve_real_url(
    google_news_url: str,
    client: httpx.AsyncClient | None = None,
) -> str | None:
    """Devuelve la URL real del medio, o None si no se pudo resolver.

    `client` se conserva por compatibilidad con los llamadores, pero no se usa:
    la decodificacion sync corre en su propio thread con su propio cliente.
    """
    del client  # kept for call-site compatibility
    token = extract_token(google_news_url)
    if not token:
        return google_news_url or None

    direct = _decode_legacy_payload(token)
    if direct:
        logger.debug("URL resuelta via payload legacy")
        return direct

    import asyncio

    resolved = await asyncio.to_thread(_decode_via_batchexecute, token)

    if resolved:
        logger.debug("URL resuelta via batchexecute")
    else:
        logger.debug("No se pudo resolver la URL; se conserva el link de Google News")

    return resolved