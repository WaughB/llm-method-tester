"""Composition-root and CLI wiring tests (SQLite stands in for Postgres)."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from pageindex_test.cli import app
from pageindex_test.config import Settings
from pageindex_test.main import build_deps, create_app

runner = CliRunner()


class TestBuildDeps:
    def test_builds_full_graph_on_sqlite(self, tmp_path: Path) -> None:
        settings = Settings(
            _env_file=None,
            database_url=f"sqlite+pysqlite:///{tmp_path / 'app.db'}",
        )
        deps = build_deps(settings)
        assert set(deps.health_probes) == {"database", "qdrant", "ollama"}
        assert deps.health_probes["database"]() == {"ok": True}
        assert deps.frontend_dist is None  # not built yet

    def test_frontend_dist_mounted_when_present(self, tmp_path: Path) -> None:
        dist = tmp_path / "dist"
        dist.mkdir()
        (dist / "index.html").write_text("<html></html>", encoding="utf-8")
        settings = Settings(
            _env_file=None,
            database_url=f"sqlite+pysqlite:///{tmp_path / 'app.db'}",
            frontend_dist=dist,
        )
        deps = build_deps(settings)
        assert deps.frontend_dist == dist
        client_app = create_app(deps)
        routes = [getattr(r, "name", "") for r in client_app.routes]
        assert "frontend" in routes


class TestCli:
    def test_help_lists_commands(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        for command in ("serve", "worker", "init-db"):
            assert command in result.output

    def test_init_db_on_sqlite(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PIT_DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 'cli.db'}")
        result = runner.invoke(app, ["init-db"])
        assert result.exit_code == 0
        assert "Schema initialized." in result.output
        assert (tmp_path / "cli.db").exists()
