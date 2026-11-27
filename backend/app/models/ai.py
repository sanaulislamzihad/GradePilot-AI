"""AI provider connections (bring your own key), model slots and usage records."""

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, Timestamps, UTCDateTime, UUIDPrimaryKey, utcnow
from app.models.user import User


class ModelSlot(str, enum.Enum):
    OCR = "ocr"              # Model A: handwriting, scans, question extraction
    EVALUATOR = "evaluator"  # Model B: rubric-based grading and feedback
    VERIFIER = "verifier"    # Model C: independent review of grading (Phase 5)


class KeyStatus(str, enum.Enum):
    VALID = "valid"
    UNVERIFIED = "unverified"  # saved, but the test could not complete (network, rate limit)
    INVALID = "invalid"        # the provider rejected the key on a later check


class AIProvider(UUIDPrimaryKey, Base):
    """Catalogue of supported providers, seeded by migration."""

    __tablename__ = "ai_providers"

    slug: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    default_base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class UserApiKey(UUIDPrimaryKey, Timestamps, Base):
    """A user's encrypted API key for one provider. The plaintext is never stored or returned."""

    __tablename__ = "user_api_keys"
    __table_args__ = (UniqueConstraint("user_id", "provider_id", name="uq_user_api_keys_user_provider"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ai_providers.id", ondelete="CASCADE"))
    encrypted_key: Mapped[str] = mapped_column(Text)
    key_hint: Mapped[str] = mapped_column(String(12))
    # Only for the optional custom OpenAI-compatible endpoint.
    base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=KeyStatus.UNVERIFIED.value)
    last_tested_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)

    user: Mapped[User] = relationship()
    provider: Mapped[AIProvider] = relationship()


class ModelConfig(UUIDPrimaryKey, Timestamps, Base):
    """Which provider connection and model a user assigned to each slot."""

    __tablename__ = "model_configs"
    __table_args__ = (UniqueConstraint("user_id", "slot", name="uq_model_configs_user_slot"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    slot: Mapped[str] = mapped_column(String(20))
    api_key_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_api_keys.id", ondelete="CASCADE"))
    model: Mapped[str] = mapped_column(String(200))
    # Result of the last capability check (availability, text, JSON, vision, context window).
    capabilities: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    checked_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    api_key: Mapped[UserApiKey] = relationship()


class UsageLog(UUIDPrimaryKey, Base):
    """One AI request: who, which model, what for, tokens, cost when known, outcome."""

    __tablename__ = "usage_logs"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(30))
    model: Mapped[str] = mapped_column(String(200))
    slot: Mapped[str | None] = mapped_column(String(20), nullable=True)
    task: Mapped[str] = mapped_column(String(50))
    submission_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("submissions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    exam_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("exams.id", ondelete="SET NULL"), nullable=True, index=True
    )
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer)
    success: Mapped[bool] = mapped_column(Boolean)
    error_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
