"""Eval sets, questions, generation, and comparison runs."""

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger("pageindex_test.api.eval")

router = APIRouter(prefix="/api")


class SetRequest(BaseModel):
    name: str


class QuestionRequest(BaseModel):
    question: str
    expected_keywords: list[list[str]] = Field(min_length=1)
    gold_doc_ids: list[str] = Field(min_length=1)


class GenerateRequest(BaseModel):
    per_doc: int = 3
    model: str | None = None


class RunRequest(BaseModel):
    model: str | None = None
    pipelines: list[str] = Field(default=["staged", "hybrid_only"])


def _deps(request: Request):
    return request.app.state.deps


def _active_location(request: Request):
    location = _deps(request).location_service.active()
    if location is None:
        raise HTTPException(status_code=409, detail="No storage location is available")
    return location


def _set_or_404(request: Request, set_id: str) -> dict:
    eval_set = _deps(request).eval_repo.get_set(set_id)
    if eval_set is None:
        raise HTTPException(status_code=404, detail=f"No eval set {set_id}")
    return eval_set


@router.post("/eval-sets", status_code=201)
def create_set(request: Request, body: SetRequest) -> dict:
    deps = _deps(request)
    location = _active_location(request)
    set_id = deps.eval_repo.create_set(location.location_id, body.name)
    return deps.eval_repo.get_set(set_id)


@router.get("/eval-sets")
def list_sets(request: Request) -> dict:
    deps = _deps(request)
    location = _active_location(request)
    sets = deps.eval_repo.list_sets(location.location_id)
    for eval_set in sets:
        questions = deps.eval_repo.questions_for(eval_set["id"])
        eval_set["question_count"] = len(questions)
        eval_set["approved_count"] = sum(1 for q in questions if q["approved"])
    return {"sets": sets}


@router.get("/eval-sets/{set_id}")
def get_set(request: Request, set_id: str) -> dict:
    eval_set = _set_or_404(request, set_id)
    deps = _deps(request)
    eval_set["questions"] = deps.eval_repo.questions_for(set_id)
    eval_set["runs"] = deps.eval_repo.runs_for_set(set_id)
    return eval_set


@router.post("/eval-sets/{set_id}/questions", status_code=201)
def add_question(request: Request, set_id: str, body: QuestionRequest) -> dict:
    _set_or_404(request, set_id)
    question_id = _deps(request).eval_repo.add_question(
        set_id, body.question, body.expected_keywords, body.gold_doc_ids
    )
    return {"id": question_id}


@router.put("/eval-questions/{question_id}/approved")
def set_approved(request: Request, question_id: str, body: dict) -> dict:
    _deps(request).eval_repo.set_approved(question_id, bool(body.get("approved", True)))
    return {"id": question_id, "approved": bool(body.get("approved", True))}


@router.delete("/eval-questions/{question_id}")
def delete_question(request: Request, question_id: str) -> dict:
    _deps(request).eval_repo.delete_question(question_id)
    return {"deleted": question_id}


@router.post("/eval-sets/{set_id}/generate", status_code=202)
def generate_questions(request: Request, set_id: str, body: GenerateRequest) -> dict:
    deps = _deps(request)
    location = _active_location(request)
    _set_or_404(request, set_id)
    model = body.model or deps.settings_repo.get("default_model", deps.settings.default_model)
    job_id = deps.job_repo.enqueue(
        location.location_id,
        "eval_generate",
        {"set_id": set_id, "per_doc": body.per_doc, "model": model},
    )
    return {"job_id": job_id}


@router.post("/eval-sets/{set_id}/runs", status_code=202)
def start_runs(request: Request, set_id: str, body: RunRequest) -> dict:
    deps = _deps(request)
    location = _active_location(request)
    _set_or_404(request, set_id)
    invalid = set(body.pipelines) - {"staged", "hybrid_only"}
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unknown pipelines: {sorted(invalid)}")
    model = body.model or deps.settings_repo.get("default_model", deps.settings.default_model)
    queued = []
    for pipeline in body.pipelines:
        run_id = deps.eval_repo.create_run(set_id, model, pipeline)
        job_id = deps.job_repo.enqueue(location.location_id, "eval_run", {"run_id": run_id})
        queued.append({"run_id": run_id, "pipeline": pipeline, "job_id": job_id})
    logger.info("eval runs queued", extra={"data": {"set_id": set_id, "runs": len(queued)}})
    return {"runs": queued}


@router.get("/eval-runs/{run_id}")
def get_run(request: Request, run_id: str) -> dict:
    deps = _deps(request)
    run = deps.eval_repo.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"No eval run {run_id}")
    run["results"] = deps.eval_repo.results_for_run(run_id)
    return run
