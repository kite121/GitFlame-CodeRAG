from dataclasses import dataclass
import os


@dataclass
class Settings:
    """Runtime configuration loaded from environment variables."""

    database_url: str = os.getenv("DATABASE_URL", "sqlite:///blog.db")
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret")
    access_token_ttl_seconds: int = int(os.getenv("ACCESS_TOKEN_TTL", "3600"))
    page_size: int = int(os.getenv("PAGE_SIZE", "20"))


def get_settings() -> Settings:
    return Settings()
