"""Settings and mount-root parsing tests."""

from pathlib import Path

import pytest

from pageindex_test.config import Settings, parse_mount_roots


class TestParseMountRoots:
    def test_parses_container_host_pairs(self) -> None:
        roots = parse_mount_roots(r"/mnt/store0=C:\Users\brett\Desktop;/mnt/store1=E:\docs")
        assert len(roots) == 2
        assert roots[0].container_path == Path("/mnt/store0")
        assert roots[0].host_label == r"C:\Users\brett\Desktop"
        assert roots[1].host_label == r"E:\docs"

    def test_windows_colons_survive(self) -> None:
        [root] = parse_mount_roots(r"/mnt/store0=D:\my archive")
        assert root.host_label == r"D:\my archive"

    def test_missing_label_falls_back_to_container_path(self) -> None:
        [root] = parse_mount_roots("/mnt/store0")
        assert root.host_label == "/mnt/store0"

    def test_empty_and_blank_entries_skipped(self) -> None:
        assert parse_mount_roots("") == []
        assert parse_mount_roots(";;") == []


class TestSettings:
    def test_defaults(self, settings: Settings) -> None:
        assert settings.default_model == "llama3.1:8b"
        assert settings.embedding_model == "nomic-embed-text"
        assert settings.tree_num_ctx == 16384

    def test_mount_roots_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PIT_MOUNT_ROOTS", r"/mnt/store0=C:\Users\brett\Desktop")
        settings = Settings(_env_file=None)
        assert len(settings.mount_roots) == 1
        assert settings.mount_roots[0].host_label == r"C:\Users\brett\Desktop"
