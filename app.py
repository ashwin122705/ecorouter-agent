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

from agents.ecorouter import _route_jobs, _use_mock_llm  # noqa: E402
from sim_environment.baseline_scheduler import (  # noqa: E402
    run_round_robin_scheduler,
    run_static_default_scheduler,
)
from sim_environment.carbon_metrics import compare_schedulers, total_carbon_cost  # noqa: E402
from sim_environment.grid_data import REGIONS, fluctuate_grid_status, get_live_grid_status  # noqa: E402
from sim_environment.grid_forecast import (  # noqa: E402
    forecast_grid,
    forecast_to_dataframe,
    recommend_deferral_window,
)
from sim_environment.job_queue import generate_mock_jobs  # noqa: E402

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
    defaults: dict[str, Any] = {
        "grid_status": get_live_grid_status(),
        "jobs": generate_mock_jobs(num_jobs=4),
        "assignments": None,
        "baseline_assignments": None,
        "comparison": None,
        "router": None,
        "model": None,
        "optimized": False,
        "num_jobs": 4,
        "routing_mode": "auto",
        "use_forecast": False,
        "baseline_type": "static",
        "forecast": None,
        "deferral": None,
        "run_history": [],
        "rr_index": 0,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def _refresh_telemetry(fluctuate: bool = False) -> None:
    if fluctuate and st.session_state.grid_status:
        st.session_state.grid_status = fluctuate_grid_status(st.session_state.grid_status)
    else:
        st.session_state.grid_status = get_live_grid_status()
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


def _run_optimization(include_baseline: bool = True) -> None:
    jobs = st.session_state.jobs
    grid = st.session_state.grid_status
    mode = "forecast" if st.session_state.use_forecast else st.session_state.routing_mode

    with contextlib.redirect_stdout(io.StringIO()):
        assignments, meta = _route_jobs(jobs, grid, mode=mode, use_forecast=st.session_state.use_forecast)

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
        )

    eco_carbon = total_carbon_cost(jobs, grid, assignments)
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
            "baseline_gco2": baseline_carbon,
            "saved_gco2": (baseline_carbon - eco_carbon) if baseline_carbon else None,
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
                "Locality": job.get("locality_constraint") or "—",
                "Routed To": region,
                "Hours": job["compute_hours"],
                "Est. Carbon (gCO₂)": grid[region] * job["compute_hours"],
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
    st.session_state.num_jobs = st.slider("Jobs per batch", 2, 8, st.session_state.num_jobs)
    st.session_state.routing_mode = st.selectbox(
        "Routing engine",
        ["auto", "mock", "gemini", "forecast"],
        index=["auto", "mock", "gemini", "forecast"].index(st.session_state.routing_mode),
        help="auto = Gemini if API key present, else mock",
    )
    st.session_state.use_forecast = st.toggle(
        "Forecast-aware scheduling",
        value=st.session_state.use_forecast,
        help="Defer flexible jobs to greener forecast windows",
    )
    st.session_state.baseline_type = st.radio(
        "A/B baseline",
        ["static", "round_robin"],
        format_func=lambda x: "Static default (us-east-1)" if x == "static" else "Round-robin",
    )
    if st.button("🔄 Refresh Grid & Queue", use_container_width=True):
        _refresh_telemetry(fluctuate=False)
        st.rerun()
    if st.button("📡 Simulate Grid Shift", use_container_width=True):
        _refresh_telemetry(fluctuate=True)
        st.rerun()
    st.markdown("---")
    engine = "Mock" if _use_mock_llm() else "Gemini 2.5 Flash"
    st.caption(f"**LLM available:** {engine}")
    st.caption(f"**Updated:** {_utc_now()}")

# --- Hero ---
st.markdown(
    """<div class="ecorouter-hero"><h1>🌱 EcoRouter</h1>
    <p>Carbon-aware AI workload orchestration with live telemetry, 12h forecasting,
    A/B baseline comparison, and a REST API.</p>
    <span class="ecorouter-pill">LLM Tool Calling</span>
    <span class="ecorouter-pill">Grid Forecasting</span>
    <span class="ecorouter-pill">A/B Carbon Analysis</span>
    <span class="ecorouter-pill">REST API</span></div>""",
    unsafe_allow_html=True,
)

