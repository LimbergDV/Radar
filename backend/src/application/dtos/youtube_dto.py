from pydantic import BaseModel

class YouTubeConfigUpdate(BaseModel):
    keywords: list[str]
    channel_ids: list[str]
    languages: list[str]
    max_results: int