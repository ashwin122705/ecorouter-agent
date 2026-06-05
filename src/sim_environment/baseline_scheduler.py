"""Naive baseline schedulers for A/B carbon comparison."""

from __future__ import annotations

from typing import Any

from sim_environment.grid_data import REGIONS

DEFAULT_REGION = "us-east-1"


def run_round_robin_scheduler(
    jobs: list[dict[str, Any]],
    grid_status: dict[str, int],
    start_index: int = 0,
) -> list[dict[str, Any]]:
    """
    Dumb round-robin: cycles through regions in fixed order.
    Still honours locality constraints when present.
    """
    assignments: list[dict[str, Any]] = []
    idx = start_index

    for job in jobs:
        locality = job.get("locality_constraint")
        if locality:
            target = locality
            reasoning = f"[Baseline RR] Locality locked to {locality}."
        else:
            target = REGIONS[idx % len(REGIONS)]
            idx += 1
            reasoning = (
                f"[Baseline RR] Round-robin dispatch to {target} "
                f"({grid_status[target]} gCO₂/kWh) — no carbon optimization."
            )

        assignments.append(
            {"job_id": job["job_id"], "target_region": target, "reasoning": reasoning}
        )

    return assignments


def run_static_default_scheduler(
    jobs: list[dict[str, Any]],
    grid_status: dict[str, int],
    default_region: str = DEFAULT_REGION,
) -> list[dict[str, Any]]:
    """
    Industry-typical naive policy: send everything to the default region (us-east-1)
    unless a locality constraint overrides it.
    """
    assignments: list[dict[str, Any]] = []

    for job in jobs:
        locality = job.get("locality_constraint")
        target = locality or default_region
        reasoning = (
            f"[Baseline Static] Default region {default_region}."
            if not locality
            else f"[Baseline Static] Locality override {locality}."
        )
        assignments.append(
            {
                "job_id": job["job_id"],
                "target_region": target,
                "reasoning": f"{reasoning} Intensity {grid_status[target]} gCO₂/kWh.",
            }
        )

    return assignments
