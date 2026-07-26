"""Shared fixtures: in-memory SQLite engine with the full schema applied."""

import pytest
from sqlalchemy import Engine, create_engine

from pageindex_test.config import Settings
from pageindex_test.db.schema import init_schema


@pytest.fixture
def engine() -> Engine:
    eng = create_engine("sqlite+pysqlite:///:memory:", future=True)
    init_schema(eng)
    return eng


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None)
