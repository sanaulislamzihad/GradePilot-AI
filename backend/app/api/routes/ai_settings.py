"""Teacher AI settings: provider keys (BYOK), model slots, capability checks and usage."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import selectinload

from app.api.deps import Client, DbSession, TeacherUser, rate_limit_ai
from app.core.config import get_settings
from app.core.errors import AppError
from app.models.ai import AIProvider, ModelConfig, ModelSlot, UsageLog, UserApiKey
from app.providers.base import AIError
from app.schemas.ai import (
    ConnectRequest,
    ModelConfigRead,
    ModelConfigUpdate,
    ModelInfoRead,
    ProviderConnection,
    ProviderRead,
    ProviderSlugRequest,
    UsageEntry,
    UsageReport,
    UsageSummaryRow,
)
from app.services import ai_capabilities, ai_keys, audit

router = APIRouter(tags=["ai settings"])


def _connection(key: UserApiKey | None) -> ProviderConnection | None:
    if key is None:
        return None
    return ProviderConnection(
        id=key.id, key_hint=key.key_hint, base_url=key.base_url, status=key.status,  # type: ignore[arg-type]
        last_tested_at=key.last_tested_at, last_error=key.last_error, created_at=key.created_at,
    )


def _config_read(config: ModelConfig) -> ModelConfigRead:
    return ModelConfigRead(
        slot=config.slot,  # type: ignore[arg-type]
        provider=config.api_key.provider.slug,
        provider_name=config.api_key.provider.name,
        model=config.model,
        capabilities=config.capabilities,
        checked_at=config.checked_at,
        updated_at=config.updated_at,
    )


# --- Providers -------------------------------------------------------------

@router.get("/providers", response_model=list[ProviderRead])
def list_providers(teacher: TeacherUser, db: DbSession) -> list[ProviderRead]:
    allow_custom = get_settings().allow_custom_ai_endpoints
    providers = db.scalars(select(AIProvider).where(AIProvider.is_enabled.is_(True))).all()
    keys = {k.provider_id: k for k in db.scalars(select(UserApiKey).where(UserApiKey.user_id == teacher.id))}
    return [
        ProviderRead(slug=p.slug, name=p.name, requires_base_url=p.slug == "custom", connection=_connection(keys.get(p.id)))
        for p in providers
        if p.slug != "custom" or allow_custom
    ]


@router.post("/providers/connect", response_model=ProviderRead, dependencies=[Depends(rate_limit_ai)])
def connect_provider(data: ConnectRequest, teacher: TeacherUser, db: DbSession, client: Client) -> ProviderRead:
    provider = ai_keys.get_provider(db, data.provider)
    key = ai_keys.save_key(db, teacher, provider, data.api_key, data.base_url)
    audit.record(db, "ai.key_saved", actor=teacher, entity_type="provider", entity_id=provider.slug,
                 details={"provider": provider.name, "status": key.status}, ip_address=client.ip_address)
    db.commit()
    return ProviderRead(slug=provider.slug, name=provider.name, requires_base_url=provider.slug == "custom",
                        connection=_connection(key))


@router.post("/providers/test", response_model=ProviderRead, dependencies=[Depends(rate_limit_ai)])
def test_provider(data: ProviderSlugRequest, teacher: TeacherUser, db: DbSession) -> ProviderRead:
    ai_keys.require_encryption()
    key = ai_keys.key_for_provider(db, teacher, data.provider)
    ai_keys.test_key(key)
    db.commit()
    return ProviderRead(slug=key.provider.slug, name=key.provider.name,
                        requires_base_url=key.provider.slug == "custom", connection=_connection(key))


@router.get("/providers/models", response_model=list[ModelInfoRead], dependencies=[Depends(rate_limit_ai)])
def provider_models(provider: Annotated[str, Query(max_length=30)], teacher: TeacherUser, db: DbSession) -> list[ModelInfoRead]:
    ai_keys.require_encryption()
    key = ai_keys.key_for_provider(db, teacher, provider)
    try:
        models = ai_keys.adapter_for(key).list_models()
    except AIError as exc:
        raise AppError(502, f"Could not load models: {exc.message}") from None
    return [ModelInfoRead(**m.__dict__) for m in models]


@router.delete("/providers/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_provider(key_id: uuid.UUID, teacher: TeacherUser, db: DbSession, client: Client) -> Response:
    key = ai_keys.owned_key(db, teacher, key_id)
    audit.record(db, "ai.key_deleted", actor=teacher, entity_type="provider", entity_id=key.provider.slug,
                 details={"provider": key.provider.name}, ip_address=client.ip_address)
    # Model slots using this key are removed with it (foreign key cascade).
    for config in db.scalars(select(ModelConfig).where(ModelConfig.api_key_id == key.id)):
        db.delete(config)
    db.delete(key)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Model slots -----------------------------------------------------------

def _load_configs(db: DbSession, teacher) -> list[ModelConfig]:
    return list(db.scalars(
        select(ModelConfig)
        .where(ModelConfig.user_id == teacher.id)
        .options(selectinload(ModelConfig.api_key).selectinload(UserApiKey.provider))
    ))


@router.get("/model-configs", response_model=list[ModelConfigRead])
def list_model_configs(teacher: TeacherUser, db: DbSession) -> list[ModelConfigRead]:
    order = {s.value: i for i, s in enumerate(ModelSlot)}
    return [_config_read(c) for c in sorted(_load_configs(db, teacher), key=lambda c: order.get(c.slot, 9))]


@router.put("/model-configs/{slot}", response_model=ModelConfigRead)
def set_model_config(slot: ModelSlot, data: ModelConfigUpdate, teacher: TeacherUser, db: DbSession) -> ModelConfigRead:
    key = ai_keys.key_for_provider(db, teacher, data.provider)
    config = db.scalar(select(ModelConfig).where(ModelConfig.user_id == teacher.id, ModelConfig.slot == slot.value))
    if config is None:
        config = ModelConfig(user_id=teacher.id, slot=slot.value)
        db.add(config)
    if config.api_key_id != key.id or config.model != data.model:
        # A different model has not been checked yet.
        config.capabilities = None
        config.checked_at = None
    config.api_key = key
    config.model = data.model
    db.commit()
    db.refresh(config)
    return _config_read(config)


@router.delete("/model-configs/{slot}", status_code=status.HTTP_204_NO_CONTENT)
def clear_model_config(slot: ModelSlot, teacher: TeacherUser, db: DbSession) -> Response:
    config = db.scalar(select(ModelConfig).where(ModelConfig.user_id == teacher.id, ModelConfig.slot == slot.value))
    if config is not None:
        db.delete(config)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/model-configs/{slot}/check", response_model=ModelConfigRead, dependencies=[Depends(rate_limit_ai)])
def check_model_config(slot: ModelSlot, teacher: TeacherUser, db: DbSession) -> ModelConfigRead:
    ai_keys.require_encryption()
    config = next((c for c in _load_configs(db, teacher) if c.slot == slot.value), None)
    if config is None:
        raise AppError(404, "Choose a model for this slot first")
    ai_capabilities.check(config)
    db.commit()
    return _config_read(config)


# --- Usage -----------------------------------------------------------------

@router.get("/usage", response_model=UsageReport)
def usage(
    teacher: TeacherUser,
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> UsageReport:
    base = select(UsageLog).where(UsageLog.user_id == teacher.id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(base.order_by(UsageLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    summary_rows = db.execute(
        select(
            UsageLog.provider,
            func.count(UsageLog.id),
            func.sum(case((UsageLog.success.is_(False), 1), else_=0)),
            func.coalesce(func.sum(UsageLog.input_tokens), 0),
            func.coalesce(func.sum(UsageLog.output_tokens), 0),
            func.sum(UsageLog.cost_usd),
        )
        .where(UsageLog.user_id == teacher.id)
        .group_by(UsageLog.provider)
    ).all()
    return UsageReport(
        summary=[
            UsageSummaryRow(provider=p, requests=n, failures=int(f or 0), input_tokens=int(i), output_tokens=int(o),
                            cost_usd=float(c) if c is not None else None)
            for p, n, f, i, o, c in summary_rows
        ],
        items=[
            UsageEntry(
                id=r.id, provider=r.provider, model=r.model, slot=r.slot, task=r.task,
                input_tokens=r.input_tokens, output_tokens=r.output_tokens,
                cost_usd=float(r.cost_usd) if r.cost_usd is not None else None,
                latency_ms=r.latency_ms, success=r.success, error_code=r.error_code, created_at=r.created_at,
            )
            for r in rows
        ],
        total=total, page=page, page_size=page_size,
    )
