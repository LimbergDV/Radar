from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class HuggingFacePaper:
    """Paper del Daily Papers o de la búsqueda de Hugging Face.

    El abstract y el AI summary son el "contenido rico" que se lee en la app y
    que el MCP entrega por bloques. El PDF no se descarga: se enlaza.
    """

    id: str
    title: str
    abstract: str
    published_at: datetime
    submitted_on_daily_at: datetime | None = None
    ai_summary: str = ""
    ai_keywords: list[str] = field(default_factory=list)
    authors: list[str] = field(default_factory=list)
    upvotes: int = 0
    comments: int = 0
    thumbnail_url: str | None = None
    github_repo: str | None = None
    project_page: str | None = None
    organization: str | None = None
    linked_models: list[str] = field(default_factory=list)
    linked_datasets: list[str] = field(default_factory=list)
    linked_spaces: list[str] = field(default_factory=list)
    hf_url: str = ""
    arxiv_url: str = ""
    pdf_url: str = ""
    source: str = "daily"
    synced_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def effective_date(self) -> datetime:
        """Fecha que se muestra y ordena: la entrada al Daily si existe."""
        return self.submitted_on_daily_at or self.published_at
