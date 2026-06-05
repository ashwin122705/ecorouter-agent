"""Carbon accounting and scheduler comparison metrics."""

from __future__ import annotations

from typing import Any

from sim_environment.grid_data import REGIONS


def job_carbon_cost(
    job: dict[str, Any],
    grid_status: dict[str, int],
    target_region: str,
) -> int:
    """Estimated gCO₂ for a job: intensity × compute_hours."""
    return grid_status.get(target_region, 0) * job.get("compute_hours", 0)


def total_carbon_cost(
    jobs: list[dict[str, Any]],
    grid_status: dict[str, int],
    assignments: list[dict[str, Any]],
) -> int:
    by_job = {a["job_id"]: a["target_region"] for a in assignments}
    return sum(
        job_carbon_cost(job, grid_status, by_job[job["job_id"]])
        for job in jobs
        if job["job_id"] in by_job
    )


def per_job_breakdown(
    jobs: list[dict[str, Any]],
    grid_status: dict[str, int],
    assignments: list[dict[str, Any]],
    scheduler_name: str,
) -> list[dict[str, Any]]:
    by_job = {a["job_id"]: a for a in assignments}
    rows: list[dict[str, Any]] = []
    for job in jobs:
        a = by_job.get(job["job_id"])
        if not a:
            continue
        region = a["target_region"]
        carbon = job_carbon_cost(job, grid_status, region)
        rows.append(
            {
                "job_id": job["job_id"],
                "task": job["task"],
                "scheduler": scheduler_name,
                "target_region": region,
                "compute_hours": job["compute_hours"],
                "carbon_gco2": carbon,
                "is_urgent": job.get("is_urgent"),
                "locality_constraint": job.get("locality_constraint"),
            }
        )
    return rows


def compare_schedulers(
    jobs: list[dict[str, Any]],
    grid_status: dict[str, int],
    eco_assignments: list[dict[str, Any]],
    baseline_assignments: list[dict[str, Any]],
    eco_name: str = "EcoRouter",
    baseline_name: str = "Baseline",
) -> dict[str, Any]:
    eco_total = total_carbon_cost(jobs, grid_status, eco_assignments)
    baseline_total = total_carbon_cost(jobs, grid_status, baseline_assignments)
    saved = baseline_total - eco_total
    pct = (saved / baseline_total * 100) if baseline_total > 0 else 0.0

    return {
        "eco_name": eco_name,
        "baseline_name": baseline_name,
        "eco_total_gco2": eco_total,
        "baseline_total_gco2": baseline_total,
        "carbon_saved_gco2": saved,
        "savings_pct": round(pct, 1),
        "eco_per_job": per_job_breakdown(jobs, grid_status, eco_assignments, eco_name),
        "baseline_per_job": per_job_breakdown(jobs, grid_status, baseline_assignments, baseline_name),
    }
