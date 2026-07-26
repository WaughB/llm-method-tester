"""Conversations, messages (query execution), and trace retrieval."""

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger("pageindex_test.api.chat")

router = APIRouter(prefix="/api")


class ConversationRequest(BaseModel):
    title: str | None = None
    model: str | None = None


class MessageRequest(BaseModel):
    question: str
    use_pageindex_stage: bool | None = None


def _deps(request: Request):
    return request.app.state.deps


def _active_location(request: Request):
    location = _deps(request).location_service.active()
    if location is None:
        raise HTTPException(status_code=409, detail="No storage location is available")
    return location


@router.post("/conversations", status_code=201)
def create_conversation(request: Request, body: ConversationRequest) -> dict:
    deps = _deps(request)
    location = _active_location(request)
    model = body.model or deps.settings_repo.get("default_model", deps.settings.default_model)
    conversation_id = deps.conversation_repo.create(
        location.location_id, body.title or "New conversation", model
    )
    return deps.conversation_repo.get(conversation_id)


@router.get("/conversations")
def list_conversations(request: Request) -> dict:
    deps = _deps(request)
    location = _active_location(request)
    return {"conversations": deps.conversation_repo.list_for_location(location.location_id)}


@router.get("/conversations/{conversation_id}")
def get_conversation(request: Request, conversation_id: str) -> dict:
    deps = _deps(request)
    conversation = deps.conversation_repo.get(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail=f"No conversation {conversation_id}")
    conversation["messages"] = deps.conversation_repo.messages_for(conversation_id)
    return conversation


@router.post("/conversations/{conversation_id}/messages")
def post_message(request: Request, conversation_id: str, body: MessageRequest) -> dict:
    deps = _deps(request)
    location = _active_location(request)
    conversation = deps.conversation_repo.get(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail=f"No conversation {conversation_id}")
    use_stage = (
        body.use_pageindex_stage
        if body.use_pageindex_stage is not None
        else bool(conversation.get("use_pageindex_stage", True))
    )

    # BM25 rebuilds from the chunk table per query: milliseconds at prototype
    # scale, and the API process never goes stale against worker ingests.
    deps.lexical_index.rebuild(deps.chunk_repo.for_location(location.location_id))

    result = deps.query_pipeline.ask(
        location.location_id,
        body.question,
        conversation["model"],
        use_pageindex_stage=use_stage,
    )
    deps.conversation_repo.add_message(conversation_id, "user", body.question)
    deps.conversation_repo.add_message(
        conversation_id,
        "assistant",
        result.answer,
        citations=[c.as_dict() for c in result.citations],
        trace_id=result.trace_id,
    )
    return {
        "answer": result.answer,
        "citations": [c.as_dict() for c in result.citations],
        "trace_id": result.trace_id,
        "pipeline": result.pipeline,
        "total_ms": result.total_ms,
        "stages": result.stages,
    }


@router.get("/traces/{trace_id}")
def get_trace(request: Request, trace_id: str) -> dict:
    trace = _deps(request).trace_repo.get(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail=f"No trace {trace_id}")
    return trace
