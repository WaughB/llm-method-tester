"""Tests for application settings."""

from pathlib import Path

import pytest

from llm_bench.config import Settings


class TestSettings:
    def test_defaults(self) -> None:
        settings = Settings(_env_file=None)
        assert settings.ollama_base_url == "http://localhost:11434"
        assert "gpt-oss:20b" in settings.models
        assert "nemotron-3-nano:4b" in settings.models
        assert "llama3.1:8b" in settings.models
        assert settings.embedding_model == "nomic-embed-text"
        assert settings.judge_model == "gpt-oss:20b"

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LLM_BENCH_OLLAMA_BASE_URL", "http://other:1234")
        settings = Settings(_env_file=None)
        assert settings.ollama_base_url == "http://other:1234"

    def test_cache_dir_is_outside_repo_by_default(self, tmp_path: Path) -> None:
        settings = Settings(_env_file=None)
        # cache must not default into the (OneDrive-synced) working directory
        assert not settings.cache_dir.is_relative_to(Path.cwd())

    def test_db_path_lives_under_cache_dir(self, tmp_path: Path) -> None:
        settings = Settings(_env_file=None, cache_dir=tmp_path)
        assert settings.db_path == tmp_path / "results.db"
