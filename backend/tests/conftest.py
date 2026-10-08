"""Fixtures compartidas.

Los tests de este proyecto son de dos tipos:

- **Unitarios**: logica pura de `core/use_cases` y mapeos. No tocan red ni DB,
  asi que corren siempre y son los que atrapan las regresiones.
- **De integracion**: requieren PostgreSQL. Se saltan solos si no hay DB
  configurada (`RUN_DB_TESTS=1` los activa explicitamente), para que
  `pytest` siga siendo util sin levantar la base de datos.
"""

import os
from pathlib import Path

import pytest

from src.core.logging_config import setup_logging

# Antes de importar `settings`. El relleno solo se pone si no hay .env: las
# variables de entorno tienen prioridad sobre el archivo y lo pisarían.
if "DATABASE_URL" not in os.environ and not Path(".env").exists():
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://user:pass@localhost:5432/test_db"

os.environ.setdefault("APP_ENV", "test")

setup_logging("WARNING")

@pytest.fixture
def sample_config_youtube():
    """Config de YouTube con dos keywords, un canal y limite 3."""
    from src.core.entities.config import YouTubeConfig

    return YouTubeConfig(
        keywords=["inteligencia artificial", "chatgpt"],
        channel_ids=["@midudev"],
        languages=["es", "en"],
        max_results=3,
    )

@pytest.fixture
def sample_config_news():
    """Config de News con feed dual ES/EN."""
    from src.core.entities.config import GoogleNewsConfig

    return GoogleNewsConfig(
        q="Inteligencia Artificial",
        ceid="MX:es-419,US:en",
        when="1d",
        max_results=10,
        days_window=1,
    )

@pytest.fixture
def sample_config_github():
    """Config de GitHub con los filtros de por defecto del plan."""
    from src.core.entities.config import GitHubConfig

    return GitHubConfig(
        keywords=["openai", "claude"],
        days_active=2,
        min_stars=50,
        min_forks=10,
        require_license=False,
        selected_topics=["ai", "llm"],
        selected_languages=["python", "typescript"],
        max_results=10,
    )