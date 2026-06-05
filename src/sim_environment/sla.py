"""SLA deadline validation for routing and deferral decisions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def parse_deadline(deadline_str: str | None) -> datetime | None:
    if not deadline_str:
        return None
    text = str(deadline_str).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def hours_until_deadline(job: dict[str, Any], now: datetime | None = None) -> float | None:
    deadline = parse_deadline(job.get("deadline_utc"))
    if not deadline:
        return None
    now = now or datetime.now(timezone.utc)
    return (deadline - now).total_seconds() / 3600


def can_defer(job: dict[str, Any], defer_hours: float, now: datetime | None = None) -> bool:
    """
    A job may defer only if:
    - compute_hours + defer_hours still finishes before deadline
    - at least defer_hours remain until deadline
    """
    remaining = hours_until_deadline(job, now)
    if remaining is None:
        return True
    compute = job.get("compute_hours", 0)
    return defer_hours + compute <= remaining


def enforce_sla_on_assignment(
    job: dict[str, Any],
    assignment: dict[str, Any],
) -> dict[str, Any]:
    """Annotate assignment with sla_met; cancel deferral if it would breach deadline."""
    result = dict(assignment)
    defer_hours = float(result.get("defer_hours") or 0)
    deferred = bool(result.get("deferred"))

    if deferred and defer_hours > 0 and not can_defer(job, defer_hours):
        result["deferred"] = False
        result["defer_hours"] = 0
        result["sla_met"] = True
        result["reasoning"] = (
            f"{result.get('reasoning', '')} "
            f"[SLA] Deferral cancelled — {defer_hours:.0f}h wait would breach deadline "
            f"{job.get('deadline_utc')}."
        ).strip()
    else:
        remaining = hours_until_deadline(job)
        compute = job.get("compute_hours", 0)
        if remaining is not None:
            result["sla_met"] = compute <= remaining
            if deferred:
                result["sla_met"] = (defer_hours + compute) <= remaining
        else:
            result["sla_met"] = True

    return result


def apply_sla_to_assignments(
    jobs: list[dict[str, Any]],
    assignments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_id = {j["job_id"]: j for j in jobs}
    return [
        enforce_sla_on_assignment(by_id[a["job_id"]], a)
        for a in assignments
        if a["job_id"] in by_id
    ]