grid = st.session_state.grid_status
jobs = st.session_state.jobs
greenest = min(grid, key=grid.get)

tab_dash, tab_forecast, tab_ab, tab_tools = st.tabs(
    ["📊 Live Dashboard", "📈 Forecast & Deferral", "⚖️ A/B Comparison", "🔧 Tools & API"]
)

# ===================== TAB 1: DASHBOARD =====================
with tab_dash:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Greenest Region", greenest)
    m2.metric("Intensity", f"{grid[greenest]} gCO₂/kWh")
    m3.metric("Pending Jobs", len(jobs))
    m4.metric("Avg Network", f"{sum(grid.values()) / len(grid):.0f} gCO₂/kWh")

    c1, c2 = st.columns([1.1, 0.9])
    with c1:
        st.markdown("<p class='section-title'>🌍 Live Grid Telemetry</p>", unsafe_allow_html=True)
        df_grid = pd.DataFrame([{"Region": r, "gCO₂/kWh": grid[r]} for r in REGIONS])
        st.bar_chart(df_grid.set_index("Region"), color="#22c55e", height=260)
    with c2:
        st.markdown(_grid_bars_html(grid), unsafe_allow_html=True)

    st.markdown("<p class='section-title'>📋 Job Queue</p>", unsafe_allow_html=True)
    df_jobs = pd.DataFrame(jobs).copy()
    df_jobs["locality_constraint"] = df_jobs["locality_constraint"].fillna("—")
    df_jobs["is_urgent"] = df_jobs["is_urgent"].map({True: "Urgent", False: "Flexible"})
    st.dataframe(
        df_jobs.rename(columns={
            "job_id": "Job ID", "task": "Workload", "compute_hours": "Hours",
            "is_urgent": "Priority", "locality_constraint": "Locality",
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
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Jobs Routed", len(st.session_state.assignments))
        eco_total = comp["eco_total_gco2"] if comp else total_carbon_cost(
            jobs, grid, st.session_state.assignments
        )
        r2.metric("EcoRouter Carbon", f"{eco_total:,} gCO₂")
        if comp:
            r3.metric("Carbon Saved vs Baseline", f"{comp['carbon_saved_gco2']:,} gCO₂", f"{comp['savings_pct']}%")
            r4.metric("Baseline Carbon", f"{comp['baseline_total_gco2']:,} gCO₂")
        st.caption(f"Engine: **{st.session_state.router}**")

        dispatch_df = _build_dispatch_table(
            jobs, st.session_state.assignments, grid, greenest
        )
        st.markdown("#### Assignment overview")
        st.dataframe(dispatch_df, use_container_width=True, hide_index=True)

        st.markdown("#### Per-job details")
        _render_dispatch_cards(jobs, st.session_state.assignments, grid, greenest)

# ===================== TAB 2: FORECAST =====================
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
    st.line_chart(
        df_fc.pivot_table(
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
        a1, a2, a3 = st.columns(3)
        a1.metric("EcoRouter Total", f"{comp['eco_total_gco2']:,} gCO₂")
        a2.metric(f"{comp['baseline_name']} Total", f"{comp['baseline_total_gco2']:,} gCO₂")
        a3.metric(
            "Savings",
            f"{comp['carbon_saved_gco2']:,} gCO₂",
            f"{comp['savings_pct']}% reduction",
        )

        chart_df = pd.DataFrame({
            comp["eco_name"]: [comp["eco_total_gco2"]],
            comp["baseline_name"]: [comp["baseline_total_gco2"]],
        })
        st.bar_chart(chart_df, color=["#22c55e", "#ef4444"], height=280)

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

        if comp["savings_pct"] > 0:
            st.success(
                f"EcoRouter avoided **{comp['carbon_saved_gco2']:,} gCO₂** "
                f"({comp['savings_pct']}%) vs {comp['baseline_name']} on this batch."
            )
        else:
            st.warning("Baseline matched EcoRouter — likely all jobs had locality constraints.")

# ===================== TAB 4: TOOLS & API =====================
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
- `GET /api/v1/grid` — live telemetry
- `GET /api/v1/forecast?hours=12` — carbon forecast + deferral advice
- `POST /api/v1/optimize?num_jobs=4&mode=forecast` — run optimizer
- `GET /api/v1/compare?baseline=static` — A/B carbon analysis
        """)

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
