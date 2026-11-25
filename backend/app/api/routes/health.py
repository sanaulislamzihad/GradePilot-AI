from fastapi import APIRouter
from sqlalchemy import text

from app import __version__
from app.api.deps import DbSession

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: DbSession) -> dict:
    """Liveness and database connectivity check (no sensitive data)."""
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except Exception:  # noqa: BLE001 - any failure means the database is unavailable
        database = "unavailable"
    return {"status": "ok" if database == "ok" else "degraded", "version": __version__, "database": database}
