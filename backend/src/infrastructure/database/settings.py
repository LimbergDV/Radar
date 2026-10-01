from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    youtube_api_key: str = ""
    github_token: str = ""
    app_env: str = "development"
    app_port: int = 8000
    cors_origins: list[str] = ["http://localhost:4200"]
    sync_interval_minutes: int = 60


# Instancia global — se importa desde cualquier lado
settings = Settings()