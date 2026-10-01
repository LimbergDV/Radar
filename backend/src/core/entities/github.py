from dataclasses import dataclass
from datetime import datetime


@dataclass
class GitHubRepo:
    id: int
    name: str
    full_name: str
    html_url: str
    description: str
    stargazers_count: int
    forks_count: int
    open_issues_count: int
    language: str
    topics: list[str]
    readme: str
    updated_at: datetime
    synced_at: datetime
    owner_avatar_url: str | None = None
    license: str | None = None