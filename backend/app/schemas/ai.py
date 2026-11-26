import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints

from app.models.ai import KeyStatus, ModelSlot


class ProviderConnection(BaseModel):
    id: uuid.UUID
    key_hint: str
    base_url: str | None
    status: KeyStatus
    last_tested_at: datetime | None
    last_error: str | None
    created_at: datetime


class ProviderRead(BaseModel):
    slug: str
    name: str
    requires_base_url: bool
    connection: ProviderConnection | None


class ConnectRequest(BaseModel):
    provider: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]
    api_key: Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=500)]
    base_url: Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=255)] = None


class ProviderSlugRequest(BaseModel):
    provider: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]


class ModelInfoRead(BaseModel):
    id: str
    name: str
    context_window: int | None
    supports_vision: bool | None
    supports_json: bool | None


class ModelConfigUpdate(BaseModel):
    provider: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]
    model: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class ModelConfigRead(BaseModel):
    slot: ModelSlot
    provider: str
    provider_name: str
    model: str
    capabilities: dict | None
    checked_at: datetime | None
    updated_at: datetime


class UsageEntry(BaseModel):
    id: uuid.UUID
    provider: str
    model: str
    slot: str | None
    task: str
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None
    latency_ms: int
    success: bool
    error_code: str | None
    created_at: datetime


class UsageSummaryRow(BaseModel):
    provider: str
    requests: int
    failures: int
    input_tokens: int
    output_tokens: int
    cost_usd: float | None


class UsageReport(BaseModel):
    summary: list[UsageSummaryRow]
    items: list[UsageEntry]
    total: int
    page: int
    page_size: int
