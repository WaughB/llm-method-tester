"""Shared fixtures for the test suite."""

from pathlib import Path

import pytest

from llm_bench.corpus import BenchmarkCorpus
from llm_bench.llm.fake import FakeEmbeddingClient, FakeLLMClient

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def mini_corpus_root() -> Path:
    return FIXTURES / "mini_corpus"


@pytest.fixture
def mini_corpus(mini_corpus_root: Path) -> BenchmarkCorpus:
    return BenchmarkCorpus.load(mini_corpus_root)


@pytest.fixture
def fake_llm() -> FakeLLMClient:
    return FakeLLMClient()


@pytest.fixture
def fake_embedder() -> FakeEmbeddingClient:
    return FakeEmbeddingClient()
