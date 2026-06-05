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


def composite_score(
    region: str,
    candidates: list[str],
    grid_status: dict[str, int],
    tariffs: dict[str, float],
    carbon_weight: float = 0.6,
    load_fraction: float = 0.0,
    load_penalty: float = 0.12,
) -> float:
    """Lower is better. Optional load_fraction in [0,1] penalizes crowded regions."""
    carbon_norm = _normalize({r: float(grid_status[r]) for r in candidates})
    cost_norm = _normalize({r: tariffs.get(r, REGION_TARIFFS_USD[r]) for r in candidates})
    cw = max(0.0, min(1.0, carbon_weight))
    return (
        cw * carbon_norm[region]
        + (1 - cw) * cost_norm[region]
        + load_penalty * load_fraction
    )


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


def pareto_candidate_pool(
    candidates: list[str],
    grid_status: dict[str, int],
    tariffs: dict[str, float],
    reference_region: str = DEFAULT_BASELINE_REGION,
) -> tuple[list[str], str]:
    """
    Return eligible regions and tier for Pareto routing.

    tier: strict_pareto | cost_neutral_carbon | cost_aware_fallback
    """
    ref_carbon = grid_status[reference_region]
    ref_tariff = tariffs.get(reference_region, REGION_TARIFFS_USD[reference_region])

    strict = [
        r for r in candidates
        if grid_status[r] < ref_carbon and tariffs.get(r, 1) <= ref_tariff
    ]
    if strict:
        return strict, "strict_pareto"

    cost_neutral = [r for r in candidates if tariffs.get(r, 1) <= ref_tariff]
    greener = [r for r in cost_neutral if grid_status[r] < ref_carbon]
    if greener:
        return greener, "cost_neutral_carbon"

    return list(candidates), "cost_aware_fallback"


def select_pareto_region(
    candidates: list[str],
    grid_status: dict[str, int],
    tariffs: dict[str, float],
    reference_region: str = DEFAULT_BASELINE_REGION,
    region_load: dict[str, int] | None = None,
    max_load: int = 1,
    load_penalty: float = 0.38,
) -> tuple[str, str, str]:
    """
    Prefer regions that beat the baseline on carbon without increasing cost.
    When several regions qualify, spread jobs using a light load penalty
    instead of sending every job to a single greenest datacenter.
    """
    pool, tier = pareto_candidate_pool(
        candidates, grid_status, tariffs, reference_region
    )
    ref_carbon = grid_status[reference_region]
    ref_tariff = tariffs.get(reference_region, REGION_TARIFFS_USD[reference_region])
    loads = region_load or {}

    if tier == "cost_aware_fallback":
        best, reasoning = select_cost_aware_region(
            candidates, grid_status, tariffs, carbon_weight=0.55
        )
        if loads:
            best = min(
                pool,
                key=lambda r: composite_score(
                    r,
                    pool,
                    grid_status,
                    tariffs,
                    carbon_weight=0.55,
                    load_fraction=loads.get(r, 0) / max(max_load, 1),
                    load_penalty=load_penalty,
                ),
            )
            reasoning = (
                f"No strict Pareto option vs {reference_region}; load-balanced pick "
                f"{best} ({grid_status[best]} gCO₂/kWh, ${tariffs.get(best, 0):.3f}/kWh)."
            )
        return best, reasoning, tier

    if len(pool) == 1 or not loads:
        best = min(pool, key=lambda r: grid_status[r])
    else:
        best = min(
            pool,
            key=lambda r: composite_score(
                r,
                pool,
                grid_status,
                tariffs,
                carbon_weight=0.72,
                load_fraction=loads.get(r, 0) / max(max_load, 1),
                load_penalty=load_penalty,
            ),
        )

    if tier == "strict_pareto":
        reasoning = (
            f"Pareto-optimal vs {reference_region}: {best} "
            f"({grid_status[best]} vs {ref_carbon} gCO₂/kWh, "
            f"${tariffs.get(best, 0):.3f} vs ${ref_tariff:.3f}/kWh)."
        )
        if len(pool) > 1 and loads.get(best, 0) > 0:
            reasoning += f" Spread across {len(pool)} qualifying regions."
    else:
        reasoning = (
            f"Cost-neutral carbon win vs {reference_region}: {best} "
            f"({grid_status[best]} gCO₂/kWh) at same-or-lower tariff."
        )

    return best, reasoning, tier
