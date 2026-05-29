"""Metrics and monitoring API routes.

Provides aggregated execution statistics for the monitoring dashboard.
"""
from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from knot.core.database import get_session
from knot.core.orm_models import ExecutionModel

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])


@router.get("/dashboard")
async def get_dashboard_metrics(
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Return aggregated metrics for the monitoring dashboard.

    Returns:
        dict with keys:
          - total_executions: int
          - execution_counts: dict[str, int]  (by status)
          - success_rate: float  (0-100)
          - avg_duration_ms: float | None
          - top_slow_nodes: list[dict]  (top 5 by avg duration)
          - recent_executions: list[dict]  (last 10)
          - executions_by_day: list[dict]  (last 7 days)
    """
    # ── Fetch all executions (async) ──────────────────────────────────────
    result = await session.execute(
        select(ExecutionModel).order_by(
            ExecutionModel.started_at.desc().nullslast()
        )
    )
    all_execs: list[ExecutionModel] = list(result.scalars().all())

    total = len(all_execs)

    # ── Counts by status ──────────────────────────────────────────────────
    counts: dict[str, int] = {}
    for ex in all_execs:
        st = ex.status or "unknown"
        counts[st] = counts.get(st, 0) + 1

    success_count = counts.get("success", 0)
    failed_count = counts.get("failed", 0)

    success_rate: float = 0.0
    if total > 0:
        success_rate = round((success_count / total) * 100, 2)

    # ── Average duration (milliseconds) ───────────────────────────────────
    durations_ms: list[float] = []
    for ex in all_execs:
        if ex.started_at and ex.completed_at:
            delta = (ex.completed_at - ex.started_at).total_seconds() * 1000
            durations_ms.append(delta)

    avg_duration_ms: float | None = None
    if durations_ms:
        avg_duration_ms = round(sum(durations_ms) / len(durations_ms), 2)

    # ── Top 5 slowest nodes (from trace data) ─────────────────────────────
    # Each trace entry may contain a "duration_ms" field.  We aggregate by
    # node_id / node_label across all executions.
    node_durations: dict[str, dict] = {}
    for ex in all_execs:
        trace_entries = ex.trace_json or []
        for entry in trace_entries:
            dur = entry.get("duration_ms")
            if dur is None:
                continue
            node_id = entry.get("node_id", "unknown")
            node_label = entry.get("node_label") or node_id
            if node_id not in node_durations:
                node_durations[node_id] = {
                    "node_id": node_id,
                    "node_label": node_label,
                    "durations": [],
                    "total_ms": 0.0,
                    "count": 0,
                }
            nd = node_durations[node_id]
            nd["node_label"] = node_label  # use latest label
            nd["durations"].append(dur)
            nd["total_ms"] += dur
            nd["count"] += 1

    top_slow_nodes: list[dict] = []
    for nd in node_durations.values():
        nd["avg_duration_ms"] = round(nd["total_ms"] / nd["count"], 2)
        top_slow_nodes.append(nd)

    top_slow_nodes.sort(key=lambda x: x["avg_duration_ms"], reverse=True)
    top_slow_nodes = top_slow_nodes[:5]

    # ── Recent 10 executions ──────────────────────────────────────────────
    recent_executions: list[dict] = []
    for ex in all_execs[:10]:
        recent_executions.append({
            "id": ex.id,
            "workflow_id": ex.workflow_id,
            "status": ex.status or "unknown",
            "started_at": (
                ex.started_at.isoformat() if ex.started_at else None
            ),
            "completed_at": (
                ex.completed_at.isoformat() if ex.completed_at else None
            ),
            "duration_ms": (
                round(
                    (ex.completed_at - ex.started_at).total_seconds() * 1000,
                    2,
                )
                if ex.started_at and ex.completed_at
                else None
            ),
            "error": ex.error,
        })

    # ── Executions by day (last 7 calendar days) ──────────────────────────
    today = datetime.date.today()
    day_counts: dict[str, int] = {}
    for i in range(6, -1, -1):
        day = today - datetime.timedelta(days=i)
        day_str = day.isoformat()
        day_counts[day_str] = 0

    for ex in all_execs:
        if ex.started_at:
            ex_date = ex.started_at.date()
            key = ex_date.isoformat()
            if key in day_counts:
                day_counts[key] += 1

    executions_by_day = [
        {"date": day_str, "count": count}
        for day_str, count in day_counts.items()
    ]

    return {
        "total_executions": total,
        "execution_counts": counts,
        "success_rate": success_rate,
        "avg_duration_ms": avg_duration_ms,
        "top_slow_nodes": top_slow_nodes,
        "recent_executions": recent_executions,
        "executions_by_day": executions_by_day,
    }
