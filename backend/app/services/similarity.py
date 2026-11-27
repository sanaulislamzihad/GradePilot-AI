"""Local semantic similarity with Sentence Transformers (all-MiniLM-L6-v2).

Runs on the server's CPU with no API key. It is a signal only: it never sets or
changes marks. It flags evaluations where the AI's marks and the closeness of
the answer to the model answer point in opposite directions.

The model (~90 MB) is downloaded from Hugging Face on first use and cached. If
the package or the model is unavailable the signal is simply skipped.
"""

import logging
import threading

from app.core.config import get_settings

logger = logging.getLogger("gradepilot.similarity")

_lock = threading.Lock()
_model = None
_unavailable = False


def _load():
    global _model, _unavailable
    if _model is not None or _unavailable:
        return _model
    with _lock:
        if _model is None and not _unavailable:
            try:
                from sentence_transformers import SentenceTransformer

                _model = SentenceTransformer(get_settings().similarity_model, device="cpu")
            except Exception as exc:  # noqa: BLE001 - missing package, no network, corrupt cache...
                _unavailable = True
                logger.warning("Semantic similarity is unavailable: %s", type(exc).__name__)
    return _model


def score(answer: str, reference: str) -> float | None:
    """Cosine similarity in [0, 1] (negative values clipped), or None if unavailable."""
    if not get_settings().similarity_enabled or not answer.strip() or not reference.strip():
        return None
    model = _load()
    if model is None:
        return None
    embeddings = model.encode([answer[:4000], reference[:4000]], normalize_embeddings=True)
    value = float((embeddings[0] * embeddings[1]).sum())
    return round(max(0.0, min(1.0, value)), 3)
