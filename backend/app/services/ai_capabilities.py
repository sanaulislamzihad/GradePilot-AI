"""Check what a configured model can actually do, with small live requests.

Provider model lists rarely state vision or JSON support, so the check sends
two tiny probes (a JSON reply, and a digit drawn in an image) instead of
trusting a hardcoded table that goes out of date.
"""

import io

from PIL import Image, ImageDraw
from pydantic import BaseModel

from app.database.base import utcnow
from app.models.ai import ModelConfig
from app.providers.base import AIError, AIImage, AIRequest
from app.services import ai_keys, ai_router


class _Probe(BaseModel):
    answer: str


_PROBE_SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
    "additionalProperties": False,
}


def _digit_image() -> bytes:
    """A large, unambiguous "7" drawn with thick strokes."""
    image = Image.new("RGB", (160, 160), "white")
    draw = ImageDraw.Draw(image)
    draw.line([(35, 30), (125, 30)], fill="black", width=16)
    draw.line([(125, 30), (65, 135)], fill="black", width=16)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def check(config: ModelConfig) -> dict:
    result: dict = {"available": None, "context_window": None, "text": False, "json": False, "vision": None, "errors": {}}
    context = ai_router.TaskContext(task="capability_check")

    try:
        models = ai_keys.adapter_for(config.api_key).list_models()
        match = next((m for m in models if m.id == config.model or m.id == config.model.removeprefix("models/")), None)
        result["available"] = match is not None
        if match:
            result["context_window"] = match.context_window
    except AIError as exc:
        result["errors"]["available"] = exc.message

    try:
        parsed, _ = ai_router.call_json(
            config,
            AIRequest(
                system="You are a connectivity check. Reply only with JSON.",
                prompt='Return the JSON object {"answer": "ready"}.',
                json_schema=_PROBE_SCHEMA,
                max_tokens=200,
            ),
            _Probe,
            context,
        )
        result["text"] = True
        result["json"] = parsed.answer.strip().lower().startswith("ready")
    except AIError as exc:
        result["errors"]["text"] = exc.message

    if result["text"]:
        try:
            parsed, _ = ai_router.call_json(
                config,
                AIRequest(
                    system="You read images. Reply only with JSON.",
                    prompt='Which single digit is drawn in the image? Return {"answer": "<digit>"}.',
                    images=[AIImage("image/png", _digit_image())],
                    json_schema=_PROBE_SCHEMA,
                    max_tokens=200,
                ),
                _Probe,
                context,
            )
            result["vision"] = "7" in parsed.answer
        except AIError as exc:
            result["vision"] = False
            result["errors"]["vision"] = exc.message

    config.capabilities = result
    config.checked_at = utcnow()
    return result
