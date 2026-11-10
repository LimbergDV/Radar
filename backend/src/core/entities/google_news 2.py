from dataclasses import dataclass
from datetime import datetime


@dataclass
class GoogleNewsArticle:
    """Articulo de Google News.

    `link` apunta al medio cuando se pudo resolver la URL real; si no, conserva
    el link de Google News (que abre en navegador). `original_link` siempre guarda
    el token opaco del RSS para poder reintentar la decodificacion mas adelante.
    """

    id: str
    title: str
    link: str
    pub_date: datetime
    source_name: str
    source_url: str
    language: str
    fetched_at: datetime
    image_url: str | None = None
    content: str | None = None
    original_link: str = ""
    content_fetched: bool = False