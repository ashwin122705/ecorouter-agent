"""
EcoRouter — Streamlit dashboard (Stanford CS 153 demo).
Run: streamlit run app.py
"""

from __future__ import annotations

import contextlib
import io
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from agents.ecorouter import _route_jobs, _use_mock_llm  # noqa: E402
from sim_environment.grid_data import REGIONS, fluctuate_grid_status, get_live_grid_status  # noqa: E402
from sim_environment.job_queue import generate_mock_jobs  # noqa: E402

load_dotenv(ROOT / ".env")

st.set_page_config(
    page_title="EcoRouter",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .block-container { padding-top: 1.5rem; padding-bottom: 2rem; max-width: 1200px; }
      .ecorouter-hero {
        background: linear-gradient(135deg, #0f172a 0%, #14532d 55%, #052e16 100%);
        border-radius: 16px; padding: 1.75rem 2rem; margin-bottom: 1.5rem;
        color: #f8fafc; box-shadow: 0 12px 40px rgba(15, 23, 42, 0.18);
      }
      .ecorouter-hero h1 { margin: 0 0 0.35rem 0; font-size: 2rem; font-weight: 700; }
      .ecorouter-hero p { margin: 0; color: #cbd5e1; font-size: 1.02rem; }
      .ecorouter-pill {
        display: inline-block; background: rgba(255,255,255,0.12);
        border: 1px solid rgba(255,255,255,0.18); border-radius: 999px;
        padding: 0.25rem 0.75rem; font-size: 0.78rem; margin-right: 0.45rem;
        margin-top: 0.75rem; color: #e2e8f0;
      }
      .section-title { font-size: 1.05rem; font-weight: 700; color: #0f172a; margin: 0 0 0.75rem 0; }
      .grid-row { margin-bottom: 0.85rem; }
      .grid-label { display: flex; justify-content: space-between; font-size: 0.88rem; color: #334155; margin-bottom: 0.25rem; }
      .grid-bar-track { height: 12px; background: #e2e8f0; border-radius: 999px; overflow: hidden; }
      .grid-bar-fill { height: 100%; border-radius: 999px; }
      .grid-greenest {
        display: inline-block; background: #dcfce7; color: #166534;
        font-size: 0.72rem; font-weight: 600; padding: 0.1rem 0.45rem;
        border-radius: 999px; margin-left: 0.35rem;
      }
      .dispatch-card {
        background: #fff; border: 1px solid #e2e8f0; border-radius: 14px;
        padding: 1.1rem 1.25rem; margin-bottom: 0.85rem;
        box-shadow: 0 2px 10px rgba(15, 23, 42, 0.05);
      }
      .dispatch-card h4 { margin: 0 0 0.35rem 0; color: #0f172a; font-size: 1rem; }
      .dispatch-meta { color: #64748b; font-size: 0.86rem; margin-bottom: 0.55rem; }
      .badge-optimal {
        display: inline-block; background: #dcfce7; color: #166534;
        border: 1px solid #86efac; border-radius: 999px;
        padding: 0.2rem 0.65rem; font-size: 0.76rem; font-weight: 700; margin-right: 0.4rem;
      }
      .badge-constraint {
        display: inline-block; background: #fef3c7; color: #92400e;
        border: 1px solid #fcd34d; border-radius: 999px;
        padding: 0.2rem 0.65rem; font-size: 0.76rem; font-weight: 700; margin-right: 0.4rem;
      }
      .badge-route {
        display: inline-block; background: #eff6ff; color: #1d4ed8;
        border: 1px solid #bfdbfe; border-radius: 999px;
        padding: 0.2rem 0.65rem; font-size: 0.76rem; font-weight: 600;
      }
      .reasoning {
        color: #475569; font-size: 0.88rem; line-height: 1.45; margin-top: 0.5rem;
        padding-top: 0.5rem; border-top: 1px dashed #e2e8f0;
      }
      div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #16a34a, #15803d); border: none;
        color: white; font-weight: 700; font-size: 1.1rem;
        padding: 0.85rem 1.5rem; border-radius: 12px;
        box-shadow: 0 8px 24px rgba(22, 163, 74, 0.35); width: 100%;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S UTC")


def _intensity_color(value: int, max_val: int) -> str:
    ratio = value / max(max_val, 1)
    if ratio <= 0.35:
        return "#22c55e"
    if ratio <= 0.55:
        return "#84cc16"
    if ratio <= 0.72:
        return "#eab308"
    return "#ef4444"


def _init_session() -> None:
    defaults = {
        "grid_status": get_live_grid_status(),
        "jobs": generate_mock_jobs(num_jobs=4),
        "assignments": None,
        "router": None,
        "model": None,
        "optimized": False,
        "num_jobs": 4,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def _refresh_telemetry(fluctuate: bool = False) -> None:
    if fluctuate and st.session_state.get("grid_status"):
        st.session_state.grid_status = fluctuate_grid_status(st.session_state.grid_status)
    else:
        st.session_state.grid_status = get_live_grid_status()
    st.session_state.jobs = generate_mock_jobs(num_jobs=st.session_state.num_jobs)
    st.session_state.assignments = None
    st.session_state.optimized = False


def _run_optimization() -> None:
    jobs = st.session_state.jobs
    grid = st.session_state.grid_status
    with contextlib.redirect_stdout(io.StringIO()):
        assignments, meta = _route_jobs(jobs, grid)
    st.session_state.assignments = assignments
    st.session_state.router = meta.get("router", "unknown")
    st.session_state.model = meta.get("model")
    st.session_state.optimized = True


def _grid_bars_html(grid: dict[str, int]) -> str:
    greenest = min(grid, key=grid.get)
    max_val = max(grid.values())
    rows = []
    for region in REGIONS:
        value = grid[region]
        width = int((value / max_val) * 100)
        color = _intensity_color(value, max_val)
        badge = '<span class="grid-greenest">GREENEST</span>' if region == greenest else ""
        rows.append(
            f'<div class="grid-row"><div class="grid-label">'
            f'<span><strong>{region}</strong>{badge}</span>'
            f'<span>{value:,} gCO₂/kWh</span></div>'
            f'<div class="grid-bar-track">'
            f'<div class="grid-bar-fill" style="width:{width}%;background:{color};"></div>'
            f'</div></div>'
        )
    return "".join(rows)


def _dispatch_card_html(job: dict[str, Any], assignment: dict[str, Any], grid: dict[str, int], greenest: str) -> str:
    region = assignment["target_region"]
    carbon = grid[region] * job["compute_hours"]
    locality = job.get("locality_constraint")
    urgency = "Urgent" if job.get("is_urgent") else "Flexible"
    if locality:
        badge = '<span class="badge-constraint">⚠ RIGID LOCALITY CONSTRAINT</span>'
    elif region == greenest:
        badge = '<span class="badge-optimal">✓ OPTIMAL CARBON ROUTING</span>'
    else:
        badge = '<span class="badge-route">ROUTED</span>'
    return f"""
    <div class="dispatch-card">
      <h4>{job['task']} <span style="color:#94a3b8;font-weight:500;">· {job['job_id']}</span></h4>
      <div class="dispatch-meta">{urgency} · {job['compute_hours']}h compute · Est. {carbon:,} gCO₂</div>
      {badge}<span class="badge-route">→ {region}</span>
      <div class="reasoning">{assignment['reasoning']}</div>
    </div>"""


_init_session()

with st.sidebar:
    st.markdown("### ⚙️ Simulation Controls")
    st.session_state.num_jobs = st.slider("Jobs per batch", 2, 8, st.session_state.num_jobs)
    if st.button("🔄 Refresh Grid & Queue", use_container_width=True):
        _refresh_telemetry(fluctuate=False)
        st.rerun()
    if st.button("📡 Simulate Live Grid Shift", use_container_width=True):
        _refresh_telemetry(fluctuate=True)
        st.rerun()
    st.markdown("---")
    engine = "Mock Scheduler" if _use_mock_llm() else "Gemini 2.5 Flash"
    st.caption(f"**Routing engine:** {engine}")
    st.caption(f"**Last updated:** {_utc_now()}")
    st.caption("Stanford CS 153 · Frontier Systems")

st.markdown(
    """
    <div class="ecorouter-hero">
      <h1>🌱 EcoRouter</h1>
      <p>Autonomous, carbon-aware AI workload scheduler — routes compute to the greenest
      data center while respecting urgency and data-residency constraints.</p>
      <span class="ecorouter-pill">Live Grid Telemetry</span>
      <span class="ecorouter-pill">LLM Tool Calling</span>
      <span class="ecorouter-pill">Digital Twin Simulation</span>
    </div>
    """,
    unsafe_allow_html=True,
)

grid = st.session_state.grid_status
jobs = st.session_state.jobs
greenest = min(grid, key=grid.get)
avg_intensity = sum(grid.values()) / len(grid)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Greenest Region", greenest)
m2.metric("Lowest Intensity", f"{grid[greenest]} gCO₂/kWh")
m3.metric("Pending Jobs", len(jobs))
m4.metric("Network Average", f"{avg_intensity:.0f} gCO₂/kWh")

st.markdown("<p class='section-title'>🌍 Global Grid Carbon Intensity</p>", unsafe_allow_html=True)
col_chart, col_bars = st.columns([1.1, 0.9])
with col_chart:
    df_grid = pd.DataFrame([{"Region": r, "Carbon Intensity (gCO₂/kWh)": grid[r]} for r in REGIONS])
    st.bar_chart(df_grid.set_index("Region"), color="#22c55e", height=280)
with col_bars:
    st.markdown(_grid_bars_html(grid), unsafe_allow_html=True)
    st.success(f"Optimal dispatch target: **{greenest}** ({grid[greenest]} gCO₂/kWh)")

st.markdown("<p class='section-title'>📋 Pending Job Queue</p>", unsafe_allow_html=True)
df_jobs = pd.DataFrame(jobs).copy()
df_jobs["locality_constraint"] = df_jobs["locality_constraint"].fillna("—")
df_jobs["is_urgent"] = df_jobs["is_urgent"].map({True: "🔴 Urgent", False: "🟢 Flexible"})
df_jobs = df_jobs.rename(columns={
    "job_id": "Job ID", "task": "Workload", "compute_hours": "Hours",
    "is_urgent": "Priority", "locality_constraint": "Locality",
})
st.dataframe(df_jobs, use_container_width=True, hide_index=True)

st.markdown("---")
st.markdown("<p class='section-title'>🤖 Agent Dispatch</p>", unsafe_allow_html=True)

if st.button("🚀 Run EcoRouter Optimization", type="primary", use_container_width=True):
    with st.spinner("EcoRouter agent evaluating grid telemetry and job constraints..."):
        _run_optimization()
    st.rerun()

if st.session_state.optimized and st.session_state.assignments:
    assignments = st.session_state.assignments
    by_job = {a["job_id"]: a for a in assignments}
    total_carbon = sum(
        grid[by_job[j["job_id"]]["target_region"]] * j["compute_hours"]
        for j in jobs if j["job_id"] in by_job
    )
    optimal_count = sum(
        1 for j in jobs
        if j["job_id"] in by_job and not j.get("locality_constraint")
        and by_job[j["job_id"]]["target_region"] == greenest
    )
    constraint_count = sum(1 for j in jobs if j.get("locality_constraint"))

    st.markdown("### ✅ Dispatch Summary")
    r1, r2, r3 = st.columns(3)
    r1.metric("Jobs Routed", len(assignments))
    r2.metric("Optimal Routes", optimal_count)
    r3.metric("Est. Total Carbon", f"{total_carbon:,} gCO₂")

    router_label = st.session_state.router or "unknown"
    if st.session_state.model:
        st.caption(f"Engine: **{router_label}** · Model: `{st.session_state.model}`")
    else:
        st.caption(f"Engine: **{router_label}**")

    for job in jobs:
        assignment = by_job.get(job["job_id"])
        if assignment:
            st.markdown(_dispatch_card_html(job, assignment, grid, greenest), unsafe_allow_html=True)

    if constraint_count:
        st.warning(
            f"{constraint_count} job(s) had **rigid locality constraints** — routing was locked "
            "to the required region regardless of global carbon intensity."
        )
    if optimal_count:
        st.success(
            f"{optimal_count} job(s) achieved **optimal carbon routing** to the greenest "
            f"available region ({greenest})."
        )
