"""
EcoRouter REST API — JSON endpoints for integrations and edge deployment.

Run locally:
  uvicorn api.server:app --reload --app-dir src --port 8000
"""

from __future__ import annotations

from typing import Any

from agents.ecorouter import _route_jobs
from sim_environment.baseline_scheduler import (
    run_round_robin_scheduler,
    run_static_default_scheduler,
)
from sim_environment.carbon_metrics import compare_schedulers
from sim_environment.grid_data import get_grid_telemetry
from sim_environment.grid_forecast import forecast_grid, recommend_deferral_window
from sim_environment.job_queue import (
    generate_mock_jobs,
    normalize_job,
    parse_jobs_from_csv,
    parse_jobs_from_json,
)


def _resolve_grid(source: str = "simulated") -> dict[str, Any]:
    return get_grid_telemetry(source=source)


def get_status(source: str = "simulated") -> dict[str, Any]:
    telemetry = _resolve_grid(source)
    carbon = telemetry["carbon_gco2_per_kwh"]
    return {
        "grid_status": carbon,
        "cost_usd_per_kwh": telemetry["cost_usd_per_kwh"],
        "data_source": telemetry["source"],
        "greenest_region": telemetry["greenest_region"],
        "greenest_intensity": telemetry["greenest_intensity"],
    }


def get_forecast(hours: int = 12, source: str = "simulated") -> dict[str, Any]:
    telemetry = _resolve_grid(source)
    carbon = telemetry["carbon_gco2_per_kwh"]
    series = forecast_grid(carbon, hours_ahead=hours)
    deferral = recommend_deferral_window(carbon, series)
    return {
        "current": carbon,
        "cost_usd_per_kwh": telemetry["cost_usd_per_kwh"],
        "data_source": telemetry["source"],
        "forecast": series,
        "deferral_recommendation": deferral,
    }


def optimize_jobs(
    num_jobs: int = 4,
    mode: str = "auto",
    use_forecast: bool = False,
    source: str = "simulated",
    jobs: list[dict[str, Any]] | None = None,
    carbon_weight: float = 0.6,
) -> dict[str, Any]:
    telemetry = _resolve_grid(source)
    carbon = telemetry["carbon_gco2_per_kwh"]
    tariffs = telemetry["cost_usd_per_kwh"]
    queue = jobs if jobs is not None else generate_mock_jobs(num_jobs=num_jobs)
    assignments, meta = _route_jobs(
        queue,
        carbon,
        mode=mode,
        use_forecast=use_forecast,
        tariffs=tariffs,
        carbon_weight=carbon_weight,
    )
    return {
        "jobs": queue,
        "grid_status": carbon,
        "cost_usd_per_kwh": tariffs,
        "data_source": telemetry["source"],
        "assignments": assignments,
        "router": meta.get("router"),
        "model": meta.get("model"),
        "deferral": meta.get("deferral"),
        "carbon_weight": meta.get("carbon_weight"),
    }


def submit_custom_jobs(
    payload: dict[str, Any],
    mode: str = "auto",
    use_forecast: bool = False,
    source: str = "simulated",
) -> dict[str, Any]:
    """Route a BYO job queue submitted via JSON body."""
    raw_jobs = payload.get("jobs", [])
    if not raw_jobs:
        raise ValueError("Request body must include a non-empty 'jobs' array.")

    jobs = [normalize_job(j, index=i) for i, j in enumerate(raw_jobs)]
    return optimize_jobs(
        mode=mode,
        use_forecast=use_forecast,
        source=source,
        jobs=jobs,
        carbon_weight=float(payload.get("carbon_weight", 0.6)),
    )


def import_jobs_from_text(
    text: str,
    format: str = "json",
) -> list[dict[str, Any]]:
    if format == "csv":
        return parse_jobs_from_csv(text)
    return parse_jobs_from_json(text)


def compare_baseline(
    num_jobs: int = 4,
    baseline: str = "static",
    mode: str = "auto",
    source: str = "simulated",
    jobs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    telemetry = _resolve_grid(source)
    carbon = telemetry["carbon_gco2_per_kwh"]
    tariffs = telemetry["cost_usd_per_kwh"]
    queue = jobs if jobs is not None else generate_mock_jobs(num_jobs=num_jobs)
    eco_assignments, eco_meta = _route_jobs(
        queue, carbon, mode=mode, tariffs=tariffs
    )

    if baseline == "round_robin":
        baseline_assignments = run_round_robin_scheduler(queue, carbon)
        baseline_name = "Round-Robin"
    else:
        baseline_assignments = run_static_default_scheduler(queue, carbon)
        baseline_name = "Static Default (us-east-1)"

    comparison = compare_schedulers(
        queue,
        carbon,
        eco_assignments,
        baseline_assignments,
        eco_name=eco_meta.get("router", "EcoRouter"),
        baseline_name=baseline_name,
        tariffs=tariffs,
    )
    return {
        "jobs": queue,
        "grid_status": carbon,
        "cost_usd_per_kwh": tariffs,
        "data_source": telemetry["source"],
        "eco_assignments": eco_assignments,
        "baseline_assignments": baseline_assignments,
        "comparison": comparison,
    }
