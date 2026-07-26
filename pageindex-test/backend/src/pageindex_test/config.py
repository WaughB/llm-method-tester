"""Settings for pageindex-test. Env prefix PIT_, .env supported.

`mount_roots` maps container paths to host display labels, parsed from
"PIT_MOUNT_ROOTS=/mnt/store0=C:\\Users\\brett\\Desktop;/mnt/store1=E:\\docs".
Semicolon separation because Windows paths contain colons.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MountRoot:
    """One user-selectable storage root: where it is in the container and
    what the host calls it (display only — the container can't see host paths)."""

    def __init__(self, container_path: str, host_label: str) -> None:
        self.container_path = Path(container_path)
        self.host_label = host_label or container_path

    def __repr__(self) -> str:  # pragma: no cover
        return f"MountRoot({self.container_path}, {self.host_label!r})"


def parse_mount_roots(raw: str) -> list[MountRoot]:
    roots = []
    for entry in raw.split(";"):
        entry = entry.strip()
        if not entry:
            continue
        container, sep, host = entry.partition("=")
        if not container.strip():
            continue
        roots.append(MountRoot(container.strip(), host.strip() if sep else ""))
    return roots


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PIT_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://pageindex:pageindex@localhost:5433/pageindex"
    qdrant_url: str = "http://localhost:6333"
    ollama_base_url: str = "http://localhost:11434"
    request_timeout_s: float = 600.0

    default_model: str = "llama3.1:8b"
    embedding_model: str = "nomic-embed-text"
    judge_model: str = "gpt-oss:20b"
    tree_num_ctx: int = 16384

    mount_roots_raw: str = Field(default="", alias="PIT_MOUNT_ROOTS")
    frontend_dist: Path | None = None

    # pipeline knobs
    hybrid_top_n: int = 8
    tree_stage_docs: int = 4
    log_retention_days: int = 30

    @property
    def mount_roots(self) -> list[MountRoot]:
        return parse_mount_roots(self.mount_roots_raw)
