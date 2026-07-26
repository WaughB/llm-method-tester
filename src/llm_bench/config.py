"""Application settings, overridable via LLM_BENCH_* env vars or a .env file."""

import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_cache_dir() -> Path:
    """Runtime artifacts live outside the repo: the repo sits in OneDrive, and
    sync locks corrupt SQLite/Chroma files that are written mid-run."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "llm-method-tester"
    return Path.home() / ".cache" / "llm-method-tester"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LLM_BENCH_", env_file=".env", extra="ignore")

    ollama_base_url: str = "http://localhost:11434"
    request_timeout_s: float = 600.0
    models: list[str] = Field(
        default_factory=lambda: ["gpt-oss:20b", "nemotron-3-nano:4b", "llama3.1:8b"]
    )
    embedding_model: str = "nomic-embed-text"
    judge_model: str = "gpt-oss:20b"
    corpus_dir: Path = Path("corpus")
    cache_dir: Path = Field(default_factory=_default_cache_dir)

    @property
    def db_path(self) -> Path:
        return self.cache_dir / "results.db"
