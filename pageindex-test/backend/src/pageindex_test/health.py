"""Dependency health probes for /api/meta — every failure mode visible."""

import httpx
from llm_bench.wiring import check_ollama
from sqlalchemy import Engine, text


def check_database(engine: Engine) -> dict:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def check_qdrant(base_url: str, transport: httpx.BaseTransport | None = None) -> dict:
    try:
        with httpx.Client(base_url=base_url, timeout=5.0, transport=transport) as client:
            response = client.get("/readyz")
            return {"ok": response.status_code == 200}
    except httpx.HTTPError as exc:
        return {"ok": False, "error": str(exc)}


def check_ollama_models(base_url: str, required: list[str]) -> dict:
    result = check_ollama(base_url)
    if not result["ok"]:
        return result
    have = result["models"]
    # "nomic-embed-text" should match the pulled tag "nomic-embed-text:latest"
    missing = [m for m in required if not any(h == m or h.startswith(f"{m}:") for h in have)]
    return {"ok": not missing, "models": have, "missing": missing}
