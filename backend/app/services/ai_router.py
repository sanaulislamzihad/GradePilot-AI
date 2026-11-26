"""Central AI router.

Every AI call goes through `run` / `run_json`: it resolves the user's model for
the task's slot, decrypts the key only for the request, calls the provider
adapter, retries transient failures, validates structured output and records
usage. The grading pipeline never talks to a provider directly.
"""

import json
import logging
import re
import time
import uuid
from dataclasses import dataclass
from typing import TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.models.ai import ModelConfig, ModelSlot, UsageLog
from app.models.user import User
from app.providers.base import (
    AIConfigurationError,
    AIError,
    AIInvalidResponseError,
    AIRequest,
    AIResponse,
)
from app.security.crypto import DecryptionError, EncryptionUnavailableError
from app.services import ai_keys

logger = logging.getLogger("gradepilot.ai")

T = TypeVar("T", bound=BaseModel)

MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = (1.0, 3.0)
_MAX_RETRY_AFTER = 20.0

# Tests replace this to avoid real waiting.
sleep = time.sleep

SLOT_LABELS = {
    ModelSlot.OCR.value: "OCR and document model",
    ModelSlot.EVALUATOR.value: "evaluator model",
    ModelSlot.VERIFIER.value: "verifier model",
}


@dataclass
class TaskContext:
    task: str
    submission_id: uuid.UUID | None = None
    exam_id: uuid.UUID | None = None


def slot_config(db: Session, user_id: uuid.UUID, slot: ModelSlot) -> ModelConfig:
    config = db.scalar(select(ModelConfig).where(ModelConfig.user_id == user_id, ModelConfig.slot == slot.value))
    if config is None:
        raise AIConfigurationError(
            f"No {SLOT_LABELS[slot.value]} is set up. Choose one in AI Settings."
        )
    return config


def has_slot(db: Session, user_id: uuid.UUID, slot: ModelSlot) -> bool:
    return db.scalar(
        select(ModelConfig.id).where(ModelConfig.user_id == user_id, ModelConfig.slot == slot.value)
    ) is not None


def _log_usage(user_id: uuid.UUID, provider: str, model: str, slot: str | None, context: TaskContext,
               response: AIResponse | None, latency_ms: int, error: AIError | None) -> None:
    # A separate session, so usage is recorded even if the caller rolls back.
    with SessionLocal() as db:
        db.add(UsageLog(
            user_id=user_id,
            provider=provider,
            model=response.model if response else model,
            slot=slot,
            task=context.task,
            submission_id=context.submission_id,
            exam_id=context.exam_id,
            input_tokens=response.usage.input_tokens if response else None,
            output_tokens=response.usage.output_tokens if response else None,
            cost_usd=response.usage.cost_usd if response else None,
            latency_ms=latency_ms,
            success=error is None,
            error_code=error.code if error else None,
        ))
        db.commit()


def call(config: ModelConfig, request: AIRequest, context: TaskContext) -> AIResponse:
    """Call the configured model with retries for transient errors."""
    key = config.api_key
    provider = key.provider.slug
    try:
        adapter = ai_keys.adapter_for(key)
    except DecryptionError:
        raise AIConfigurationError("The stored API key could not be decrypted. Enter the key again in AI Settings.") from None
    except EncryptionUnavailableError:
        raise AIConfigurationError("API key storage is not configured on the server.") from None

    last_error: AIError | None = None
    for attempt in range(MAX_ATTEMPTS):
        started = time.monotonic()
        try:
            response = adapter.complete(config.model, request)
        except AIError as exc:
            latency = int((time.monotonic() - started) * 1000)
            _log_usage(config.user_id, provider, config.model, config.slot, context, None, latency, exc)
            last_error = exc
            if not exc.retryable or attempt == MAX_ATTEMPTS - 1:
                break
            delay = min(exc.retry_after or _BACKOFF_SECONDS[min(attempt, len(_BACKOFF_SECONDS) - 1)], _MAX_RETRY_AFTER)
            logger.info("Retrying %s/%s after %s (%s)", provider, config.model, exc.code, context.task)
            sleep(delay)
            continue
        latency = int((time.monotonic() - started) * 1000)
        _log_usage(config.user_id, provider, config.model, config.slot, context, response, latency, None)
        return response
    assert last_error is not None
    raise last_error


def run(db: Session, user: User | uuid.UUID, slot: ModelSlot, request: AIRequest, context: TaskContext) -> AIResponse:
    user_id = user.id if isinstance(user, User) else user
    return call(slot_config(db, user_id, slot), request, context)


_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def parse_json(text: str) -> object:
    """Parse model output as JSON, tolerating a Markdown code fence or leading prose."""
    cleaned = _FENCE.sub("", text.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end > start:
            return json.loads(cleaned[start:end + 1])
        raise


def call_json(config: ModelConfig, request: AIRequest, model_cls: type[T], context: TaskContext,
              extra_check=None) -> tuple[T, AIResponse]:
    """Call the model for structured output and validate it.

    Invalid output is retried once with the validation error fed back to the
    model; a second failure raises AIInvalidResponseError. `extra_check` may
    raise ValueError for domain rules the schema cannot express.
    """
    attempt_request = request
    last_problem = ""
    for attempt in range(2):
        response = call(config, attempt_request, context)
        try:
            parsed = model_cls.model_validate(parse_json(response.text))
            if extra_check:
                extra_check(parsed)
            return parsed, response
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            last_problem = str(exc).splitlines()[0][:300] if str(exc) else type(exc).__name__
            logger.info("Invalid structured output from %s (%s): %s", config.model, context.task, last_problem)
            attempt_request = AIRequest(
                system=request.system,
                prompt=(
                    f"{request.prompt}\n\nYour previous answer was rejected: {last_problem}\n"
                    "Return only a JSON object that follows the required schema and rules."
                ),
                images=request.images,
                json_schema=request.json_schema,
                max_tokens=request.max_tokens,
            )
    raise AIInvalidResponseError(f"The model did not return valid structured output: {last_problem}")


def run_json(db: Session, user: User | uuid.UUID, slot: ModelSlot, request: AIRequest, model_cls: type[T],
             context: TaskContext, extra_check=None) -> tuple[T, AIResponse]:
    user_id = user.id if isinstance(user, User) else user
    return call_json(slot_config(db, user_id, slot), request, model_cls, context, extra_check)
