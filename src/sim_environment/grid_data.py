"""Grid telemetry: simulated and live (Electricity Maps) carbon + regional tariffs."""

from __future__ import annotations

import os
import random
from typing import Any

import requests

# 30 AWS commercial regions — realistic IDs and metro labels
REGIONS = [
    "us-east-1",
    "us-east-2",
    "us-west-1",
    "us-west-2",
    "ca-central-1",
    "mx-central-1",
    "sa-east-1",
    "sa-west-1",
    "eu-north-1",
    "eu-central-1",
    "eu-central-2",
    "eu-west-1",
    "eu-west-2",
    "eu-west-3",
    "eu-south-1",
    "eu-south-2",
    "il-central-1",
    "me-south-1",
    "me-central-1",
    "af-south-1",
    "ap-south-1",
    "ap-south-2",
    "ap-southeast-1",
    "ap-southeast-2",
    "ap-southeast-3",
    "ap-southeast-4",
    "ap-northeast-1",
    "ap-northeast-2",
    "ap-northeast-3",
    "ap-east-1",
]

BASE_INTENSITIES: dict[str, int] = {
    "us-east-1": 380,
    "us-east-2": 420,
    "us-west-1": 260,
    "us-west-2": 210,
    "ca-central-1": 55,
    "mx-central-1": 340,
    "sa-east-1": 290,
    "sa-west-1": 118,
    "eu-north-1": 45,
    "eu-central-1": 180,
    "eu-central-2": 72,
    "eu-west-1": 195,
    "eu-west-2": 225,
    "eu-west-3": 205,
    "eu-south-1": 310,
    "eu-south-2": 275,
    "il-central-1": 470,
    "me-south-1": 580,
    "me-central-1": 520,
    "af-south-1": 640,
    "ap-south-1": 550,
    "ap-south-2": 525,
    "ap-southeast-1": 420,
    "ap-southeast-2": 510,
    "ap-southeast-3": 465,
    "ap-southeast-4": 495,
    "ap-northeast-1": 480,
    "ap-northeast-2": 455,
    "ap-northeast-3": 468,
    "ap-east-1": 490,
}

REGION_TARIFFS_USD: dict[str, float] = {
    "us-east-1": 0.115,
    "us-east-2": 0.108,
    "us-west-1": 0.135,
    "us-west-2": 0.098,
    "ca-central-1": 0.092,
    "mx-central-1": 0.105,
    "sa-east-1": 0.102,
    "sa-west-1": 0.084,
    "eu-north-1": 0.095,
    "eu-central-1": 0.142,
    "eu-central-2": 0.118,
    "eu-west-1": 0.128,
    "eu-west-2": 0.132,
    "eu-west-3": 0.136,
    "eu-south-1": 0.138,
    "eu-south-2": 0.134,
    "il-central-1": 0.128,
    "me-south-1": 0.072,
    "me-central-1": 0.078,
    "af-south-1": 0.090,
    "ap-south-1": 0.088,
    "ap-south-2": 0.081,
    "ap-southeast-1": 0.118,
    "ap-southeast-2": 0.125,
    "ap-southeast-3": 0.095,
    "ap-southeast-4": 0.122,
    "ap-northeast-1": 0.152,
    "ap-northeast-2": 0.148,
    "ap-northeast-3": 0.150,
    "ap-east-1": 0.146,
}

