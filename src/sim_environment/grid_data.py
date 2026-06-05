"""Grid telemetry: simulated and live (Electricity Maps) carbon + regional tariffs."""

from __future__ import annotations

import os
import random
from typing import Any

import requests

# 20 regions — globally distributed for diverse carbon/cost optimization
REGIONS = [
    "us-east-1",
    "us-east-2",
    "us-west-1",
    "us-west-2",
    "ca-central-1",
    "mx-central-1",
    "eu-west-1",
    "eu-west-2",
    "eu-central-1",
    "eu-north-1",
    "eu-south-1",
    "il-central-1",
    "me-south-1",
    "af-south-1",
    "ap-south-1",
    "ap-southeast-1",
    "ap-southeast-2",
    "ap-northeast-1",
    "ap-northeast-2",
    "sa-east-1",
]

BASE_INTENSITIES: dict[str, int] = {
    "us-east-1": 380,
    "us-east-2": 420,
    "us-west-1": 260,
    "us-west-2": 210,
    "ca-central-1": 55,
    "mx-central-1": 340,
    "eu-west-1": 195,
    "eu-west-2": 225,
    "eu-central-1": 180,
    "eu-north-1": 45,
    "eu-south-1": 310,
    "il-central-1": 470,
    "me-south-1": 580,
    "af-south-1": 640,
    "ap-south-1": 550,
    "ap-southeast-1": 420,
    "ap-southeast-2": 510,
    "ap-northeast-1": 480,
    "ap-northeast-2": 455,
    "sa-east-1": 290,
}

REGION_TARIFFS_USD: dict[str, float] = {
    "us-east-1": 0.115,
    "us-east-2": 0.108,
    "us-west-1": 0.135,
    "us-west-2": 0.098,
    "ca-central-1": 0.092,
    "mx-central-1": 0.105,
    "eu-west-1": 0.128,
    "eu-west-2": 0.132,
    "eu-central-1": 0.142,
    "eu-north-1": 0.095,
    "eu-south-1": 0.138,
    "il-central-1": 0.128,
    "me-south-1": 0.072,
    "af-south-1": 0.090,
    "ap-south-1": 0.088,
    "ap-southeast-1": 0.118,
    "ap-southeast-2": 0.125,
    "ap-northeast-1": 0.152,
    "ap-northeast-2": 0.148,
    "sa-east-1": 0.102,
}

# Geographic metadata for map / scatter visualizations
REGION_GEO: dict[str, dict[str, Any]] = {
    "us-east-1": {"lat": 38.9, "lon": -77.0, "label": "N. Virginia"},
    "us-east-2": {"lat": 40.0, "lon": -83.0, "label": "Ohio"},
    "us-west-1": {"lat": 37.4, "lon": -122.0, "label": "N. California"},
    "us-west-2": {"lat": 45.5, "lon": -122.7, "label": "Oregon"},
    "ca-central-1": {"lat": 45.5, "lon": -73.6, "label": "Montreal"},
    "mx-central-1": {"lat": 19.4, "lon": -99.1, "label": "Mexico City"},
    "eu-west-1": {"lat": 53.3, "lon": -6.3, "label": "Ireland"},
    "eu-west-2": {"lat": 51.5, "lon": -0.1, "label": "London"},
    "eu-central-1": {"lat": 50.1, "lon": 8.7, "label": "Frankfurt"},
    "eu-north-1": {"lat": 59.3, "lon": 18.1, "label": "Stockholm"},
    "eu-south-1": {"lat": 45.5, "lon": 9.2, "label": "Milan"},
    "il-central-1": {"lat": 32.1, "lon": 34.8, "label": "Tel Aviv"},
    "me-south-1": {"lat": 26.0, "lon": 50.6, "label": "Bahrain"},
    "af-south-1": {"lat": -33.9, "lon": 18.4, "label": "Cape Town"},
    "ap-south-1": {"lat": 19.1, "lon": 72.9, "label": "Mumbai"},
    "ap-southeast-1": {"lat": 1.3, "lon": 103.8, "label": "Singapore"},
    "ap-southeast-2": {"lat": -33.9, "lon": 151.2, "label": "Sydney"},
    "ap-northeast-1": {"lat": 35.7, "lon": 139.7, "label": "Tokyo"},
    "ap-northeast-2": {"lat": 37.6, "lon": 127.0, "label": "Seoul"},
    "sa-east-1": {"lat": -23.5, "lon": -46.6, "label": "São Paulo"},
}

