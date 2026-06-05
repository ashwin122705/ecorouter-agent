"""
EcoRouter — Streamlit dashboard (Stanford CS 153).
Run: streamlit run app.py
API:  uvicorn api.server:app --reload --app-dir src --port 8000
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import os

from agents.ecorouter import _route_jobs, _use_mock_llm  # noqa: E402
from reports.esg_report import generate_esg_pdf  # noqa: E402
from sim_environment.baseline_scheduler import (  # noqa: E402
    run_round_robin_scheduler,
    run_static_default_scheduler,
)
from sim_environment.carbon_metrics import (  # noqa: E402
    compare_schedulers,
    total_carbon_cost,
    total_energy_cost_usd,
)
from sim_environment.grid_data import (  # noqa: E402
    MAX_BATCH_JOBS,
    REGIONS,
    REGION_GEO,
    fluctuate_grid_status,
    get_grid_telemetry,
)
from sim_environment.region_analytics import (  # noqa: E402
    compute_load_distribution,
    region_score_matrix,
    what_if_analyze,
)
from sim_environment.grid_forecast import (  # noqa: E402
    forecast_grid,
    forecast_to_dataframe,
    recommend_deferral_window,
)
from sim_environment.job_queue import (  # noqa: E402
    generate_mock_jobs,
    parse_jobs_from_csv,
    parse_jobs_from_json,
    sample_jobs_json,
)
from sim_environment.sla import hours_until_deadline  # noqa: E402

load_dotenv(ROOT / ".env")

st.set_page_config(page_title="EcoRouter", page_icon="🌱", layout="wide", initial_sidebar_state="expanded")

st.markdown(
    """
    <style>
      .block-container { padding-top: 1.2rem; max-width: 1280px; }
      .ecorouter-hero {
        background: linear-gradient(135deg, #0f172a 0%, #14532d 55%, #052e16 100%);
        border-radius: 16px; padding: 1.5rem 2rem; margin-bottom: 1.25rem; color: #f8fafc;
      }
      .ecorouter-hero h1 { margin: 0; font-size: 1.85rem; font-weight: 700; }
      .ecorouter-hero p { margin: 0.35rem 0 0; color: #cbd5e1; font-size: 0.98rem; }
      .ecorouter-pill {
        display: inline-block; background: rgba(255,255,255,0.12);
        border: 1px solid rgba(255,255,255,0.18); border-radius: 999px;
        padding: 0.2rem 0.65rem; font-size: 0.75rem; margin-right: 0.4rem; margin-top: 0.6rem;
      }
      .section-title { font-size: 1.02rem; font-weight: 700; color: #0f172a; margin: 0 0 0.65rem 0; }
      .grid-row { margin-bottom: 0.75rem; }
      .grid-label { display: flex; justify-content: space-between; font-size: 0.86rem; color: #334155; }
      .grid-bar-track { height: 10px; background: #e2e8f0; border-radius: 999px; overflow: hidden; margin-top: 0.2rem; }
      .grid-greenest {
        background: #dcfce7; color: #166534; font-size: 0.7rem; font-weight: 600;
        padding: 0.08rem 0.4rem; border-radius: 999px; margin-left: 0.3rem;
      }
      .dispatch-card {
        background: #fff; border: 1px solid #e2e8f0; border-radius: 12px;
        padding: 1rem 1.15rem; margin-bottom: 0.75rem;
      }
      .badge-optimal { background: #dcfce7; color: #166534; border: 1px solid #86efac;
        border-radius: 999px; padding: 0.15rem 0.55rem; font-size: 0.74rem; font-weight: 700; }
      .badge-constraint { background: #fef3c7; color: #92400e; border: 1px solid #fcd34d;
        border-radius: 999px; padding: 0.15rem 0.55rem; font-size: 0.74rem; font-weight: 700; }
      .badge-defer { background: #ede9fe; color: #5b21b6; border: 1px solid #c4b5fd;
        border-radius: 999px; padding: 0.15rem 0.55rem; font-size: 0.74rem; font-weight: 700; }
      .badge-route { background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe;
        border-radius: 999px; padding: 0.15rem 0.55rem; font-size: 0.74rem; }
      div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #16a34a, #15803d); border: none; color: white;
        font-weight: 700; border-radius: 10px; width: 100%;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S UTC")


def _format_locality(value: str | None) -> str:
    """Human-readable locality — None means the job can run in any region."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "Any region"
    text = str(value).strip()
    if text.lower() in {"", "—", "-", "none", "null", "nan"}:
        return "Any region"
    return text


def _intensity_color(value: int, max_val: int) -> str:
    ratio = value / max(max_val, 1)
    if ratio <= 0.35:
        return "#22c55e"
    if ratio <= 0.55:
        return "#84cc16"
    if ratio <= 0.72:
        return "#eab308"
    return "#ef4444"


def _load_grid(source: str | None = None, fluctuate: bool = False) -> dict[str, Any]:
    src = source or st.session_state.get("grid_source", "simulated")
    if fluctuate and st.session_state.get("grid_status"):
        carbon = fluctuate_grid_status(st.session_state.grid_status)
        telemetry = dict(st.session_state.grid_telemetry)
        telemetry["carbon_gco2_per_kwh"] = carbon
        telemetry["greenest_region"] = min(carbon, key=carbon.get)
        telemetry["greenest_intensity"] = carbon[telemetry["greenest_region"]]
        telemetry["source"] = "simulated_shift"
        return telemetry
    return get_grid_telemetry(source=src)


def _init_session() -> None:
    telemetry = get_grid_telemetry(source="simulated")
    defaults: dict[str, Any] = {
        "grid_telemetry": telemetry,
        "grid_status": telemetry["carbon_gco2_per_kwh"],
        "tariffs": telemetry["cost_usd_per_kwh"],
        "grid_source": "simulated",
        "jobs": generate_mock_jobs(num_jobs=4),
        "assignments": None,
        "baseline_assignments": None,
        "comparison": None,
        "router": None,
        "model": None,
        "optimized": False,
        "num_jobs": 4,
        "routing_mode": "pareto",
        "carbon_weight": 0.6,
        "use_forecast": False,
        "baseline_type": "static",
        "forecast": None,
        "deferral": None,
        "run_history": [],
        "rr_index": 0,
        "custom_jobs_loaded": False,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def _refresh_telemetry(fluctuate: bool = False, reload_jobs: bool = True) -> None:
    telemetry = _load_grid(fluctuate=fluctuate)
    st.session_state.grid_telemetry = telemetry
    st.session_state.grid_status = telemetry["carbon_gco2_per_kwh"]
    st.session_state.tariffs = telemetry["cost_usd_per_kwh"]
    if reload_jobs and not st.session_state.custom_jobs_loaded:
        st.session_state.jobs = generate_mock_jobs(num_jobs=st.session_state.num_jobs)
    st.session_state.assignments = None
    st.session_state.baseline_assignments = None
    st.session_state.comparison = None
    st.session_state.optimized = False
    st.session_state.forecast = forecast_grid(st.session_state.grid_status, hours_ahead=12)
    st.session_state.deferral = recommend_deferral_window(
        st.session_state.grid_status, st.session_state.forecast
    )


def _update_forecast() -> None:
    st.session_state.forecast = forecast_grid(st.session_state.grid_status, hours_ahead=12)
    st.session_state.deferral = recommend_deferral_window(
        st.session_state.grid_status, st.session_state.forecast
    )


ROUTING_MODES = [
    "pareto",
    "cost_aware",
    "load_balanced",
    "auto",
    "mock",
    "gemini",
    "forecast",
]

ROUTING_MODE_LABELS = {
    "pareto": "Pareto (carbon ↓, cost ≤ baseline)",
    "cost_aware": "Cost-aware (weighted carbon + $)",
    "load_balanced": "Load-balanced (spread + green)",
    "auto": "Auto (Gemini or mock)",
    "mock": "Carbon-first mock",
    "gemini": "Gemini LLM (carbon-first)",
    "forecast": "Forecast deferral (carbon-first)",
}


def _run_optimization(include_baseline: bool = True) -> None:
    jobs = st.session_state.jobs
    grid = st.session_state.grid_status
    mode = st.session_state.routing_mode
    if (
        st.session_state.use_forecast
        and mode not in ("cost_aware", "pareto", "load_balanced", "forecast")
    ):
        mode = "forecast"

    with contextlib.redirect_stdout(io.StringIO()):
        assignments, meta = _route_jobs(
            jobs,
            grid,
            mode=mode,
            use_forecast=st.session_state.use_forecast,
            tariffs=st.session_state.tariffs,
            carbon_weight=st.session_state.carbon_weight,
        )

    st.session_state.assignments = assignments
    st.session_state.router = meta.get("router", "unknown")
    st.session_state.model = meta.get("model")
    st.session_state.optimized = True

    if include_baseline:
        if st.session_state.baseline_type == "round_robin":
            baseline = run_round_robin_scheduler(jobs, grid, st.session_state.rr_index)
            baseline_name = "Round-Robin"
            st.session_state.rr_index += len(jobs)
        else:
            baseline = run_static_default_scheduler(jobs, grid)
            baseline_name = "Static Default"
        st.session_state.baseline_assignments = baseline
        st.session_state.comparison = compare_schedulers(
            jobs, grid, assignments, baseline,
            eco_name=st.session_state.router or "EcoRouter",
            baseline_name=baseline_name,
            tariffs=st.session_state.tariffs,
        )

    eco_carbon = total_carbon_cost(jobs, grid, assignments)
    eco_cost = total_energy_cost_usd(jobs, st.session_state.tariffs, assignments)
    baseline_carbon = (
        st.session_state.comparison["baseline_total_gco2"]
        if st.session_state.comparison
        else None
    )
    st.session_state.run_history.insert(
        0,
        {
            "timestamp": _utc_now(),
            "router": st.session_state.router,
            "jobs": len(jobs),
            "eco_gco2": eco_carbon,
            "eco_cost_usd": eco_cost,
            "baseline_gco2": baseline_carbon,
            "saved_gco2": (baseline_carbon - eco_carbon) if baseline_carbon else None,
            "grid_source": st.session_state.grid_telemetry.get("source", "simulated"),
        },
    )
    st.session_state.run_history = st.session_state.run_history[:20]


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
            f'<span><strong>{region}</strong>{badge}</span><span>{value:,} gCO₂/kWh</span></div>'
            f'<div class="grid-bar-track"><div style="width:{width}%;height:100%;'
            f'background:{color};border-radius:999px;"></div></div></div>'
        )
    return "".join(rows)


def _assignment_status(
    job: dict[str, Any],
    assignment: dict[str, Any],
    greenest: str,
) -> str:
    if assignment.get("deferred"):
        return "⏳ Forecast deferral"
    if job.get("locality_constraint"):
        return "⚠ Locality constraint"
    if assignment["target_region"] == greenest:
        return "✓ Optimal carbon routing"
    return "Routed"


def _build_dispatch_table(
    jobs: list[dict[str, Any]],
    assignments: list[dict[str, Any]],
    grid: dict[str, int],
    greenest: str,
) -> pd.DataFrame:
    by_job = {a["job_id"]: a for a in assignments}
    rows: list[dict[str, Any]] = []
    for job in jobs:
        a = by_job.get(job["job_id"])
        if not a:
            continue
        region = a["target_region"]
        rows.append(
            {
                "Job ID": job["job_id"],
                "Workload": job["task"],
                "Priority": "Urgent" if job.get("is_urgent") else "Flexible",
                "Locality": _format_locality(job.get("locality_constraint")),
                "Routed To": region,
                "Hours": job["compute_hours"],
                "Est. Carbon (gCO₂)": grid[region] * job["compute_hours"],
                "Est. Cost ($)": round(
                    st.session_state.tariffs.get(region, 0.10) * job["compute_hours"], 2
                ),
                "Deadline (UTC)": job.get("deadline_utc", "—"),
                "SLA": "PASS" if a.get("sla_met", True) else "FAIL",
                "Status": _assignment_status(job, a, greenest),
                "Reasoning": a.get("reasoning", ""),
            }
        )
    return pd.DataFrame(rows)


def _render_dispatch_cards(
    jobs: list[dict[str, Any]],
    assignments: list[dict[str, Any]],
    grid: dict[str, int],
    greenest: str,
) -> None:
    by_job = {a["job_id"]: a for a in assignments}
    for job in jobs:
        a = by_job.get(job["job_id"])
        if not a:
            st.warning(f"No assignment for **{job['job_id']}** ({job['task']})")
            continue

        region = a["target_region"]
        carbon = grid[region] * job["compute_hours"]
        status = _assignment_status(job, a, greenest)

        with st.container(border=True):
            h1, h2 = st.columns([3, 1])
            with h1:
                st.markdown(f"**{job['task']}**")
                st.caption(f"`{job['job_id']}` · {job['compute_hours']}h · "
                          f"{'Urgent' if job.get('is_urgent') else 'Flexible'}")
            with h2:
                st.metric("Carbon", f"{carbon:,} gCO₂")

            st.markdown(f"**→ {region}**")

            if "Forecast deferral" in status:
                st.info(status)
            elif "Locality" in status:
                st.warning(status)
            elif "Optimal" in status:
                st.success(status)
            else:
                st.write(status)

            st.caption(a.get("reasoning", ""))


_init_session()
if st.session_state.forecast is None:
    _update_forecast()

# --- Sidebar ---
with st.sidebar:
    st.markdown("### ⚙️ Controls")
    cap = min(40, MAX_BATCH_JOBS)
    if st.session_state.num_jobs > cap:
        st.session_state.num_jobs = cap
    st.session_state.num_jobs = st.slider(
        "Jobs per batch", 2, cap, st.session_state.num_jobs,
        help=f"Simulate up to {cap} workloads per optimization run",
    )
    if st.session_state.routing_mode not in ROUTING_MODES:
        st.session_state.routing_mode = "pareto"
    st.session_state.routing_mode = st.selectbox(
        "Routing engine",
        ROUTING_MODES,
        index=ROUTING_MODES.index(st.session_state.routing_mode),
        format_func=lambda m: ROUTING_MODE_LABELS.get(m, m),
        help=(
            "Pareto: lower carbon without raising $/kWh vs baseline. "
            "Cost-aware: tune carbon vs cost with the slider below."
        ),
    )
    if st.session_state.routing_mode == "cost_aware":
        st.session_state.carbon_weight = st.slider(
            "Carbon vs cost weight",
            0.0,
            1.0,
            st.session_state.carbon_weight,
            0.05,
            help="1.0 = carbon only, 0.0 = cost only",
        )
    st.session_state.use_forecast = st.toggle(
        "Forecast-aware scheduling",
        value=st.session_state.use_forecast,
        help="Defer flexible jobs to greener forecast windows (carbon-first modes only)",
        disabled=st.session_state.routing_mode in ("cost_aware", "pareto", "load_balanced"),
    )
    st.session_state.baseline_type = st.radio(
        "A/B baseline",
        ["static", "round_robin"],
        format_func=lambda x: "Static default (us-east-1)" if x == "static" else "Round-robin",
    )
    new_source = st.selectbox(
        "Grid data source",
        ["simulated", "live"],
        index=0 if st.session_state.grid_source == "simulated" else 1,
        help="Live uses Electricity Maps API when ELECTRICITY_MAPS_API_KEY is set",
    )
    if new_source != st.session_state.grid_source:
        st.session_state.grid_source = new_source
        telemetry = get_grid_telemetry(source=new_source)
        st.session_state.grid_telemetry = telemetry
        st.session_state.grid_status = telemetry["carbon_gco2_per_kwh"]
        st.session_state.tariffs = telemetry["cost_usd_per_kwh"]
        _update_forecast()
        st.rerun()
    if st.button("🔄 Refresh Grid & Queue", use_container_width=True):
        st.session_state.custom_jobs_loaded = False
        _refresh_telemetry(fluctuate=False, reload_jobs=True)
        st.rerun()
    if st.button("📡 Simulate Grid Shift", use_container_width=True):
        _refresh_telemetry(fluctuate=True, reload_jobs=False)
        st.rerun()
    st.markdown("---")
    engine = "Mock" if _use_mock_llm() else "Gemini 2.5 Flash"
    live_key = bool(os.getenv("ELECTRICITY_MAPS_API_KEY", "").strip())
    st.caption(f"**LLM available:** {engine}")
    st.caption(f"**Electricity Maps:** {'configured' if live_key else 'not set (simulated fallback)'}")
    st.caption(f"**Grid source:** {st.session_state.grid_telemetry.get('source', 'simulated')}")
    st.caption(f"**Updated:** {_utc_now()}")

# --- Hero ---
st.markdown(
    """<div class="ecorouter-hero"><h1>🌱 EcoRouter</h1>
    <p>Carbon-aware AI workload orchestration with live telemetry, 12h forecasting,
    A/B baseline comparison, and a REST API.</p>
    <span class="ecorouter-pill">LLM Tool Calling</span>
    <span class="ecorouter-pill">Grid Forecasting</span>
    <span class="ecorouter-pill">A/B Carbon Analysis</span>
    <span class="ecorouter-pill">REST API</span>
    <span class="ecorouter-pill">FinOps $/kWh</span>
    <span class="ecorouter-pill">SLA Deadlines</span>
    <span class="ecorouter-pill">ESG Export</span>
    <span class="ecorouter-pill">Pareto Routing</span>
    <span class="ecorouter-pill">18 Regions</span></div>""",
    unsafe_allow_html=True,
)

grid = st.session_state.grid_status
tariffs = st.session_state.tariffs
jobs = st.session_state.jobs
greenest = min(grid, key=grid.get)

tab_dash, tab_optimizer, tab_forecast, tab_ab, tab_enterprise, tab_tools = st.tabs(
    [
        "📊 Live Dashboard",
        "🧭 Region Optimizer",
        "📈 Forecast & Deferral",
        "⚖️ A/B Comparison",
        "🏢 Enterprise",
        "🔧 Tools & API",
    ]
)

# ===================== TAB 1: DASHBOARD =====================
with tab_dash:
    cheapest = min(tariffs, key=tariffs.get)
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Regions", len(REGIONS))
    m2.metric("Greenest", f"{greenest} ({grid[greenest]})")
    m3.metric("Cheapest", f"{cheapest} (${tariffs[cheapest]:.3f})")
    m4.metric("Pending Jobs", len(jobs))
    m5.metric("Routing", ROUTING_MODE_LABELS.get(st.session_state.routing_mode, "—"))
    m6.metric("Grid Source", st.session_state.grid_telemetry.get("source", "simulated")[:12])

    c1, c2 = st.columns([1.1, 0.9])
    with c1:
        st.markdown("<p class='section-title'>🌍 Live Grid Telemetry</p>", unsafe_allow_html=True)
        df_grid = pd.DataFrame([{"Region": r, "gCO₂/kWh": grid[r]} for r in REGIONS])
        st.bar_chart(df_grid.set_index("Region"), color="#22c55e", height=260)
    with c2:
        st.markdown(_grid_bars_html(grid), unsafe_allow_html=True)

    st.info(
        "**Routing modes:** *Carbon-first* (mock/Gemini/forecast) minimizes gCO₂ and may "
        "increase cost when greener regions have higher tariffs. **Pareto** and **Cost-aware** "
        "balance sustainability with FinOps — recommended for production pilots."
    )

    st.markdown("<p class='section-title'>📋 Job Queue</p>", unsafe_allow_html=True)
    df_jobs = pd.DataFrame(jobs).copy()
    df_jobs["locality_constraint"] = df_jobs["locality_constraint"].apply(_format_locality)
    df_jobs["is_urgent"] = df_jobs["is_urgent"].map({True: "Urgent", False: "Flexible"})
    df_jobs["hours_to_deadline"] = df_jobs.apply(
        lambda r: (
            f"{hours_until_deadline(r.to_dict()):.1f}h"
            if hours_until_deadline(r.to_dict()) is not None
            else "—"
        ),
        axis=1,
    )
    st.dataframe(
        df_jobs.rename(columns={
            "job_id": "Job ID", "task": "Workload", "compute_hours": "Hours",
            "is_urgent": "Priority", "locality_constraint": "Locality",
            "deadline_utc": "Deadline (UTC)", "hours_to_deadline": "Time to SLA",
        }),
        use_container_width=True,
        hide_index=True,
    )

    if st.button("🚀 Run EcoRouter Optimization", type="primary", use_container_width=True):
        with st.spinner("Routing workloads…"):
            _run_optimization(include_baseline=True)
        st.rerun()

    if st.session_state.optimized and st.session_state.assignments:
        st.markdown("### ✅ Dispatch Summary")
        comp = st.session_state.comparison
        r1, r2, r3, r4, r5 = st.columns(5)
        r1.metric("Jobs Routed", len(st.session_state.assignments))
        eco_total = comp["eco_total_gco2"] if comp else total_carbon_cost(
            jobs, grid, st.session_state.assignments
        )
        eco_cost_total = comp["eco_total_cost_usd"] if comp else total_energy_cost_usd(
            jobs, tariffs, st.session_state.assignments
        )
        r2.metric("EcoRouter Carbon", f"{eco_total:,} gCO₂")
        r3.metric("EcoRouter Cost", f"${eco_cost_total:.2f}")
        if comp:
            r4.metric(
                "Carbon Saved",
                f"{comp['carbon_saved_gco2']:,} gCO₂",
                f"{comp['savings_pct']}%",
            )
            r5.metric(
                "Cost Saved",
                f"${comp['cost_saved_usd']:.2f}",
                f"{comp['cost_savings_pct']}%",
            )
            tradeoff = comp.get("tradeoff_type", "")
            if tradeoff == "win_win":
                st.success(comp.get("tradeoff_message", ""))
            elif tradeoff == "carbon_tradeoff":
                st.warning(comp.get("tradeoff_message", ""))
            elif comp.get("tradeoff_message"):
                st.info(comp.get("tradeoff_message", ""))
        st.caption(f"Engine: **{st.session_state.router}**")

        dispatch_df = _build_dispatch_table(
            jobs, st.session_state.assignments, grid, greenest
        )
        st.markdown("#### Assignment overview")
        st.dataframe(dispatch_df, use_container_width=True, hide_index=True)

        load_df = pd.DataFrame(compute_load_distribution(st.session_state.assignments))
        active_load = load_df[load_df["jobs"] > 0]
        if not active_load.empty:
            st.markdown("#### Regional load distribution")
            st.bar_chart(active_load.set_index("region")["jobs"], height=200)
            st.caption(
                f"Jobs spread across **{len(active_load)}** of {len(REGIONS)} regions."
            )

        with st.expander("Per-job detail cards"):
            _render_dispatch_cards(jobs, st.session_state.assignments, grid, greenest)

# ===================== TAB 2: REGION OPTIMIZER =====================
with tab_optimizer:
    st.markdown("<p class='section-title'>🧭 Region Optimizer Tools</p>", unsafe_allow_html=True)
    st.caption(
        f"Explore all **{len(REGIONS)}** regions — ranked by composite carbon+cost score "
        "and Pareto eligibility vs us-east-1 baseline."
    )

    matrix = region_score_matrix(
        grid, tariffs, carbon_weight=st.session_state.carbon_weight
    )
    matrix_df = pd.DataFrame(matrix).rename(columns={
        "region": "Region",
        "carbon_gco2_per_kwh": "Carbon (gCO₂/kWh)",
        "tariff_usd_per_kwh": "$/kWh",
        "composite_score": "Score (lower=better)",
        "pareto_vs_baseline": "Pareto vs baseline",
        "rank": "Rank",
        "carbon_vs_baseline_pct": "Carbon Δ%",
        "cost_vs_baseline_pct": "Cost Δ%",
    })
    st.dataframe(matrix_df, use_container_width=True, hide_index=True)

    geo_df = pd.DataFrame([
        {
            "region": r,
            "label": REGION_GEO[r]["label"],
            "lat": REGION_GEO[r]["lat"],
            "lon": REGION_GEO[r]["lon"],
            "carbon": grid[r],
            "tariff": tariffs[r],
        }
        for r in REGIONS
    ])
    st.markdown("#### Global carbon map (bubble size = carbon intensity)")
    st.scatter_chart(
        geo_df,
        x="lon",
        y="lat",
        size="carbon",
        color="tariff",
        height=360,
    )

    st.markdown("#### What-if job analyzer")
    w1, w2, w3, w4 = st.columns(4)
    wi_hours = w1.number_input("Compute hours", 1, 168, 12, key="wi_hours")
    wi_urgent = w2.checkbox("Urgent", key="wi_urgent")
    wi_locality = w3.selectbox(
        "Locality lock",
        ["Any region"] + REGIONS,
        key="wi_locality",
    )
    wi_weight = w4.slider("Carbon weight", 0.0, 1.0, st.session_state.carbon_weight, 0.05, key="wi_weight")
    locality_val = None if wi_locality == "Any region" else wi_locality
    wi = what_if_analyze(
        int(wi_hours), grid, tariffs,
        is_urgent=wi_urgent, locality=locality_val, carbon_weight=wi_weight,
    )
    rec_df = pd.DataFrame([
        {"Mode": k, **{kk: vv for kk, vv in v.items() if kk != "reasoning"}}
        for k, v in wi["recommendations"].items()
    ])
    st.dataframe(rec_df, use_container_width=True, hide_index=True)
    for mode, data in wi["recommendations"].items():
        st.caption(f"**{mode}:** {data.get('reasoning', '')}")

# ===================== TAB 3: FORECAST =====================
with tab_forecast:
    st.markdown("<p class='section-title'>📈 12-Hour Carbon Intensity Forecast</p>", unsafe_allow_html=True)
    st.caption("Diurnal solar/wind model with mean-reversion — enables proactive scheduling.")

    if st.button("🔮 Regenerate Forecast", use_container_width=False):
        _update_forecast()
        st.rerun()

    deferral = st.session_state.deferral or {}
    f1, f2, f3 = st.columns(3)
    f1.metric("Greenest Now", deferral.get("current_greenest", greenest))
    f2.metric("Best Forecast Region", deferral.get("recommended_region", "—"))
    f3.metric("Forecast Savings", f"{deferral.get('estimated_savings_pct', 0)}%")

    if deferral.get("should_defer"):
        st.info(f"**Deferral recommended:** {deferral.get('rationale', '')}")
    else:
        st.success(deferral.get("rationale", "Dispatch flexible jobs now."))

    forecast = st.session_state.forecast or []
    df_fc = pd.DataFrame(forecast_to_dataframe(forecast))
    top_regions = sorted(REGIONS, key=lambda r: grid[r])[:8]
    st.caption(f"Forecast chart shows 8 greenest regions (of {len(REGIONS)} total).")
    st.line_chart(
        df_fc[df_fc["Region"].isin(top_regions)].pivot_table(
            index="Hours Ahead", columns="Region", values="Carbon Intensity (gCO₂/kWh)"
        ),
        height=320,
    )

    with st.expander("Forecast data table"):
        st.dataframe(df_fc, use_container_width=True, hide_index=True)

    st.markdown("#### How forecast-aware routing works")
    st.markdown(
        """
        - **Urgent jobs** → dispatched immediately to the greenest region now.
        - **Locality-locked jobs** → always routed to the required region.
        - **Flexible jobs** → if a ≥12% greener window exists within 12h, the agent
          recommends deferral to that region/time (enable via sidebar toggle).
        """
    )

# ===================== TAB 3: A/B COMPARISON =====================
with tab_ab:
    st.markdown("<p class='section-title'>⚖️ EcoRouter vs Baseline Scheduler</p>", unsafe_allow_html=True)
    st.caption("Quantify carbon savings against naive industry-default policies.")

    if not st.session_state.comparison:
        st.info("Run **EcoRouter Optimization** on the Live Dashboard tab to generate comparison data.")
    else:
        comp = st.session_state.comparison
        a1, a2, a3, a4 = st.columns(4)
        a1.metric("EcoRouter Carbon", f"{comp['eco_total_gco2']:,} gCO₂")
        a2.metric("Baseline Carbon", f"{comp['baseline_total_gco2']:,} gCO₂")
        a3.metric(
            "Carbon Saved",
            f"{comp['carbon_saved_gco2']:,} gCO₂",
            f"{comp['savings_pct']}%",
        )
        a4.metric(
            "Cost Saved",
            f"${comp['cost_saved_usd']:.2f}",
            f"{comp['cost_savings_pct']}%",
        )

        tradeoff = comp.get("tradeoff_type", "")
        if tradeoff == "win_win":
            st.success(comp.get("tradeoff_message", ""))
        elif tradeoff == "carbon_tradeoff":
            st.warning(comp.get("tradeoff_message", ""))
        elif comp.get("tradeoff_message"):
            st.info(comp.get("tradeoff_message", ""))

        c1, c2 = st.columns(2)
        with c1:
            chart_df = pd.DataFrame({
                comp["eco_name"]: [comp["eco_total_gco2"]],
                comp["baseline_name"]: [comp["baseline_total_gco2"]],
            })
            st.markdown("**Carbon (gCO₂)**")
            st.bar_chart(chart_df, color=["#22c55e", "#ef4444"], height=240)
        with c2:
            cost_df = pd.DataFrame({
                comp["eco_name"]: [comp["eco_total_cost_usd"]],
                comp["baseline_name"]: [comp["baseline_total_cost_usd"]],
            })
            st.markdown("**Energy cost (USD)**")
            st.bar_chart(cost_df, color=["#22c55e", "#ef4444"], height=240)

        merged = pd.DataFrame(comp["eco_per_job"]).merge(
            pd.DataFrame(comp["baseline_per_job"]),
            on="job_id",
            suffixes=("_eco", "_baseline"),
        )
        merged["carbon_saved"] = merged["carbon_gco2_baseline"] - merged["carbon_gco2_eco"]
        st.markdown("#### Per-job carbon breakdown")
        st.dataframe(
            merged[[
                "job_id", "task_eco", "target_region_eco", "carbon_gco2_eco",
                "target_region_baseline", "carbon_gco2_baseline", "carbon_saved",
            ]].rename(columns={
                "job_id": "Job ID", "task_eco": "Workload",
                "target_region_eco": "EcoRouter Region", "carbon_gco2_eco": "Eco gCO₂",
                "target_region_baseline": "Baseline Region",
                "carbon_gco2_baseline": "Baseline gCO₂", "carbon_saved": "Saved gCO₂",
            }),
            use_container_width=True,
            hide_index=True,
        )

        if tradeoff == "win_win":
            st.markdown(
                f"**Summary:** {comp['carbon_saved_gco2']:,} gCO₂ and "
                f"${comp['cost_saved_usd']:.2f} saved vs {comp['baseline_name']}."
            )
        elif tradeoff == "carbon_tradeoff":
            st.markdown(
                f"**Summary:** {comp['carbon_saved_gco2']:,} gCO₂ saved, but energy cost "
                f"increased by **${abs(comp['cost_saved_usd']):.2f}**. "
                "Switch to **Pareto** or **Cost-aware** routing to avoid this."
            )
        elif comp["savings_pct"] <= 0 and comp["cost_savings_pct"] <= 0:
            st.warning("Baseline matched EcoRouter — likely all jobs had locality constraints.")

# ===================== TAB 4: ENTERPRISE =====================
with tab_enterprise:
    st.markdown("<p class='section-title'>🏢 Enterprise — BYO Jobs, SLA & ESG Reporting</p>", unsafe_allow_html=True)
    st.caption("Upload your workload queue, enforce SLA deadlines, and export Scope 2 reports for compliance.")

    up1, up2 = st.columns(2)
    with up1:
        st.markdown("#### Upload job queue (JSON)")
        json_upload = st.file_uploader("JSON file", type=["json"], key="json_jobs")
        json_text = st.text_area("Or paste JSON", value=sample_jobs_json(), height=180, key="json_paste")
        if st.button("Load JSON jobs", use_container_width=True):
            try:
                text = json_upload.getvalue().decode() if json_upload else json_text
                st.session_state.jobs = parse_jobs_from_json(text)
                st.session_state.custom_jobs_loaded = True
                st.session_state.assignments = None
                st.session_state.comparison = None
                st.session_state.optimized = False
                st.success(f"Loaded {len(st.session_state.jobs)} job(s).")
                st.rerun()
            except Exception as exc:
                st.error(f"Invalid JSON: {exc}")

    with up2:
        st.markdown("#### Upload job queue (CSV)")
        st.caption("Columns: job_id, task, compute_hours, is_urgent, locality_constraint, deadline_utc")
        csv_upload = st.file_uploader("CSV file", type=["csv"], key="csv_jobs")
        if st.button("Load CSV jobs", use_container_width=True, disabled=csv_upload is None):
            try:
                st.session_state.jobs = parse_jobs_from_csv(csv_upload.getvalue().decode())
                st.session_state.custom_jobs_loaded = True
                st.session_state.assignments = None
                st.session_state.comparison = None
                st.session_state.optimized = False
                st.success(f"Loaded {len(st.session_state.jobs)} job(s).")
                st.rerun()
            except Exception as exc:
                st.error(f"Invalid CSV: {exc}")

    st.markdown(f"#### Regional tariffs & carbon ({len(REGIONS)} regions)")
    tariff_df = pd.DataFrame([
        {
            "Region": r,
            "USD/kWh": tariffs[r],
            "Carbon (gCO₂/kWh)": grid[r],
            "Pareto vs us-east-1": (
                "✓ strict"
                if grid[r] < grid["us-east-1"] and tariffs[r] <= tariffs["us-east-1"]
                else ("~ carbon only" if grid[r] < grid["us-east-1"] else "—")
            ),
        }
        for r in REGIONS
    ])
    st.dataframe(tariff_df, use_container_width=True, hide_index=True)

    st.markdown("#### ESG / Scope 2 PDF export")
    if st.session_state.optimized and st.session_state.assignments:
        pdf_bytes = generate_esg_pdf(
            jobs=jobs,
            grid_status=grid,
            assignments=st.session_state.assignments,
            comparison=st.session_state.comparison,
            grid_source=st.session_state.grid_telemetry.get("source", "simulated"),
            router=st.session_state.router or "EcoRouter",
            tariffs=tariffs,
        )
        st.download_button(
            "⬇️ Download ESG Report (PDF)",
            data=pdf_bytes,
            file_name=f"ecorouter_esg_{datetime.now(timezone.utc).strftime('%Y%m%d')}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
        st.caption("Share with sustainability / compliance teams for Scope 2 workload reporting.")
    else:
        st.info("Run **EcoRouter Optimization** first to generate the ESG report.")

    if st.session_state.custom_jobs_loaded:
        st.success("Using **custom uploaded** job queue (refresh grid will not replace jobs).")

# ===================== TAB 5: TOOLS & API =====================
with tab_tools:
    st.markdown("<p class='section-title'>🔧 Tools, Export & REST API</p>", unsafe_allow_html=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### Export last run")
        if st.session_state.optimized and st.session_state.assignments:
            export_payload = {
                "timestamp": _utc_now(),
                "grid_status": grid,
                "jobs": jobs,
                "eco_assignments": st.session_state.assignments,
                "baseline_assignments": st.session_state.baseline_assignments,
                "comparison": st.session_state.comparison,
                "forecast": st.session_state.forecast,
            }
            st.download_button(
                "⬇️ Download JSON report",
                data=json.dumps(export_payload, indent=2, default=str),
                file_name=f"ecorouter_run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.json",
                mime="application/json",
                use_container_width=True,
            )
            if st.session_state.comparison:
                csv_df = pd.DataFrame(st.session_state.comparison["eco_per_job"])
                st.download_button(
                    "⬇️ Download CSV (eco per-job)",
                    data=csv_df.to_csv(index=False),
                    file_name="ecorouter_per_job.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
        else:
            st.caption("Run an optimization first to enable exports.")

    with col_b:
        st.markdown("#### REST API (local)")
        st.code(
            "uvicorn api.server:app --reload --app-dir src --port 8000",
            language="bash",
        )
        st.markdown("""
**Endpoints:**
- `GET /api/v1/regions` — 18-region catalog with geo + tariffs
- `GET /api/v1/regions/matrix?carbon_weight=0.6` — ranked optimizer matrix
- `POST /api/v1/analyze?compute_hours=12&mode=pareto` — what-if job analyzer
- `GET /api/v1/grid?source=live` — carbon + $/kWh tariffs
- `POST /api/v1/optimize?num_jobs=24&mode=load_balanced` — batch optimizer (up to 50)
- `POST /api/v1/jobs` — BYO job queue (JSON body)
- `GET /api/v1/compare?baseline=static` — A/B carbon + cost analysis
        """)
        st.markdown("**BYO jobs example:**")
        st.code(
            """curl -X POST http://localhost:8000/api/v1/jobs \\
  -H "Content-Type: application/json" \\
  -d '{"jobs":[{"job_id":"t1","task":"train_llama3_8b","compute_hours":12,"deadline_utc":"2026-06-10T18:00:00Z"}],"mode":"forecast"}'""",
            language="bash",
        )

    st.markdown("#### Run history (this session)")
    if st.session_state.run_history:
        st.dataframe(pd.DataFrame(st.session_state.run_history), use_container_width=True, hide_index=True)
    else:
        st.caption("No runs yet.")

    st.markdown("#### Cloudflare edge (roadmap)")
    st.caption(
        "`wrangler.jsonc` is configured for static asset deployment. "
        "The FastAPI service can be containerized or proxied behind a Worker for production edge routing."
    )
