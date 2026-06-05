"""FastAPI server for EcoRouter programmatic access."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from api.ecorouter_api import compare_baseline, get_forecast, get_status, optimize_jobs

app = FastAPI(
    title="EcoRouter API",
    description="Carbon-aware AI workload routing — grid telemetry, forecasts, and optimization.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ecorouter"}


@app.get("/api/v1/grid")
def grid_status() -> dict[str, Any]:
    return get_status()


@app.get("/api/v1/forecast")
def grid_forecast(hours: int = Query(12, ge=1, le=24)) -> dict[str, Any]:
    return get_forecast(hours=hours)


@app.post("/api/v1/optimize")
def optimize(
    num_jobs: int = Query(4, ge=1, le=20),
    mode: str = Query("auto", pattern="^(auto|mock|gemini|forecast)$"),
    use_forecast: bool = Query(False),
) -> dict[str, Any]:
    return optimize_jobs(num_jobs=num_jobs, mode=mode, use_forecast=use_forecast or mode == "forecast")


@app.get("/api/v1/compare")
def compare(
    num_jobs: int = Query(4, ge=1, le=20),
    baseline: str = Query("static", pattern="^(static|round_robin)$"),
    mode: str = Query("auto", pattern="^(auto|mock|gemini|forecast)$"),
) -> dict[str, Any]:
    return compare_baseline(num_jobs=num_jobs, baseline=baseline, mode=mode)
