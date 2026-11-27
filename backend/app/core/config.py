"""Application settings loaded from environment variables.

The backend reads `.env` from the backend folder or the repository root, so the
same file works for local development and Docker Compose.
"""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
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

    # API key encryption: comma-separated "key_id:base64(32 bytes)" entries.
    # The first entry encrypts new keys; the others still decrypt older ones (rotation).
    encryption_keys: str = ""

    # Background jobs. Redis in production; the SQLAlchemy broker needs no extra service.
    celery_broker_url: str = f"sqla+sqlite:///{(BACKEND_DIR / 'celery-broker.db').as_posix()}"
    celery_task_always_eager: bool = False

    # AI providers
    ai_request_timeout_seconds: float = Field(default=120.0, ge=5, le=600)
    # OpenAI-compatible endpoints at a custom URL (e.g. a local model server).
    # Off by default: a user-supplied URL makes the server send requests to it.
    allow_custom_ai_endpoints: bool = False

    # Local semantic similarity signal (Sentence Transformers, CPU).
    similarity_enabled: bool = True
    similarity_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Rate limits. With RATE_LIMIT_REDIS_URL set, counts are shared by every API
    # worker; otherwise each process keeps its own (fine for a single worker).
    rate_limit_redis_url: str = ""
    auth_rate_limit_attempts: int = 10
    auth_rate_limit_window_seconds: int = 300
    upload_rate_limit_attempts: int = 20
    upload_rate_limit_window_seconds: int = 600
    ai_rate_limit_attempts: int = 60
    ai_rate_limit_window_seconds: int = 600

    # Largest request body accepted, in megabytes (answer scripts are limited per exam, up to 50 MB).
    max_request_size_mb: int = Field(default=60, ge=1, le=500)

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

    @model_validator(mode="after")
    def _production_safety(self) -> "Settings":
        """Refuse to start a production server with settings that are only safe locally."""
        if self.environment != "production":
            return self
        problems = []
        if not self.cookie_secure:
            problems.append("COOKIE_SECURE must be true (the app must be served over HTTPS)")
        if not self.encryption_keys or "replace-with" in self.encryption_keys:
            problems.append("ENCRYPTION_KEYS must be set so provider API keys can be stored encrypted")
        if self.is_sqlite:
            problems.append("DATABASE_URL must point to PostgreSQL; SQLite is for local development only")
        if self.celery_broker_url.startswith("sqla+sqlite"):
            problems.append("CELERY_BROKER_URL must point to Redis")
        if problems:
            raise ValueError("Unsafe production configuration: " + "; ".join(problems))
        return self

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
