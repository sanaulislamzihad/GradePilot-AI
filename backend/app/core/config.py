"""Application settings loaded from environment variables.

The backend reads `.env` from the backend folder or the repository root, so the
same file works for local development and Docker Compose.
"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent

_INSECURE_SECRETS = {"", "replace-with-a-long-random-secret", "change-me", "secret"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    app_name: str = "GradePilot AI"
    api_prefix: str = "/api"
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    database_url: str = f"sqlite:///{(BACKEND_DIR / 'gradepilot.db').as_posix()}"

    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=15, ge=1, le=120)
    refresh_token_expire_days: int = Field(default=7, ge=1, le=60)
    refresh_cookie_name: str = "gp_refresh"
    cookie_secure: bool = False

    storage_dir: Path = REPO_DIR / "storage"

    # Simple per-process limiter for credential endpoints.
    auth_rate_limit_attempts: int = 10
    auth_rate_limit_window_seconds: int = 300

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("jwt_secret_key")
    @classmethod
    def _require_strong_secret(cls, value: str) -> str:
        if value in _INSECURE_SECRETS or len(value) < 32:
            raise ValueError(
                "JWT_SECRET_KEY must be set to a random value of at least 32 characters. "
                'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(64))"'
            )
        return value

    @field_validator("database_url")
    @classmethod
    def _resolve_sqlite_path(cls, value: str) -> str:
        # Anchor relative SQLite files to the backend folder so the API, Alembic
        # and scripts always open the same database regardless of the shell cwd.
        prefix = "sqlite:///./"
        if value.startswith(prefix):
            return f"sqlite:///{(BACKEND_DIR / value[len(prefix):]).as_posix()}"
        return value

    @field_validator("storage_dir", mode="after")
    @classmethod
    def _resolve_storage(cls, value: Path) -> Path:
        # Relative paths are resolved from the backend folder, not the shell cwd.
        return value if value.is_absolute() else (BACKEND_DIR / value).resolve()

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
