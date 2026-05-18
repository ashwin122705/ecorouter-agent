import json
import sys
import os

# Add the root directory to the system path to allow local imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim_environment.grid_data import get_live_grid_status
from sim_environment.job_queue import generate_mock_jobs

def run_agent_scaffolding():
    print("🌱 Initializing EcoRouter Agent Environment...\n")
    
    # 1. Fetch the live simulated grid status
    print("🌍 1. Fetching Global Grid Telemetry...")
    grid_status = get_live_grid_status()
    print(f"Current Carbon Intensity (gCO2/kWh):\n{json.dumps(grid_status, indent=2)}\n")
    
    # 2. Fetch the mock job queue
    print("📋 2. Evaluating Job Queue...")
    jobs = generate_mock_jobs(num_jobs=3)
    for job in jobs:
        constraint = f"Must run in {job['locality_constraint']}" if job['locality_constraint'] else "No geographic limits"
        urgency = "URGENT" if job['is_urgent'] else "FLEXIBLE (Eligible for temporal shift)"
        print(f"  - [{job['job_id']}] {job['task']} | {urgency} | {constraint}")
        
    # 3. LLM Agent Routing (Scaffolding Phase)
    print("\n🤖 3. Agent Execution Scaffolding...")
    print("  -> LLM Tool Calling framework will be injected here.")
    print("  -> Agent will receive the JSON queue and grid status.")
    
    # Simulating the expected output of the LLM for proof of concept
    print("\n✅ Simulated Output from Agent:")
    for job in jobs:
        # A basic heuristic mimicking what the LLM will be prompted to do:
        if job['locality_constraint']:
            assigned_region = job['locality_constraint']
            reason = "Strict locality constraint."
        else:
            assigned_region = min(grid_status, key=grid_status.get)
            reason = "Lowest global carbon intensity."
            
        print(f"  -> Dispatched {job['job_id']} to {assigned_region} ({reason})")

if __name__ == "__main__":
    run_agent_scaffolding()
