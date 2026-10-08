from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Dialecto que espera `create_async_engine`. Cualquier URL de Postgres tiene que
# apuntar aqui o el arranque falla con NoSuchModuleError.
_ASYNC_PG_DRIVER = "postgresql+asyncpg"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    database_url: str
    sql_echo: bool = False

    youtube_api_key: str = ""
    # Sin token el rate limit de GitHub es 60 req/h; con token, 5000.
    github_token: str = ""

    app_env: str = "development"
    app_port: int = 8000
    # NoDecode: acepta tanto JSON (["https://a","https://b"]) como una lista
    # separada por comas. Sin esto, un CORS_ORIGINS="a,b" en Railway revienta
    # al arrancar porque pydantic-settings solo probaria a parsear JSON.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:4200"]

    sync_interval_minutes: int = 60
    log_level: str = "INFO"

    @field_validator("database_url")
    @classmethod
    def _force_asyncpg_driver(cls, value: str) -> str:
        """Fuerza el driver asyncpq en la URL de la base de datos.

        Railway entrega `postgres://user:pass@host:5432/db`, y un Postgres de
        cualquier proveedor suele venir como `postgresql://...`. Ninguno de los
        dos funciona con `create_async_engine`: el primero no es un dialecto
        conocido y el segundo intenta cargar el driver sincrono `psycopg`, que
        no esta instalado. Se normaliza a `postgresql+asyncpg://` una sola vez,
        aqui, para que el resto del codigo no tenga que celibrar el formato.
        """
        if not value:
            return value

        url = value.strip()
        scheme, sep, rest = url.partition("://")
        if not sep:
            # URL sin esquema explicito: se asume Postgres.
            return f"{_ASYNC_PG_DRIVER}://{url}"

        if scheme in ("postgres", "postgresql", "postgresql+psycopg2", "postgres+psycopg2"):
            return f"{_ASYNC_PG_DRIVER}://{rest}"
        if scheme == "postgres+asyncpg":
            return f"{_ASYNC_PG_DRIVER}://{rest}"
        if scheme == _ASYNC_PG_DRIVER:
            return url

        # Otro driver (mysql, sqlite, ...): se deja como esta para que el error
        # lo diga SQLAlchemy y no una conversion silenciosa.
        return url

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value):
        """Acepta JSON o lista separada por comas/espacios."""
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            if raw.startswith("["):
                import json

                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    # JSON roto: mejor una lista utilizable que un crash.
                    raw = raw.strip("[]")
            return [part.strip().strip("\"'") for part in raw.split(",") if part.strip()]
        return value


# Instancia global — se importa desde cualquier lado
settings = Settings()