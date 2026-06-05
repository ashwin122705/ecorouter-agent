"""Grid telemetry: simulated and live (Electricity Maps) carbon + regional tariffs."""

from __future__ import annotations

import os
import random
from typing import Any

import requests

REGIONS = [
    "us-east-1",
    "us-west-2",
    "eu-central-1",
    "ap-south-1",
]

BASE_INTENSITIES = {
    "us-east-1": 380,
    "us-west-2": 210,
    "eu-central-1": 180,
    "ap-south-1": 550,
}

# Approximate cloud-region electricity tariffs (USD/kWh) for FinOps modeling
REGION_TARIFFS_USD: dict[str, float] = {
    "us-east-1": 0.115,
    "us-west-2": 0.098,
    "eu-central-1": 0.142,
    "ap-south-1": 0.088,
}

# Electricity Maps zone codes per simulated region
ELECTRICITYMAP_ZONES: dict[str, str] = {
    "us-east-1": "US-MIDA-PJM",
    "us-west-2": "US-NW-PACW",
    "eu-central-1": "DE",
    "ap-south-1": "IN",
}


def _simulated_carbon() -> dict[str, int]:
    current_status: dict[str, int] = {}
    for region, base in BASE_INTENSITIES.items():
        fluctuation = random.randint(-40, 60)
        current_status[region] = max(0, base + fluctuation)
    return current_status


def fetch_electricity_maps_carbon() -> dict[str, int] | None:
    """
    Fetch live carbon intensity from Electricity Maps API.
    Requires ELECTRICITY_MAPS_API_KEY in environment.
    """
    api_key = os.getenv("ELECTRICITY_MAPS_API_KEY", "").strip()
    if not api_key:
        return None

    carbon: dict[str, int] = {}
    headers = {"auth-token": api_key}

    for region, zone in ELECTRICITYMAP_ZONES.items():
        try:
            resp = requests.get(
                "https://api.electricitymap.org/v3/carbon-intensity/latest",
                params={"zone": zone},
                headers=headers,
                timeout=8,
            )
            if resp.ok:
                intensity = resp.json().get("carbonIntensity")
                if intensity is not None:
                    carbon[region] = max(0, int(intensity))
        except requests.RequestException:
            continue

    return carbon if len(carbon) == len(REGIONS) else None


def get_live_grid_status() -> dict[str, int]:
    """Backward-compatible: returns carbon intensities only."""
    return get_grid_telemetry(source="simulated")["carbon_gco2_per_kwh"]


def get_grid_telemetry(source: str = "simulated") -> dict[str, Any]:
    """
    Return full telemetry snapshot: carbon, cost, and data provenance.

    source: "simulated" | "live" (Electricity Maps with simulated fallback)
    """
    data_source = "simulated"
    carbon = _simulated_carbon()

    if source == "live":
        live = fetch_electricity_maps_carbon()
        if live:
            carbon = live
            data_source = "electricity_maps"
        else:
            data_source = "simulated_fallback"

    cost = {r: REGION_TARIFFS_USD[r] for r in REGIONS}
    greenest = min(carbon, key=carbon.get)

    return {
        "carbon_gco2_per_kwh": carbon,
        "cost_usd_per_kwh": cost,
        "source": data_source,
        "greenest_region": greenest,
        "greenest_intensity": carbon[greenest],
    }


def fluctuate_grid_status(
    current_status: dict[str, int],
    max_delta: int = 18,
) -> dict[str, int]:
    """Nudge intensities between polling cycles (solar/wind simulation)."""
    updated: dict[str, int] = {}
    for region in REGIONS:
        prior = current_status.get(region, BASE_INTENSITIES[region])
        baseline = BASE_INTENSITIES[region]
        delta = random.randint(-max_delta, max_delta)
        reversion = (baseline - prior) // 8
        updated[region] = max(80, min(650, prior + delta + reversion))
    return updated
