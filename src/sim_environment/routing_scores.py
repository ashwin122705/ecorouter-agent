"""Region scoring for cost-aware and Pareto routing modes."""

from __future__ import annotations

from typing import Any

from sim_environment.grid_data import DEFAULT_BASELINE_REGION, REGIONS, REGION_TARIFFS_USD


def allowed_regions(job: dict[str, Any]) -> list[str]:
    locality = job.get("locality_constraint")
    return [locality] if locality else list(REGIONS)


def baseline_reference_region(
    job: dict[str, Any],
    default: str = DEFAULT_BASELINE_REGION,
) -> str:
    """Region a naive static baseline would use for this job."""
    return job.get("locality_constraint") or default


def _normalize(values: dict[str, float]) -> dict[str, float]:
    lo = min(values.values())
    hi = max(values.values())
    span = hi - lo
    if span <= 0:
        return {k: 0.0 for k in values}
    return {k: (v - lo) / span for k, v in values.items()}


def select_cost_aware_region(
    candidates: list[str],
    grid_status: dict[str, int],
    tariffs: dict[str, float],
    carbon_weight: float = 0.6,
) -> tuple[str, str]:
    """
    Pick region minimizing weighted carbon + cost score (lower is better).
    carbon_weight in [0, 1]: 1.0 = carbon only, 0.0 = cost only.
    """
    carbon_weight = max(0.0, min(1.0, carbon_weight))
    cost_weight = 1.0 - carbon_weight

    carbon_norm = _normalize({r: float(grid_status[r]) for r in candidates})
    cost_norm = _normalize({r: tariffs.get(r, REGION_TARIFFS_USD[r]) for r in candidates})

    best = min(
        candidates,
        key=lambda r: carbon_weight * carbon_norm[r] + cost_weight * cost_norm[r],
    )
    reasoning = (
        f"Cost-aware routing ({carbon_weight:.0%} carbon / {cost_weight:.0%} cost): "
        f"{best} at {grid_status[best]} gCO₂/kWh, "
        f"${tariffs.get(best, 0):.3f}/kWh."
    )
    return best, reasoning


def select_pareto_region(
    candidates: list[str],
    grid_status: dict[str, int],
    tariffs: dict[str, float],
    reference_region: str = DEFAULT_BASELINE_REGION,
) -> tuple[str, str, str]:
    """
    Prefer regions that beat the baseline on carbon without increasing cost.

    Returns (region, reasoning, tier) where tier is:
      strict_pareto | cost_neutral_carbon | cost_aware_fallback
    """
    ref_carbon = grid_status[reference_region]
    ref_tariff = tariffs.get(reference_region, REGION_TARIFFS_USD[reference_region])

    strict = [
        r for r in candidates
        if grid_status[r] < ref_carbon and tariffs.get(r, 1) <= ref_tariff
    ]
    if strict:
        best = min(strict, key=lambda r: grid_status[r])
        return (
            best,
            (
                f"Pareto-optimal vs {reference_region}: {best} lowers carbon "
                f"({grid_status[best]} vs {ref_carbon} gCO₂/kWh) "
                f"without raising tariff (${tariffs.get(best, 0):.3f} vs ${ref_tariff:.3f}/kWh)."
            ),
            "strict_pareto",
        )

    cost_neutral = [r for r in candidates if tariffs.get(r, 1) <= ref_tariff]
    greener = [r for r in cost_neutral if grid_status[r] < ref_carbon]
    if greener:
        best = min(greener, key=lambda r: grid_status[r])
        return (
            best,
            (
                f"Cost-neutral carbon win vs {reference_region}: {best} "
                f"({grid_status[best]} gCO₂/kWh) at same-or-lower tariff."
            ),
            "cost_neutral_carbon",
        )

    best, reasoning = select_cost_aware_region(
        candidates, grid_status, tariffs, carbon_weight=0.55
    )
    return (
        best,
        f"No strict Pareto option vs {reference_region}; {reasoning}",
        "cost_aware_fallback",
    )
