from dataclasses import dataclass
from datetime import datetime


@dataclass
class GoogleNewsArticle:
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