ELECTRICITYMAP_ZONES: dict[str, str] = {
    "us-east-1": "US-MIDA-PJM",
    "us-east-2": "US-MIDW-MISO",
    "us-west-1": "US-CAL-CISO",
    "us-west-2": "US-NW-PACW",
    "ca-central-1": "CA-QC",
    "mx-central-1": "MX",
    "eu-west-1": "IE",
    "eu-west-2": "GB",
    "eu-central-1": "DE",
    "eu-north-1": "SE",
    "eu-south-1": "IT-NO",
    "il-central-1": "IL",
    "me-south-1": "BH",
    "af-south-1": "ZA",
    "ap-south-1": "IN",
    "ap-southeast-1": "SG",
    "ap-southeast-2": "AU-NSW",
    "ap-northeast-1": "JP-TK",
    "ap-northeast-2": "KR",
    "sa-east-1": "BR-S",
}

DEFAULT_BASELINE_REGION = "us-east-1"
MAX_BATCH_JOBS = 50


def _simulated_carbon() -> dict[str, int]:
    current_status: dict[str, int] = {}
    for region, base in BASE_INTENSITIES.items():
        fluctuation = random.randint(-40, 60)
        current_status[region] = max(0, base + fluctuation)
    return current_status


def fetch_electricity_maps_carbon() -> dict[str, int]:
    """Fetch live carbon intensity; returns partial results per zone."""
    api_key = os.getenv("ELECTRICITY_MAPS_API_KEY", "").strip()
    if not api_key:
        return {}

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

    return carbon


def get_live_grid_status() -> dict[str, int]:
    return get_grid_telemetry(source="simulated")["carbon_gco2_per_kwh"]


def get_regions_catalog() -> list[dict[str, Any]]:
    """Full region catalog for API and UI tools."""
    return [
        {
            "region": r,
            "label": REGION_GEO[r]["label"],
            "lat": REGION_GEO[r]["lat"],
            "lon": REGION_GEO[r]["lon"],
            "baseline_carbon_gco2_per_kwh": BASE_INTENSITIES[r],
            "tariff_usd_per_kwh": REGION_TARIFFS_USD[r],
            "electricitymap_zone": ELECTRICITYMAP_ZONES.get(r),
        }
        for r in REGIONS
    ]


def get_grid_telemetry(source: str = "simulated") -> dict[str, Any]:
    data_source = "simulated"
    carbon = _simulated_carbon()

    if source == "live":
        live = fetch_electricity_maps_carbon()
        if live:
            carbon.update(live)
            if len(live) == len(REGIONS):
                data_source = "electricity_maps"
            else:
                data_source = f"electricity_maps_partial ({len(live)}/{len(REGIONS)} zones)"
        else:
            data_source = "simulated_fallback"

    cost = {r: REGION_TARIFFS_USD[r] for r in REGIONS}
    greenest = min(carbon, key=carbon.get)
    cheapest = min(cost, key=cost.get)

    return {
        "carbon_gco2_per_kwh": carbon,
        "cost_usd_per_kwh": cost,
        "source": data_source,
        "greenest_region": greenest,
        "greenest_intensity": carbon[greenest],
        "cheapest_region": cheapest,
        "cheapest_tariff": cost[cheapest],
        "region_count": len(REGIONS),
    }


def fluctuate_grid_status(
    current_status: dict[str, int],
    max_delta: int = 18,
) -> dict[str, int]:
    updated: dict[str, int] = {}
    for region in REGIONS:
        prior = current_status.get(region, BASE_INTENSITIES[region])
        baseline = BASE_INTENSITIES[region]
        delta = random.randint(-max_delta, max_delta)
        reversion = (baseline - prior) // 8
        updated[region] = max(40, min(680, prior + delta + reversion))
    return updated
