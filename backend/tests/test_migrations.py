"""The Alembic history must produce exactly the schema the models describe."""

from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

from app.database.base import Base
from tests.conftest import alembic_config


def test_migrations_match_models(tmp_path: Path):
    url = f"sqlite:///{(tmp_path / 'fresh.db').as_posix()}"
    command.upgrade(alembic_config(url), "head")
    engine = create_engine(url)
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    engine.dispose()
    assert diff == []


def test_downgrade_to_base_and_back(tmp_path: Path):
    config = alembic_config(f"sqlite:///{(tmp_path / 'roundtrip.db').as_posix()}")
    command.upgrade(config, "head")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
