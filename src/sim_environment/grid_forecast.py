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
    "us-east-2": 0.80,
    "us-west-1": 1.25,
    "us-west-2": 1.35,
    "eu-west-1": 1.20,
    "eu-central-1": 1.15,
    "eu-north-1": 1.45,
    "ap-northeast-1": 0.75,
    "ap-south-1": 0.65,
    "sa-east-1": 1.10,
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
        solar_adjust = -28 * math.sin((hour_of_day - 6) * math.pi / 12)

        regions: dict[str, int] = {}
        for region in REGIONS:
            base = current_status.get(region, BASE_INTENSITIES[region])
            baseline = BASE_INTENSITIES[region]
            profile = _RENEWABLE_PROFILE.get(region, 1.0)
            noise = random.randint(-12, 12)
            reversion = (baseline - base) // 6
            projected = base + int(solar_adjust * profile) + reversion + noise
            regions[region] = max(40, min(650, projected))

        series.append(
            {
                "hours_ahead": h,
                "timestamp": (now + timedelta(hours=h)).isoformat(),
                "regions": regions,
            }
        )

    return series


def forecast_to_dataframe(forecast: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten forecast series for charting."""
    rows: list[dict[str, Any]] = []
    for snap in forecast:
        for region, intensity in snap["regions"].items():
            rows.append(
                {
                    "Hours Ahead": snap["hours_ahead"],
                    "Region": region,
                    "Carbon Intensity (gCO₂/kWh)": intensity,
                }
            )
    return rows


def recommend_deferral_window(
    current_status: dict[str, int],
    forecast: list[dict[str, Any]],
    min_savings_pct: float = 12.0,
) -> dict[str, Any]:
    """
    Scan the forecast for a greener dispatch window for flexible jobs.

    Compares the best future intensity against the greenest region right now.
    """
    greenest_now = min(current_status, key=current_status.get)
    intensity_now = current_status[greenest_now]

    best_future_intensity = intensity_now
    best_region = greenest_now
    best_hour = 0

    for snap in forecast[1:]:
        for region, intensity in snap["regions"].items():
            if intensity < best_future_intensity:
                best_future_intensity = intensity
                best_region = region
                best_hour = snap["hours_ahead"]

    if intensity_now <= 0:
        savings_pct = 0.0
    else:
        savings_pct = (intensity_now - best_future_intensity) / intensity_now * 100

    should_defer = savings_pct >= min_savings_pct and best_hour > 0

    if should_defer:
        rationale = (
            f"Deferring {best_hour}h could route to {best_region} at "
            f"~{best_future_intensity} gCO₂/kWh ({savings_pct:.0f}% vs greenest now)."
        )
    else:
        rationale = (
            f"No forecast window ≥{min_savings_pct:.0f}% greener than "
            f"{greenest_now} ({intensity_now} gCO₂/kWh) — dispatch now."
        )

    return {
        "should_defer": should_defer,
        "current_greenest": greenest_now,
        "current_intensity": intensity_now,
        "recommended_region": best_region,
        "recommended_hours_ahead": best_hour,
        "recommended_intensity": best_future_intensity,
        "estimated_savings_pct": round(savings_pct, 1),
        "rationale": rationale,
    }
