"""FastAPI server for EcoRouter programmatic access."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from api.ecorouter_api import (
    analyze_job,
    compare_baseline,
    get_forecast,
    get_region_matrix,
    get_status,
    list_regions,
    optimize_jobs,
    submit_custom_jobs,
)
from sim_environment.grid_data import MAX_BATCH_JOBS

app = FastAPI(
    title="EcoRouter API",
    description="Carbon-aware AI workload routing — grid telemetry, forecasts, SLA, and optimization.",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class JobPayload(BaseModel):
    job_id: str | None = None
    task: str | None = None
    compute_hours: int | None = Field(None, ge=1)
    is_urgent: bool | None = None
    locality_constraint: str | None = None
    deadline_utc: str | None = None


class JobsRequest(BaseModel):
    jobs: list[JobPayload]
    mode: str = "auto"
    use_forecast: bool = False
    grid_source: str = "simulated"
    carbon_weight: float = Field(0.6, ge=0.0, le=1.0)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ecorouter"}


@app.get("/api/v1/regions")
def regions_catalog() -> dict[str, Any]:
    return list_regions()


@app.get("/api/v1/regions/matrix")
def regions_matrix(
    source: str = Query("simulated", pattern="^(simulated|live)$"),
    carbon_weight: float = Query(0.6, ge=0.0, le=1.0),
) -> dict[str, Any]:
    return get_region_matrix(source=source, carbon_weight=carbon_weight)


@app.post("/api/v1/analyze")
def analyze_workload(
    compute_hours: int = Query(8, ge=1, le=168),
    is_urgent: bool = Query(False),
    locality: str | None = Query(None),
    source: str = Query("simulated", pattern="^(simulated|live)$"),
    carbon_weight: float = Query(0.6, ge=0.0, le=1.0),
) -> dict[str, Any]:
    return analyze_job(
        compute_hours=compute_hours,
        is_urgent=is_urgent,
        locality=locality,
        source=source,
        carbon_weight=carbon_weight,
    )


@app.get("/api/v1/grid")
def grid_status(
    source: str = Query("simulated", pattern="^(simulated|live)$"),
) -> dict[str, Any]:
    return get_status(source=source)


@app.get("/api/v1/forecast")
def grid_forecast(
    hours: int = Query(12, ge=1, le=24),
    source: str = Query("simulated", pattern="^(simulated|live)$"),
) -> dict[str, Any]:
    return get_forecast(hours=hours, source=source)


@app.post("/api/v1/optimize")
def optimize(
    num_jobs: int = Query(4, ge=1, le=MAX_BATCH_JOBS),
    mode: str = Query(
        "auto",
        pattern="^(auto|mock|gemini|forecast|cost_aware|pareto|load_balanced)$",
    ),
    use_forecast: bool = Query(False),
    source: str = Query("simulated", pattern="^(simulated|live)$"),
    carbon_weight: float = Query(0.6, ge=0.0, le=1.0),
) -> dict[str, Any]:
    return optimize_jobs(
        num_jobs=num_jobs,
        mode=mode,
        use_forecast=use_forecast or mode == "forecast",
        source=source,
        carbon_weight=carbon_weight,
    )


@app.post("/api/v1/jobs")
def route_custom_jobs(body: JobsRequest) -> dict[str, Any]:
    """Submit a custom job queue (BYO) for carbon-aware routing."""
    try:
        return submit_custom_jobs(
            payload={
                **body.model_dump(),
                "carbon_weight": body.carbon_weight,
            },
            mode=body.mode,
            use_forecast=body.use_forecast,
            source=body.grid_source,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/compare")
def compare(
    num_jobs: int = Query(4, ge=1, le=MAX_BATCH_JOBS),
    baseline: str = Query("static", pattern="^(static|round_robin)$"),
    mode: str = Query(
        "auto",
        pattern="^(auto|mock|gemini|forecast|cost_aware|pareto|load_balanced)$",
    ),
    source: str = Query("simulated", pattern="^(simulated|live)$"),
) -> dict[str, Any]:
    return compare_baseline(
        num_jobs=num_jobs,
        baseline=baseline,
        mode=mode,
        source=source,
    )
