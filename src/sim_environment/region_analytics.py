"""Region analytics, what-if analysis, and load distribution tools."""

from __future__ import annotations

from collections import Counter
from typing import Any

from sim_environment.grid_data import DEFAULT_BASELINE_REGION, REGIONS, REGION_TARIFFS_USD
from sim_environment.routing_scores import (
    select_cost_aware_region,
    select_pareto_region,
)


def region_score_matrix(
    grid_status: dict[str, int],
    tariffs: dict[str, float],
    carbon_weight: float = 0.6,
    reference_region: str = DEFAULT_BASELINE_REGION,
) -> list[dict[str, Any]]:
    """Score every region for carbon, cost, Pareto eligibility, and composite rank."""
    ref_carbon = grid_status[reference_region]
    ref_tariff = tariffs.get(reference_region, REGION_TARIFFS_USD[reference_region])
    max_c = max(grid_status.values())
    min_c = min(grid_status.values())
    max_t = max(tariffs.values())
    min_t = min(tariffs.values())
    c_span = max(max_c - min_c, 1)
    t_span = max(max_t - min_t, 0.001)

    rows: list[dict[str, Any]] = []
    for region in REGIONS:
        carbon = grid_status[region]
        tariff = tariffs.get(region, REGION_TARIFFS_USD[region])
        carbon_norm = (carbon - min_c) / c_span
        cost_norm = (tariff - min_t) / t_span
        composite = carbon_weight * carbon_norm + (1 - carbon_weight) * cost_norm

        if carbon < ref_carbon and tariff <= ref_tariff:
            pareto = "strict"
        elif carbon < ref_carbon:
            pareto = "carbon_only"
        elif tariff <= ref_tariff:
            pareto = "cost_only"
        else:
            pareto = "dominated"

        rows.append(
            {
                "region": region,
                "carbon_gco2_per_kwh": carbon,
                "tariff_usd_per_kwh": round(tariff, 4),
                "composite_score": round(composite, 3),
                "pareto_vs_baseline": pareto,
                "carbon_vs_baseline_pct": round((ref_carbon - carbon) / ref_carbon * 100, 1)
                if ref_carbon
                else 0,
                "cost_vs_baseline_pct": round((ref_tariff - tariff) / ref_tariff * 100, 1)
                if ref_tariff
                else 0,
            }
        )

    rows.sort(key=lambda r: r["composite_score"])
    for i, row in enumerate(rows, start=1):
        row["rank"] = i
    return rows


def compute_load_distribution(assignments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Count jobs assigned per region after routing."""
    counts = Counter(a["target_region"] for a in assignments)
    total = len(assignments) or 1
    return [
        {
            "region": r,
            "jobs": counts.get(r, 0),
            "share_pct": round(counts.get(r, 0) / total * 100, 1),
        }
        for r in REGIONS
        if counts.get(r, 0) > 0
    ] + [
        {"region": r, "jobs": 0, "share_pct": 0.0}
        for r in REGIONS
        if counts.get(r, 0) == 0
    ]


def what_if_analyze(
    compute_hours: int,
    grid_status: dict[str, int],
    tariffs: dict[str, float],
    *,
    is_urgent: bool = False,
    locality: str | None = None,
    carbon_weight: float = 0.6,
    reference_region: str = DEFAULT_BASELINE_REGION,
) -> dict[str, Any]:
    """Recommend best region per routing objective for a single hypothetical job."""
    candidates = [locality] if locality else list(REGIONS)
    hours = max(1, compute_hours)

    carbon_best = min(candidates, key=lambda r: grid_status[r])
    cost_best = min(candidates, key=lambda r: tariffs.get(r, 1))
    pareto_r, pareto_reason, pareto_tier = select_pareto_region(
        candidates, grid_status, tariffs, reference_region
    )
    cost_aware_r, cost_aware_reason = select_cost_aware_region(
        candidates, grid_status, tariffs, carbon_weight
    )

    def _estimate(region: str) -> dict[str, float | int]:
        return {
            "region": region,
            "carbon_gco2": grid_status[region] * hours,
            "cost_usd": round(tariffs.get(region, 0) * hours, 2),
        }

    return {
        "compute_hours": hours,
        "is_urgent": is_urgent,
        "locality": locality,
        "recommendations": {
            "carbon_first": {**_estimate(carbon_best), "reasoning": "Lowest gCO₂/kWh now."},
            "cost_first": {**_estimate(cost_best), "reasoning": "Lowest $/kWh tariff."},
            "pareto": {
                **_estimate(pareto_r),
                "reasoning": pareto_reason,
                "tier": pareto_tier,
            },
            "cost_aware": {
                **_estimate(cost_aware_r),
                "reasoning": cost_aware_reason,
            },
        },
        "baseline": _estimate(reference_region if reference_region in candidates else candidates[0]),
    }
