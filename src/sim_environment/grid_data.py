import random

REGIONS = [
    "us-east-1",     # Usually mixed coal/gas
    "us-west-2",     # Often greener (hydro/wind)
    "eu-central-1",  # Strict regulations, often green
    "ap-south-1"     # High carbon baseline
]

BASE_INTENSITIES = {
    "us-east-1": 380,
    "us-west-2": 210,
    "eu-central-1": 180,
    "ap-south-1": 550,
}


def get_live_grid_status():
    """
    Simulates real-time carbon intensity across global data centers.
    Returns values in gCO2eq/kWh (grams of carbon dioxide equivalent per kilowatt-hour).
    """
    current_status = {}
    for region, base in BASE_INTENSITIES.items():
        fluctuation = random.randint(-40, 60)
        current_status[region] = max(0, base + fluctuation)

    return current_status


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

if __name__ == "__main__":
    print(get_live_grid_status())
