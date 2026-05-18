import random

REGIONS = [
    "us-east-1",     # Usually mixed coal/gas
    "us-west-2",     # Often greener (hydro/wind)
    "eu-central-1",  # Strict regulations, often green
    "ap-south-1"     # High carbon baseline
]

def get_live_grid_status():
    """
    Simulates real-time carbon intensity across global data centers.
    Returns values in gCO2eq/kWh (grams of carbon dioxide equivalent per kilowatt-hour).
    """
    # Base historical carbon averages for these regions
    base_intensities = {
        "us-east-1": 380,
        "us-west-2": 210,
        "eu-central-1": 180,
        "ap-south-1": 550
    }
    
    current_status = {}
    for region, base in base_intensities.items():
        # Add random fluctuation to simulate live wind/solar/demand changes
        fluctuation = random.randint(-40, 60)
        current_status[region] = max(0, base + fluctuation)
        
    return current_status

if __name__ == "__main__":
    print(get_live_grid_status())
