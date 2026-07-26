"""Log querying for the in-app viewer (and future metrics mining)."""

from fastapi import APIRouter, Request
from sqlalchemy import func, select

from pageindex_test.db.schema import logs

router = APIRouter(prefix="/api")


@router.get("/logs")
def query_logs(
    request: Request,
    level: str | None = None,
    component: str | None = None,
    since: str | None = None,
    until: str | None = None,
    trace_id: str | None = None,
    q: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> dict:
    engine = request.app.state.deps.engine
    query = select(logs).order_by(logs.c.id.desc()).limit(min(limit, 1000)).offset(offset)
    count_query = select(func.count()).select_from(logs)
    conditions = []
    if level:
        conditions.append(logs.c.level == level.upper())
    if component:
        conditions.append(logs.c.component.like(f"{component}%"))
    if since:
        conditions.append(logs.c.ts >= since)
    if until:
        conditions.append(logs.c.ts <= until)
    if trace_id:
        conditions.append(logs.c.trace_id == trace_id)
    if q:
        conditions.append(logs.c.message.like(f"%{q}%"))
    for condition in conditions:
        query = query.where(condition)
        count_query = count_query.where(condition)
    with engine.connect() as conn:
        rows = [dict(r) for r in conn.execute(query).mappings().fetchall()]
        total = conn.execute(count_query).scalar_one()
    return {"logs": rows, "total": total}
