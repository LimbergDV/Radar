"""Tests de la configuracion (settings).

Regresion que cubren: al desplegar, Railway entrega la base de datos como
`postgres://user:pass@host:5432/db`. Ese esquema no es un dialecto de
SQLAlchemy y el arranque reventaba con NoSuchModuleError; igual pasaba con el
`postgresql://` clasico, que intenta cargar psycopg (driver sincrono, no
instalado). Aqui se normaliza a `postgresql+asyncpg://`.

Tambien cubren CORS_ORIGINS, que en Railway se escribe como texto plano y
pydantic-settings solo probaria a parsearlo como JSON.
"""

import pytest

from src.infrastructure.database.settings import Settings

DB = "postgresql+asyncpg://u:p@host:5432/db"


def _settings(**overrides):
    return Settings(database_url=DB, **overrides)

@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Lo que da Railway.
        ("postgres://u:p@h.railway.internal:5432/railway",
         "postgresql+asyncpg://u:p@h.railway.internal:5432/railway"),
        # Postgres generico.
        ("postgresql://u:p@h:5432/db", "postgresql+asyncpg://u:p@h:5432/db"),
        ("postgresql+psycopg2://u:p@h:5432/db", "postgresql+asyncpg://u:p@h:5432/db"),
        # Ya correcto: no debe tocarse ni duplicar el esquema.
        ("postgresql+asyncpg://u:p@h:5432/db", "postgresql+asyncpg://u:p@h:5432/db"),
        ("postgres+asyncpg://u:p@h:5432/db", "postgresql+asyncpg://u:p@h:5432/db"),
        # Sin esquema explicito.
        ("u:p@h:5432/db", "postgresql+asyncpg://u:p@h:5432/db"),
    ],
)
def test_database_url_is_normalized_to_asyncpg(raw, expected):
    assert Settings(database_url=raw).database_url == expected

def test_database_url_keeps_unknown_driver_untouched():
    """No we silently convert a MySQL URL; que lo diga SQLAlchemy."""
    assert Settings(database_url="mysql+aiomysql://u:p@h/db").database_url == (
        "mysql+aiomysql://u:p@h/db"
    )

def test_database_url_strips_surrounding_whitespace():
    assert Settings(database_url="  postgres://u:p@h/db  ").database_url == (
        "postgresql+asyncpg://u:p@h/db"
    )

def test_cors_origins_accepts_json_list():
    got = _settings(cors_origins='["https://a.up.railway.app","https://b.up.railway.app"]')
    assert got.cors_origins == ["https://a.up.railway.app", "https://b.up.railway.app"]

def test_cors_origins_accepts_comma_separated():
    got = _settings(cors_origins="https://a.up.railway.app,https://b.up.railway.app")
    assert got.cors_origins == ["https://a.up.railway.app", "https://b.up.railway.app"]

def test_cors_origins_accepts_single_value():
    assert _settings(cors_origins="https://a.up.railway.app").cors_origins == [
        "https://a.up.railway.app"
    ]

def test_cors_origins_empty_string_yields_empty_list():
    assert _settings(cors_origins="").cors_origins == []

def test_cors_origins_broken_json_does_not_crash_startup():
    """Un '[' de mas no debe tumbar el arranque de la API."""
    assert _settings(cors_origins='["https://a.up.railway.app"').cors_origins == [
        "https://a.up.railway.app"
    ]

def test_default_cors_origins_still_localhost():
    """Que no se rompa el desarrollo local por defecto."""
    assert _settings().cors_origins == ["http://localhost:4200"]