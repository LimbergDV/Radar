from dataclasses import dataclass
from datetime import datetime


@dataclass
class YouTubeVideo:
    id: str
    title: str
    channel: str
    channel_id: str
    published_at: datetime
    url: str
    thumbnail_url: str
    transcript: str
    views: int
    likes: int
    comments: int
    duration_seconds: int
    language: str
    synced_at: datetime