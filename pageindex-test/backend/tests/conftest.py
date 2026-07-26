"""Shared fixtures: in-memory SQLite engine with the full schema applied."""

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.pool import StaticPool

from pageindex_test.config import Settings
from pageindex_test.db.schema import init_schema


@pytest.fixture
def engine() -> Engine:
    # StaticPool: one shared connection, or every checkout would see a brand
    # new empty in-memory database
    eng = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    init_schema(eng)
    return eng


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None)


def make_pdf(path, pages, toc=None):
    """Build a small real PDF for extraction tests."""
    import pymupdf

    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 72), text)
    if toc:
        doc.set_toc(toc)
    doc.save(path)
    doc.close()
    return path
