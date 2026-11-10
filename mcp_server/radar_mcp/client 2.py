"""Cliente HTTP contra la API de Radar.

Un solo lugar donde se habla con la API, para que:
- la key nunca se imprima en un error,
- los errores del backend (que vienen en `detail`) lleguen al agente con texto
  legible en vez de una traza,
- y sea trivial de mockear en los tests.
"""

from typing import Any

import httpx

from .config import Settings, settings as default_settings

# Errores que el backend ya sabe explicar. Si aparecen sin texto útil, el
# agente no puede hacer nada con un "502".
_HINTS = {
    401: "La API pide autenticación. Configura RADAR_API_KEY.",
    403: "Sin permisos para esta operación (scope insuficiente?).",
    404: "No existe ese recurso en la base de Radar.",
    422: "Los parámetros no son válidos para este endpoint.",
    429: "Cuota de la API de YouTube agotada o demasiadas peticiones.",
    502: "El backend no pudo con la fuente externa (YouTube/Bing/Google caída o limitado).",
}


class RadarError(RuntimeError):
    """Fallo hablando con Radar. El texto va dirigido al agente."""

    def __init__(self, message: str, *, status: int | None = None, detail: Any = None):
        super().__init__(message)
        self.status = status
        self.detail = detail

    def as_dict(self) -> dict:
        return {"error": str(self), "status": self.status, "detail": self.detail}


class RadarClient:
    """Cliente asíncrono y stateless (abre conexión por petición).

    Se abre por petición a propósito: el servidor MCP se lanza, se usan unas
    pocas llamadas y se muere. Reutilizar un pool exigiría gestionar su
    cierre y no aporta nada a esta escala.
    """

    def __init__(self, settings: Settings | None = None, transport: Any = None):
        self.settings = settings or default_settings
        # `transport` permite inyectar httpx.MockTransport en los tests.
        self._transport = transport

    def _headers(self) -> dict[str, str]:
        headers = {"User-Agent": "radar-mcp/1.0", "Accept": "application/json"}
        if self.settings.api_key:
            headers["X-API-Key"] = self.settings.api_key
        return headers

    async def get_json(self, path: str, params: dict | None = None) -> Any:
        url = f"{self.settings.api_url}{path}"
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.timeout,
                headers=self._headers(),
                transport=self._transport,
            ) as client:
                response = await client.get(url, params=params)
        except httpx.TimeoutException as exc:
            raise RadarError(
                f"Radar no respondió en {self.settings.timeout}s ({url}). "
                "¿Está desplegado el backend?"
            ) from exc
        except httpx.HTTPError as exc:
            raise RadarError(f"No se pudo contactar con Radar ({url}): {exc}") from exc

        if response.status_code == 200:
            return response.json()

        raise RadarError(
            self._explain(response),
            status=response.status_code,
            detail=_extract_detail(response),
        )

    async def post_json(self, path: str, params: dict | None = None) -> Any:
        """POST sin cuerpo. Solo lo usan los endpoints de sincronización."""
        url = f"{self.settings.api_url}{path}"
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.timeout,
                headers=self._headers(),
                transport=self._transport,
            ) as client:
                response = await client.post(url)
        except httpx.TimeoutException as exc:
            raise RadarError(
                f"Radar no respondió en {self.settings.timeout}s ({url}). "
                "Un sync puede tardar: scrapear artículos llama a sitios externos."
            ) from exc
        except httpx.HTTPError as exc:
            raise RadarError(f"No se pudo contactar con Radar ({url}): {exc}") from exc

        if response.status_code in (200, 201, 202):
            return response.json()

        raise RadarError(
            self._explain(response),
            status=response.status_code,
            detail=_extract_detail(response),
        )

    def _explain(self, response: httpx.Response) -> str:
        """Mensaje que el agente pueda usar, no solo el status.

        La pista por status se antepone SIEMPRE, incluso cuando hay `detail`:
        con un 401, "Not authenticated" no dice que hay que poner RADAR_API_KEY,
        y eso es justo lo que el agente necesita saber.
        """
        head = f"{response.status_code} en {response.request.url.path}"
        hint = _HINTS.get(response.status_code)
        detail = _describe_detail(_extract_detail(response))

        lead = f"{head}. {hint}" if hint else head
        return f"{lead} ({detail})" if detail else lead


def _describe_detail(detail: Any) -> str | None:
    """Convierte el `detail` de FastAPI en una frase corta."""
    if isinstance(detail, str):
        return detail or None
    if isinstance(detail, list) and detail and isinstance(detail[0], dict):
        first = detail[0]
        # `loc[0]` es el origen del error ("query"/"body"), no el campo affected.
        field = ".".join(str(part) for part in (first.get("loc") or [])[1:] or [])
        return f"{field or 'parametros'}: {first.get('msg', 'invalido')}"
    return None


def _extract_detail(response: httpx.Response) -> Any:
    """FastAPI mete el motivo en `detail`, pero a veces es HTML (Railway)."""
    try:
        payload = response.json()
    except ValueError:
        text = (response.text or "").strip()
        if text.startswith("<"):
            # Respuesta de la capa de proxy, no de FastAPI.
            return None
        return text or None
    if isinstance(payload, dict) and "detail" in payload:
        return payload["detail"]
    return payload if not isinstance(payload, dict) else None


def client_for_tests(handler) -> RadarClient:
    """Cliente que responde con el handler de httpx (para MockTransport)."""
    return RadarClient(transport=httpx.MockTransport(handler))