"""Application configuration via environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings


# Locate .env: search up from this file's directory for the project root
_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parent.parent.parent.parent.parent  # knot/core/ -> src/ -> backend/ -> KNOT/
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Global application settings loaded from environment variables."""

    # LLM Provider
    llm_provider: str = "deepseek"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"

    # Database
    database_url: str = "sqlite+aiosqlite:///./knot.db"
    redis_url: str = "redis://localhost:6379/0"

    # Milvus
    milvus_host: str = "localhost"
    milvus_port: int = 19530

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    model_config = {
        "env_file": str(_ENV_FILE) if _ENV_FILE.exists() else ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
