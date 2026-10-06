from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class YouTubeConfig:
    keywords: list[str] = field(default_factory=list)
    channel_ids: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=lambda: ["es", "en"])
    max_results: int = 5
    last_search_at: datetime | None = None


@dataclass
class GoogleNewsConfig:
    q: str = "Inteligencia Artificial OR IA"
    hl: str = "es-419"
    gl: str = "MX"
    # Varios pares separados por coma -> feed dual (p.ej. "MX:es-419,US:en")
    ceid: str = "MX:es-419"
    when: str = "1d"
    site: str = ""
    intitle: str = ""
    max_results: int = 50
    # Ventana de antiguedad en dias para el sync (0 = sin filtro)
    days_window: int = 1
    last_search_at: datetime | None = None


@dataclass
class GitHubConfig:
    keywords: list[str] = field(default_factory=lambda: ["openai", "claude", "langchain"])
    days_active: int = 2
    min_stars: int = 50
    min_forks: int = 10
    require_license: bool = False
    selected_topics: list[str] = field(default_factory=lambda: ["ai", "llm"])
    selected_languages: list[str] = field(default_factory=lambda: ["python", "typescript"])
    max_results: int = 50
    last_search_at: datetime | None = None