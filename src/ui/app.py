import streamlit as st
import pandas as pd
import sys
import os
import time

# Add the root directory to the system path to allow local imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sim_environment.grid_data import get_live_grid_status
from sim_environment.job_queue import generate_mock_jobs

# Configure the Streamlit page
st.set_page_config(page_title="EcoRouter Dashboard", page_icon="🌱", layout="wide")

st.title("🌱 EcoRouter: Live Telemetry")
st.write("Autonomous LLM scheduling agent for carbon-aware AI workloads.")

# Create two columns for the UI
col1, col2 = st.columns(2)

with col1:
    st.subheader("🌍 Global Grid Status")
    grid_data = get_live_grid_status()
    df_grid = pd.DataFrame(list(grid_data.items()), columns=["Region", "Carbon Intensity (gCO2/kWh)"])
    st.dataframe(df_grid, use_container_width=True, hide_index=True)
    
    greenest_region = min(grid_data, key=grid_data.get)
    st.success(f"**Greenest Region Right Now:** {greenest_region} ({grid_data[greenest_region]} gCO2/kWh)")

with col2:
    st.subheader("📋 Incoming Job Queue")
    jobs = generate_mock_jobs(num_jobs=3)
    df_jobs = pd.DataFrame(jobs)
    st.dataframe(df_jobs, use_container_width=True, hide_index=True)

st.divider()

# Simulate the agent action
st.subheader("🤖 Agent Dispatch Simulation")
if st.button("Run EcoRouter Routing Logic"):
    with st.spinner("LLM Agent evaluating constraints and grid data..."):
        time.sleep(1.5) 
        
        for job in jobs:
            if job['locality_constraint']:
                target = job['locality_constraint']
                reason = "Strict data residency constraint"
            else:
                target = greenest_region
                reason = "Optimized for lowest carbon footprint"
            
            st.info(f"**Job ID:** `{job['job_id']}` ➔ **Routed to Data Center:** `{target}`  \n*Reasoning: {reason}*")
