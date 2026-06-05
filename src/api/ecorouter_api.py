"""
EcoRouter REST API — JSON endpoints for integrations and edge deployment.

Run locally:
  uvicorn api.server:app --reload --app-dir src --port 8000
"""

from __future__ import annotations

from typing import Any

from agents.ecorouter import _route_jobs, run_forecast_aware_router
from sim_environment.baseline_scheduler import (
    run_round_robin_scheduler,
    run_static_default_scheduler,
)
from sim_environment.carbon_metrics import compare_schedulers
from sim_environment.grid_data import get_live_grid_status
from sim_environment.grid_forecast import forecast_grid, recommend_deferral_window
from sim_environment.job_queue import generate_mock_jobs


def get_status() -> dict[str, Any]:
    grid = get_live_grid_status()
    greenest = min(grid, key=grid.get)
    return {
        "grid_status": grid,
        "greenest_region": greenest,
        "greenest_intensity": grid[greenest],
    }


def get_forecast(hours: int = 12) -> dict[str, Any]:
    grid = get_live_grid_status()
    series = forecast_grid(grid, hours_ahead=hours)
    deferral = recommend_deferral_window(grid, series)
    return {"current": grid, "forecast": series, "deferral_recommendation": deferral}


def optimize_jobs(
    num_jobs: int = 4,
    mode: str = "auto",
    use_forecast: bool = False,
) -> dict[str, Any]:
    grid = get_live_grid_status()
    jobs = generate_mock_jobs(num_jobs=num_jobs)
    assignments, meta = _route_jobs(jobs, grid, mode=mode, use_forecast=use_forecast)
    return {
        "jobs": jobs,
        "grid_status": grid,
        "assignments": assignments,
        "router": meta.get("router"),
        "model": meta.get("model"),
        "deferral": meta.get("deferral"),
    }


def compare_baseline(
    num_jobs: int = 4,
    baseline: str = "static",
    mode: str = "auto",
) -> dict[str, Any]:
    grid = get_live_grid_status()
    jobs = generate_mock_jobs(num_jobs=num_jobs)
    eco_assignments, eco_meta = _route_jobs(jobs, grid, mode=mode)

    if baseline == "round_robin":
        baseline_assignments = run_round_robin_scheduler(jobs, grid)
        baseline_name = "Round-Robin"
    else:
        baseline_assignments = run_static_default_scheduler(jobs, grid)
        baseline_name = "Static Default (us-east-1)"

    comparison = compare_schedulers(
        jobs,
        grid,
        eco_assignments,
        baseline_assignments,
        eco_name=eco_meta.get("router", "EcoRouter"),
        baseline_name=baseline_name,
    )
    return {
        "jobs": jobs,
        "grid_status": grid,
        "eco_assignments": eco_assignments,
        "baseline_assignments": baseline_assignments,
        "comparison": comparison,
    }
