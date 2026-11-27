"""Declarative base and shared column helpers."""

import threading
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import DateTime, MetaData, TypeDecorator, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Stable constraint names keep Alembic migrations identical on SQLite and PostgreSQL.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


_clock_lock = threading.Lock()
_last_timestamp = datetime.min.replace(tzinfo=UTC)
_TICK = timedelta(microseconds=1)


def utcnow() -> datetime:
    """Current UTC time, strictly increasing within the process.

    Some platforms (Windows with Python 3.11) only advance the wall clock every
    ~15 ms, so records created in quick succession would share a timestamp and
    "newest first" lists would have no defined order.
    """
    global _last_timestamp
    with _clock_lock:
        now = datetime.now(UTC)
        if now <= _last_timestamp:
            now = _last_timestamp + _TICK
        _last_timestamp = now
        return now


def as_utc(value: datetime) -> datetime:
    """SQLite returns naive datetimes; treat them as UTC."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)


class UTCDateTime(TypeDecorator[datetime]):
    """Timezone-aware datetime that always comes back from the database in UTC.

    PostgreSQL keeps the offset, but SQLite drops it, which would make the API
    emit naive timestamps that browsers misread as local time.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        return as_utc(value).astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        return None if value is None else as_utc(value).astimezone(UTC)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {datetime: UTCDateTime}


class UUIDPrimaryKey:
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utcnow, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
        nullable=False,
    )
