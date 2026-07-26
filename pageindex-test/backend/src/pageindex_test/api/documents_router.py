"""Document upload/import, listing, deletion, and job visibility."""

import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, UploadFile
from pydantic import BaseModel

from pageindex_test.ingest.extract import SUPPORTED_SUFFIXES
from pageindex_test.locations import library_dir

logger = logging.getLogger("pageindex_test.api.documents")

router = APIRouter(prefix="/api")


class ImportRequest(BaseModel):
    path: str  # relative to the active storage root


def _deps(request: Request):
    return request.app.state.deps


def _active_location(request: Request):
    location = _deps(request).location_service.active()
    if location is None:
        raise HTTPException(status_code=409, detail="No storage location is available")
    return location


def doc_dir(location, doc_id: str) -> Path:
    return library_dir(location) / "docs" / doc_id


@router.post("/documents", status_code=202)
async def upload_document(request: Request, file: UploadFile) -> dict:
    deps = _deps(request)
    location = _active_location(request)
    suffix = Path(file.filename or "upload").suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type {suffix!r} — supported: PDF, Markdown, TXT",
        )
    doc_id = deps.document_repo.create(
        location.location_id, file.filename or "upload", suffix.lstrip(".")
    )
    target = doc_dir(location, doc_id) / f"original{suffix}"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    job_id = deps.job_repo.enqueue(
        location.location_id,
        "ingest",
        {"doc_id": doc_id, "source": str(target), "extracted": str(target.parent / "extracted.md")},
    )
    logger.info(
        "document uploaded",
        extra={"data": {"doc_id": doc_id, "filename": file.filename, "job_id": job_id}},
    )
    return {"doc_id": doc_id, "job_id": job_id}


@router.post("/documents/import", status_code=202)
def import_documents(request: Request, body: ImportRequest) -> dict:
    """Bulk-ingest files already under the active storage root."""
    deps = _deps(request)
    location = _active_location(request)
    base = Path(location.container_path)
    target = (base / body.path).resolve()
    if not str(target).startswith(str(base.resolve())):
        raise HTTPException(status_code=400, detail="Path escapes the storage root")
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"No such path under root: {body.path}")
    files = (
        [target]
        if target.is_file()
        else [p for p in sorted(target.rglob("*")) if p.suffix.lower() in SUPPORTED_SUFFIXES]
    )
    if not files:
        raise HTTPException(status_code=404, detail="No supported documents found at that path")
    queued = []
    for source in files:
        doc_id = deps.document_repo.create(
            location.location_id, source.name, source.suffix.lower().lstrip(".")
        )
        job_id = deps.job_repo.enqueue(
            location.location_id,
            "ingest",
            {
                "doc_id": doc_id,
                "source": str(source),
                "extracted": str(doc_dir(location, doc_id) / "extracted.md"),
            },
        )
        queued.append({"doc_id": doc_id, "job_id": job_id, "filename": source.name})
    logger.info("import queued", extra={"data": {"count": len(queued), "path": body.path}})
    return {"queued": queued}


@router.get("/documents")
def list_documents(request: Request) -> dict:
    deps = _deps(request)
    location = _active_location(request)
    return {"documents": deps.document_repo.list_for_location(location.location_id)}


@router.get("/documents/{doc_id}")
def get_document(request: Request, doc_id: str) -> dict:
    doc = _deps(request).document_repo.get(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"No document {doc_id}")
    return doc


@router.delete("/documents/{doc_id}")
def delete_document(request: Request, doc_id: str) -> dict:
    deps = _deps(request)
    location = _active_location(request)
    doc = deps.document_repo.get(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"No document {doc_id}")
    deps.vector_index_factory(location.location_id).delete_doc(doc_id)
    deps.document_repo.delete(doc_id)
    shutil.rmtree(doc_dir(location, doc_id), ignore_errors=True)
    logger.info("document deleted", extra={"data": {"doc_id": doc_id}})
    return {"deleted": doc_id}


@router.get("/jobs")
def list_jobs(request: Request, status: str | None = None) -> dict:
    return {"jobs": _deps(request).job_repo.list_recent(status=status)}


@router.get("/jobs/{job_id}")
def get_job(request: Request, job_id: int) -> dict:
    job = _deps(request).job_repo.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"No job {job_id}")
    return job
