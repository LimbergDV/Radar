"""Configuración del servidor MCP, leída del entorno.

Todo tiene defaults que apuntan a la app ya desplegada, para que `radar-mcp`
funcione sin configurar nada. Lo que sí conviene cambiar en cada instalación
es `RADAR_API_KEY` (cuando exista auth) y el presupuesto de caracteres.
"""

import os
from dataclasses import dataclass

# La app desplegada. El MCP habla SIEMPRE por aquí, nunca contra localhost.
DEFAULT_API_URL = "https://frontend-production-820b7.up.railway.app"


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    """Ajustes del servidor. Se resuelve una vez al importar."""

    api_url: str = DEFAULT_API_URL
    api_key: str = ""
    timeout: float = 30.0

    # Presupuesto de contenido por respuesta. ~8.000 chars ≈ 2.000 tokens:
    # cabe de sobra en la ventana del agente sin vaciarlo, y lo que se pasa se
    # dice explícitamente con `truncated`, para que pida el resto si lo quiere.
    max_content_chars: int = 8_000

    # Cuántos items trae radar_search por defecto (la API tope 50).
    default_limit: int = 20

    # sync está apagado por defecto: consume cuota de YouTube y hace scraping.
    enable_sync: bool = False

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key)


def load_settings() -> Settings:
    return Settings(
        api_url=os.getenv("RADAR_API_URL", DEFAULT_API_URL).rstrip("/"),
        api_key=os.getenv("RADAR_API_KEY", "").strip(),
        timeout=float(_env_int("RADAR_TIMEOUT", 30)),
        max_content_chars=_env_int("RADAR_MAX_CONTENT_CHARS", 8_000),
        default_limit=min(_env_int("RADAR_DEFAULT_LIMIT", 20), 50),
        enable_sync=_env_bool("RADAR_ENABLE_SYNC", False),
    )


settings = load_settings()