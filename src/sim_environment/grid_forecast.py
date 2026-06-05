"""Predictive carbon-intensity forecasting for proactive job scheduling."""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone
from typing import Any

from sim_environment.grid_data import BASE_INTENSITIES, REGIONS

# Diurnal renewable boost by region (solar/wind midday dip in carbon)
_RENEWABLE_PROFILE: dict[str, float] = {
    "us-east-1": 0.85,
    "us-west-2": 1.35,
    "eu-central-1": 1.15,
    "ap-south-1": 0.65,
}


def forecast_grid(
    current_status: dict[str, int],
    hours_ahead: int = 12,
    step_hours: int = 1,
) -> list[dict[str, Any]]:
    """
    Project carbon intensity per region over the next N hours.

    Uses diurnal solar curves + mean-reversion toward regional baselines + noise.
    Returns chronologically sorted snapshots:
      [{"hours_ahead": 0, "timestamp": "...", "regions": {...}}, ...]
    """
    now = datetime.now(timezone.utc)
    series: list[dict[str, Any]] = []

    for h in range(0, hours_ahead + 1, step_hours):
        hour_of_day = (now.hour + h) % 24
        # Carbon dips when solar output peaks (~10:00–14:00 local proxy)
        solar_adjust = -28 * math.sin((hour_of_day - 6) * math.pi / 12)

        regions: dict[str, int] = {}
        for region in REGIONS:
            current = current_status.get(region, BASE_INTENSITIES[region])
            baseline = BASE_INTENSITIES[region]
            profile = _RENEWABLE_PROFILE.get(region, 1.0)
            drift = (baseline - current) // 12
            noise = random.randint(-6, 6) * max(1, h // 3)
            value = int(current + solar_adjust * profile + drift + noise)
            regions[region] = max(80, min(650, value))

        series.append(
            {
                "hours_ahead": h,
                "timestamp": (now + timedelta(hours=h)).strftime("%Y-%m-%d %H:%M UTC"),
                "regions": regions,
            }
        )

    return series


def greenest_at_horizon(forecast: list[dict[str, Any]], hours_ahead: int) -> tuple[str, int]:
    """Return (region, intensity) at a specific forecast horizon."""
    entry = next((s for s in forecast if s["hours_ahead"] == hours_ahead), forecast[-1])
    regions = entry["regions"]
    best = min(regions, key=regions.get)
    return best, regions[best]


def recommend_deferral_window(
    current_status: dict[str, int],
    forecast: list[dict[str, Any]],
    min_savings_pct: float = 12.0,
) -> dict[str, Any]:
    """
    Suggest whether flexible workloads should wait for a greener window.

    Compares current greenest intensity vs best intensity within the 12h forecast.
    """
    current_greenest = min(current_status, key=current_status.get)
    current_intensity = current_status[current_greenest]

    best_horizon = 0
    best_region = current_greenest
    best_intensity = current_intensity

    for snap in forecast:
        if snap["hours_ahead"] == 0:
            continue
        region, intensity = greenest_at_horizon(forecast, snap["hours_ahead"])
        if intensity < best_intensity:
            best_intensity = intensity
            best_region = region
            best_horizon = snap["hours_ahead"]

    savings_pct = (
        ((current_intensity - best_intensity) / current_intensity) * 100
        if current_intensity > 0
        else 0.0
    )
    should_defer = savings_pct >= min_savings_pct

    return {
        "should_defer": should_defer,
        "current_greenest": current_greenest,
        "current_intensity": current_intensity,
        "recommended_region": best_region,
        "recommended_intensity": best_intensity,
        "recommended_hours_ahead": best_horizon,
        "estimated_savings_pct": round(savings_pct, 1),
        "rationale": (
            f"Defer flexible jobs {best_horizon}h to {best_region} "
            f"({best_intensity} vs {current_intensity} gCO₂/kWh now, ~{savings_pct:.0f}% greener)."
            if should_defer
            else "No meaningful greener window in the next 12h; dispatch now."
        ),
    }


def forecast_to_dataframe(forecast: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten forecast series for charting (one row per region × hour)."""
    rows: list[dict[str, Any]] = []
    for snap in forecast:
        for region in REGIONS:
            rows.append(
                {
                    "Hours Ahead": snap["hours_ahead"],
                    "Timestamp": snap["timestamp"],
                    "Region": region,
                    "Carbon Intensity (gCO₂/kWh)": snap["regions"][region],
                }
            )
    return rows
