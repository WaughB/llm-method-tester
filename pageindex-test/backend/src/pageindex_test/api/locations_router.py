"""Storage locations and app settings endpoints."""

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger("pageindex_test.api.locations")

router = APIRouter(prefix="/api")

MUTABLE_SETTINGS = {"default_model", "hybrid_top_n", "tree_stage_docs", "use_pageindex_stage"}


class ActivateRequest(BaseModel):
    location_id: str


def _services(request: Request):
    deps = request.app.state.deps
    return deps.location_service, deps.settings_repo


@router.get("/locations")
def list_locations(request: Request) -> dict:
    service, _ = _services(request)
    active = service.active()
    return {
        "locations": [
            dict(loc.as_dict(), active=active is not None and loc.location_id == active.location_id)
            for loc in service.list()
        ]
    }


@router.put("/locations/active")
def activate_location(request: Request, body: ActivateRequest) -> dict:
    service, _ = _services(request)
    try:
        location = service.activate(body.location_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    logger.info("location activated", extra={"data": {"host_label": location.host_label}})
    return location.as_dict()


@router.get("/settings")
def get_settings(request: Request) -> dict:
    deps = request.app.state.deps
    _, repo = _services(request)
    stored = repo.all()
    return {
        "default_model": stored.get("default_model", deps.settings.default_model),
        "hybrid_top_n": stored.get("hybrid_top_n", deps.settings.hybrid_top_n),
        "tree_stage_docs": stored.get("tree_stage_docs", deps.settings.tree_stage_docs),
        "use_pageindex_stage": stored.get("use_pageindex_stage", True),
    }


@router.put("/settings")
def put_settings(request: Request, body: dict) -> dict:
    _, repo = _services(request)
    unknown = set(body) - MUTABLE_SETTINGS
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown settings: {sorted(unknown)}")
    for key, value in body.items():
        repo.set(key, value)
    logger.info("settings updated", extra={"data": body})
    return get_settings(request)
