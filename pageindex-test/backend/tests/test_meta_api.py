"""API tests for /api/meta with injected health probes."""

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from pageindex_test.config import Settings
from pageindex_test.health import check_database, check_ollama_models, check_qdrant
from pageindex_test.main import AppDeps, create_app


def make_client(engine: Engine, settings: Settings, probes: dict) -> TestClient:
    return TestClient(create_app(AppDeps(settings=settings, engine=engine, health_probes=probes)))


class TestMeta:
    def test_all_green(self, engine: Engine, settings: Settings) -> None:
        client = make_client(
            engine,
            settings,
            {"database": lambda: {"ok": True}, "ollama": lambda: {"ok": True}},
        )
        data = client.get("/api/meta").json()
        assert data["ok"] is True
        assert data["default_model"] == "llama3.1:8b"
        assert data["checks"]["database"]["ok"] is True

    def test_one_red_flips_overall(self, engine: Engine, settings: Settings) -> None:
        client = make_client(
            engine,
            settings,
            {"database": lambda: {"ok": True}, "qdrant": lambda: {"ok": False, "error": "down"}},
        )
        data = client.get("/api/meta").json()
        assert data["ok"] is False
        assert data["checks"]["qdrant"]["error"] == "down"


class TestProbes:
    def test_database_probe_ok(self, engine: Engine) -> None:
        assert check_database(engine) == {"ok": True}

    def test_qdrant_probe(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/readyz"
            return httpx.Response(200, text="ok")

        assert check_qdrant("http://q", transport=httpx.MockTransport(handler)) == {"ok": True}

    def test_qdrant_probe_down(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("refused")

        result = check_qdrant("http://q", transport=httpx.MockTransport(handler))
        assert result["ok"] is False

    def test_ollama_models_probe_flags_missing(self, monkeypatch) -> None:
        import pageindex_test.health as health

        monkeypatch.setattr(
            health,
            "check_ollama",
            lambda base_url: {"ok": True, "models": ["llama3.1:8b", "nomic-embed-text:latest"]},
        )
        result = check_ollama_models("http://o", ["llama3.1:8b", "nomic-embed-text", "gpt-oss:20b"])
        assert result["missing"] == ["gpt-oss:20b"]
        assert result["ok"] is False
