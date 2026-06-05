"""Carbon and electricity cost accounting."""

from __future__ import annotations

from typing import Any

from sim_environment.grid_data import REGIONS, REGION_TARIFFS_USD


def job_carbon_cost(
    job: dict[str, Any],
    grid_status: dict[str, int],
    target_region: str,
) -> int:
    return grid_status.get(target_region, 0) * job.get("compute_hours", 0)


def job_energy_cost_usd(
    job: dict[str, Any],
    tariffs: dict[str, float],
    target_region: str,
) -> float:
    rate = tariffs.get(target_region, REGION_TARIFFS_USD.get(target_region, 0.10))
    return round(rate * job.get("compute_hours", 0), 2)


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


def total_energy_cost_usd(
    jobs: list[dict[str, Any]],
    tariffs: dict[str, float],
    assignments: list[dict[str, Any]],
) -> float:
    by_job = {a["job_id"]: a["target_region"] for a in assignments}
    return round(
        sum(
            job_energy_cost_usd(job, tariffs, by_job[job["job_id"]])
            for job in jobs
            if job["job_id"] in by_job
        ),
        2,
    )


def per_job_breakdown(
    jobs: list[dict[str, Any]],
    grid_status: dict[str, int],
    assignments: list[dict[str, Any]],
    scheduler_name: str,
    tariffs: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    tariffs = tariffs or REGION_TARIFFS_USD
    by_job = {a["job_id"]: a for a in assignments}
    rows: list[dict[str, Any]] = []
    for job in jobs:
        a = by_job.get(job["job_id"])
        if not a:
            continue
        region = a["target_region"]
        rows.append(
            {
                "job_id": job["job_id"],
                "task": job["task"],
                "scheduler": scheduler_name,
                "target_region": region,
                "compute_hours": job["compute_hours"],
                "carbon_gco2": job_carbon_cost(job, grid_status, region),
                "cost_usd": job_energy_cost_usd(job, tariffs, region),
                "is_urgent": job.get("is_urgent"),
                "locality_constraint": job.get("locality_constraint"),
                "deadline_utc": job.get("deadline_utc"),
                "sla_met": a.get("sla_met", True),
                "deferred": a.get("deferred", False),
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
    tariffs: dict[str, float] | None = None,
) -> dict[str, Any]:
    tariffs = tariffs or REGION_TARIFFS_USD
    eco_total = total_carbon_cost(jobs, grid_status, eco_assignments)
    baseline_total = total_carbon_cost(jobs, grid_status, baseline_assignments)
    carbon_saved = baseline_total - eco_total
    carbon_pct = (carbon_saved / baseline_total * 100) if baseline_total > 0 else 0.0

    eco_cost = total_energy_cost_usd(jobs, tariffs, eco_assignments)
    baseline_cost = total_energy_cost_usd(jobs, tariffs, baseline_assignments)
    cost_saved = round(baseline_cost - eco_cost, 2)
    cost_pct = (cost_saved / baseline_cost * 100) if baseline_cost > 0 else 0.0

    tradeoff = _classify_tradeoff(carbon_saved, cost_saved)

    return {
        "eco_name": eco_name,
        "baseline_name": baseline_name,
        "eco_total_gco2": eco_total,
        "baseline_total_gco2": baseline_total,
        "carbon_saved_gco2": carbon_saved,
        "savings_pct": round(carbon_pct, 1),
        "eco_total_cost_usd": eco_cost,
        "baseline_total_cost_usd": baseline_cost,
        "cost_saved_usd": cost_saved,
        "cost_savings_pct": round(cost_pct, 1),
        "tradeoff_type": tradeoff["type"],
        "tradeoff_message": tradeoff["message"],
        "eco_per_job": per_job_breakdown(jobs, grid_status, eco_assignments, eco_name, tariffs),
        "baseline_per_job": per_job_breakdown(jobs, grid_status, baseline_assignments, baseline_name, tariffs),
    }


def _classify_tradeoff(carbon_saved: int, cost_saved: float) -> dict[str, str]:
    """Label carbon vs cost outcome for dashboard messaging."""
    if carbon_saved > 0 and cost_saved > 0:
        return {
            "type": "win_win",
            "message": (
                "Win-win: EcoRouter reduced both carbon and energy cost vs baseline. "
                "This is the ideal outcome for ESG and FinOps teams."
            ),
        }
    if carbon_saved > 0 and cost_saved < 0:
        return {
            "type": "carbon_tradeoff",
            "message": (
                "Carbon-first tradeoff: emissions fell but energy cost increased because "
                "greener regions (e.g. EU) can have higher $/kWh than the baseline default. "
                "Try **Pareto** or **Cost-aware** routing to balance both objectives."
            ),
        }
    if carbon_saved > 0 and cost_saved == 0:
        return {
            "type": "carbon_neutral_cost",
            "message": "Carbon improved with no net cost change vs baseline.",
        }
    if carbon_saved <= 0 and cost_saved > 0:
        return {
            "type": "cost_only",
            "message": "Cost improved; carbon matched or increased (often due to locality locks).",
        }
    return {
        "type": "no_gain",
        "message": (
            "No net savings — likely all jobs had locality constraints or baseline "
            "already matched the routing policy."
        ),
    }