# Geographic metadata for map / scatter visualizations
REGION_GEO: dict[str, dict[str, Any]] = {
    "us-east-1": {"lat": 38.9, "lon": -77.0, "label": "N. Virginia"},
    "us-east-2": {"lat": 40.0, "lon": -83.0, "label": "Ohio"},
    "us-west-1": {"lat": 37.4, "lon": -122.0, "label": "N. California"},
    "us-west-2": {"lat": 45.5, "lon": -122.7, "label": "Oregon"},
    "ca-central-1": {"lat": 45.5, "lon": -73.6, "label": "Montreal"},
    "mx-central-1": {"lat": 19.4, "lon": -99.1, "label": "Mexico City"},
    "sa-east-1": {"lat": -23.5, "lon": -46.6, "label": "São Paulo"},
    "sa-west-1": {"lat": -33.4, "lon": -70.6, "label": "Santiago"},
    "eu-north-1": {"lat": 59.3, "lon": 18.1, "label": "Stockholm"},
    "eu-central-1": {"lat": 50.1, "lon": 8.7, "label": "Frankfurt"},
    "eu-central-2": {"lat": 47.4, "lon": 8.5, "label": "Zurich"},
    "eu-west-1": {"lat": 53.3, "lon": -6.3, "label": "Ireland"},
    "eu-west-2": {"lat": 51.5, "lon": -0.1, "label": "London"},
    "eu-west-3": {"lat": 48.9, "lon": 2.3, "label": "Paris"},
    "eu-south-1": {"lat": 45.5, "lon": 9.2, "label": "Milan"},
    "eu-south-2": {"lat": 41.6, "lon": -0.9, "label": "Aragón"},
    "il-central-1": {"lat": 32.1, "lon": 34.8, "label": "Tel Aviv"},
    "me-south-1": {"lat": 26.0, "lon": 50.6, "label": "Bahrain"},
    "me-central-1": {"lat": 25.2, "lon": 55.3, "label": "UAE"},
    "af-south-1": {"lat": -33.9, "lon": 18.4, "label": "Cape Town"},
    "ap-south-1": {"lat": 19.1, "lon": 72.9, "label": "Mumbai"},
    "ap-south-2": {"lat": 17.4, "lon": 78.5, "label": "Hyderabad"},
    "ap-southeast-1": {"lat": 1.3, "lon": 103.8, "label": "Singapore"},
    "ap-southeast-2": {"lat": -33.9, "lon": 151.2, "label": "Sydney"},
    "ap-southeast-3": {"lat": -6.2, "lon": 106.8, "label": "Jakarta"},
    "ap-southeast-4": {"lat": -37.8, "lon": 144.9, "label": "Melbourne"},
    "ap-northeast-1": {"lat": 35.7, "lon": 139.7, "label": "Tokyo"},
    "ap-northeast-2": {"lat": 37.6, "lon": 127.0, "label": "Seoul"},
    "ap-northeast-3": {"lat": 34.7, "lon": 135.5, "label": "Osaka"},
    "ap-east-1": {"lat": 25.0, "lon": 121.5, "label": "Taipei"},
}

ELECTRICITYMAP_ZONES: dict[str, str] = {
    "us-east-1": "US-MIDA-PJM",
    "us-east-2": "US-MIDW-MISO",
    "us-west-1": "US-CAL-CISO",
    "us-west-2": "US-NW-PACW",
    "ca-central-1": "CA-QC",
    "mx-central-1": "MX",
    "sa-east-1": "BR-S",
    "sa-west-1": "CL-SEN",
    "eu-north-1": "SE",
    "eu-central-1": "DE",
    "eu-central-2": "CH",
    "eu-west-1": "IE",
    "eu-west-2": "GB",
    "eu-west-3": "FR",
    "eu-south-1": "IT-NO",
    "eu-south-2": "ES",
    "il-central-1": "IL",
    "me-south-1": "BH",
    "me-central-1": "AE",
    "af-south-1": "ZA",
    "ap-south-1": "IN",
    "ap-south-2": "IN-SO",
    "ap-southeast-1": "SG",
    "ap-southeast-2": "AU-NSW",
    "ap-southeast-3": "ID",
    "ap-southeast-4": "AU-VIC",
    "ap-northeast-1": "JP-TK",
    "ap-northeast-2": "KR",
    "ap-northeast-3": "JP-KN",
    "ap-east-1": "TW",
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
