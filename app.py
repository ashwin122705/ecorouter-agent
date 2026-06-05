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
    BATCH_LOCALITY_LABELS,
    BATCH_LOCALITY_MODES,
    build_job_batch,
    parse_jobs_from_csv,
    parse_jobs_from_json,
    sample_jobs_json,
)
from sim_environment.sla import hours_until_deadline  # noqa: E402
from theme_css import assignment_row_colors, build_theme_css  # noqa: E402

load_dotenv(ROOT / ".env")

st.set_page_config(page_title="EcoRouter", page_icon="🌱", layout="wide", initial_sidebar_state="expanded")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S UTC")


CARBON_GRADIENT_STOPS: list[tuple[float, str]] = [
    (0.0, "#ecfdf5"),
    (0.18, "#86efac"),
    (0.40, "#fde047"),
    (0.62, "#fb923c"),
    (0.82, "#dc2626"),
    (1.0, "#450a0a"),
]


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _lerp_hex(c1: str, c2: str, t: float) -> str:
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    return "#{:02x}{:02x}{:02x}".format(
        int(r1 + (r2 - r1) * t),
        int(g1 + (g2 - g1) * t),
        int(b1 + (b2 - b1) * t),
    )


def _carbon_gradient_color(ratio: float) -> str:
    """Smooth light → dark scale for carbon intensity (0 = greenest, 1 = dirtiest)."""
    ratio = max(0.0, min(1.0, ratio))
    for i in range(len(CARBON_GRADIENT_STOPS) - 1):
        r0, c0 = CARBON_GRADIENT_STOPS[i]
        r1, c1 = CARBON_GRADIENT_STOPS[i + 1]
        if r0 <= ratio <= r1:
            span = r1 - r0 or 1.0
            return _lerp_hex(c0, c1, (ratio - r0) / span)
    return CARBON_GRADIENT_STOPS[-1][1]


def _tab_intro(text: str) -> None:
    st.markdown(f'<div class="tab-intro">{text}</div>', unsafe_allow_html=True)


THEME = "dark"


def _render_hero(
    region_count: int,
    grid: dict[str, int],
    greenest: str,
    comparison: dict[str, Any] | None = None,
    user_name: str = "",
    user_home_region: str | None = None,
    locality_mode: str = "scenario_mix",
) -> None:
    """Top title block with live impact stats."""
    baseline_region = "us-east-1"
    baseline_intensity = grid.get(baseline_region, 380)
    greenest_intensity = grid[greenest]
    potential_pct = round(
        100 * (1 - greenest_intensity / max(baseline_intensity, 1)),
        1,
    )

    if comparison and comparison.get("carbon_saved_gco2", 0) > 0:
        impact_value = f"{comparison['carbon_saved_gco2']:,} gCO₂"
        impact_label = f"{comparison['savings_pct']}% vs baseline"
        impact_class = "hero-stat-highlight"
        impact_sub = (
            f"EcoRouter beat {comparison.get('baseline_name', 'baseline')} "
            f"on this batch"
        )
    else:
        impact_value = f"{potential_pct}%"
        impact_label = "carbon upside vs us-east-1"
        impact_class = "hero-stat-highlight"
        impact_sub = (
            f"Run optimization to route flexible jobs toward {greenest} "
            f"({greenest_intensity:,} gCO₂/kWh)"
        )

    name = user_name.strip()
    title = f"🌱 EcoRouter — {name}" if name else "🌱 EcoRouter Agent"
    eyebrow = "Stanford CS 153 · One-Person Frontier Lab · Automation / Agent Systems"
    if name and user_home_region:
        eyebrow = f"{eyebrow} · {_region_label(user_home_region)} workspace"
    if name or locality_mode != "scenario_mix":
        if locality_mode == "home_region" and user_home_region:
            personal_lead = (
                f"Your batch locks workloads to {_region_label(user_home_region)}."
            )
        elif locality_mode == "any_region":
            personal_lead = "Your batch is carbon-flexible across all regions."
        elif locality_mode == "specific_region":
            personal_lead = "Your batch locks every job to the region you selected."
        else:
            personal_lead = "Your batch uses realistic enterprise workload scenarios."
    else:
        personal_lead = ""

    st.markdown(
        f'<div class="ecorouter-hero">'
        f'<div class="hero-top">'
        f'<div class="hero-brand">'
        f'<div class="hero-eyebrow">{eyebrow}</div>'
        f"<h1>{title}</h1>"
        f'<p class="hero-lead">Autonomous workload routing across {region_count} AWS regions. '
        f"EcoRouter reads live grid carbon and cost telemetry, then dispatches AI jobs to "
        f"greener regions while respecting SLA deadlines and your region preferences. "
        f"{personal_lead} {impact_sub}.</p>"
        f"</div>"
        f'<div class="hero-impact">'
        f'<div class="hero-stat"><span class="hero-stat-num">{region_count}</span>'
        f'<span class="hero-stat-lbl">Regions</span></div>'
        f'<div class="hero-stat"><span class="hero-stat-num">{greenest}</span>'
        f'<span class="hero-stat-lbl">{greenest_intensity:,} gCO₂/kWh</span></div>'
        f'<div class="hero-stat {impact_class}"><span class="hero-stat-num">{impact_value}</span>'
        f'<span class="hero-stat-lbl">{impact_label}</span></div>'
        f'<div class="hero-stat"><span class="hero-stat-num">{baseline_region}</span>'
        f'<span class="hero-stat-lbl">{baseline_intensity:,} gCO₂/kWh</span></div>'
        f"</div></div>"
        f'<div class="hero-pills">'
        f'<span class="ecorouter-pill">LLM Tool Calling</span>'
        f'<span class="ecorouter-pill">Pareto Routing</span>'
        f'<span class="ecorouter-pill">12h Forecasting</span>'
        f'<span class="ecorouter-pill">A/B Carbon Analysis</span>'
        f'<span class="ecorouter-pill">FinOps $/kWh</span>'
        f'<span class="ecorouter-pill">REST API</span>'
        f'<span class="ecorouter-pill">{region_count} Regions</span>'
        f"</div></div>",
        unsafe_allow_html=True,
    )


def _render_stat_cards(
    cards: list[tuple[str, str, str, str | None, str]],
) -> None:
    """Render summary metrics with large contrasting icons (icon, label, value, delta, accent)."""
    parts: list[str] = [f'<div class="stat-grid" style="--stat-count:{len(cards)}">']
    for icon, label, value, delta, accent in cards:
        delta_html = f'<div class="stat-delta">{delta}</div>' if delta else ""
        parts.append(
            f'<div class="stat-card">'
            f'<div class="stat-icon-wrap stat-icon-{accent}">{icon}</div>'
            f'<div class="stat-body">'
            f'<div class="stat-label">{label}</div>'
            f'<div class="stat-value">{value}</div>'
            f"{delta_html}"
            f"</div></div>"
        )
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def _format_locality(value: str | None) -> str:
    """Human-readable locality — None means the job can run in any region."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "Any region"
    text = str(value).strip()
    if text.lower() in {"", "—", "-", "none", "null", "nan"}:
        return "Any region"
    label = REGION_GEO.get(text, {}).get("label", "")
    return f"{text} ({label})" if label else text


def _region_label(region: str) -> str:
    label = REGION_GEO.get(region, {}).get("label", "")
    return f"{region} ({label})" if label else region


def _intensity_color(value: int, max_val: int, min_val: int | None = None) -> str:
    lo = min_val if min_val is not None else 0
    span = max(max_val - lo, 1)
    ratio = (value - lo) / span
    return _carbon_gradient_color(ratio)


def _render_scrollable_carbon_chart(
    grid: dict[str, int],
    tariffs: dict[str, float],
    bar_width: int = 56,
    chart_height: int = 180,
) -> None:
    """Horizontal-scroll bar chart with a shared baseline for every bar."""
    greenest = min(grid, key=grid.get)
    max_val = max(grid.values()) or 1
    min_val = min(grid.values()) or 0
    bar_slots: list[str] = []
    label_slots: list[str] = []

    for region in REGIONS:
        value = grid[region]
        h_pct = max(6, int((value / max_val) * 100))
        color = _intensity_color(value, max_val, min_val)
        geo = REGION_GEO.get(region, {})
        badge = (
            '<span class="bar-badge-green">GREENEST</span>'
            if region == greenest
            else "&nbsp;"
        )
        bar_slots.append(
            f'<div class="carbon-bar-slot" style="width:{bar_width}px">'
            f'<div class="carbon-bar-value">{value:,}</div>'
            f'<div class="carbon-bar-wrap" style="height:{chart_height}px">'
            f'<div class="carbon-bar-fill" style="height:{h_pct}%;background:{color}"></div>'
            f"</div></div>"
        )
        label_slots.append(
            f'<div class="carbon-label-slot" style="width:{bar_width}px">'
            f'<div class="carbon-bar-region">{region}</div>'
            f'<div class="carbon-bar-label">{geo.get("label", "")}</div>'
            f'<div class="carbon-bar-tariff">${tariffs.get(region, 0):.3f}/kWh</div>'
            f'<div class="carbon-badge-slot">{badge}</div>'
            f"</div>"
        )

    inner_w = len(REGIONS) * (bar_width + 10) + 20
    st.markdown(
        f'<div class="carbon-scroll-hint">↔ Scroll horizontally — {len(REGIONS)} regions · '
        f'drag bar width in sidebar to enlarge</div>'
        f'<div class="carbon-chart-scroll">'
        f'<div class="carbon-chart-plot" style="min-width:{inner_w}px">'
        f'<div class="carbon-bars-row">{"".join(bar_slots)}</div>'
        f'<div class="carbon-baseline"></div>'
        f'<div class="carbon-labels-row">{"".join(label_slots)}</div>'
        f"</div></div>"
        f'<div class="carbon-legend">Carbon intensity scale'
        f'<div class="gradient-legend-bar"></div>'
        f'<div class="gradient-legend-labels">'
        f"<span>Light · low gCO₂</span><span>→</span><span>Dark · high gCO₂</span>"
        f"</div></div>",
        unsafe_allow_html=True,
    )


def _render_compact_carbon_strip(grid: dict[str, int], max_rows: int = 5) -> None:
    """Minimal horizontal bars when chart panel is collapsed."""
    greenest = min(grid, key=grid.get)
    max_val = max(grid.values()) or 1
    min_val = min(grid.values()) or 0
    sorted_regions = sorted(REGIONS, key=lambda r: grid[r])
    rows: list[str] = []
    for region in sorted_regions[:max_rows]:
        value = grid[region]
        width = int((value / max_val) * 100)
        color = _intensity_color(value, max_val, min_val)
        star = " ★" if region == greenest else ""
        rows.append(
            f'<div class="compact-grid-row">'
            f'<span style="width:110px;font-weight:600">{region}{star}</span>'
            f'<div class="compact-grid-track">'
            f'<div style="width:{width}%;height:100%;background:{color};border-radius:999px"></div>'
            f"</div>"
            f'<span style="width:70px;text-align:right;font-weight:700">{value:,}</span>'
            f"</div>"
        )
    st.markdown(
        f'<div class="panel-card">{"".join(rows)}'
        f'<div class="panel-muted" style="font-size:0.75rem;margin-top:6px">'
        f"Top {max_rows} shown · expand panel for all {len(REGIONS)} regions</div></div>",
        unsafe_allow_html=True,
    )


def _load_bar_color(jobs: int, max_jobs: int) -> str:
    """Green gradient — darker = more jobs in this batch."""
    if max_jobs <= 0:
        return "#22c55e"
    ratio = jobs / max_jobs
    stops = [(0.35, "#4ade80"), (0.65, "#22c55e"), (1.0, "#15803d")]
    for threshold, color in stops:
        if ratio <= threshold:
            return color
    return "#15803d"


def _render_load_distribution_chart(
    load_rows: pd.DataFrame | list[dict[str, Any]],
    *,
    chart_height: int = 300,
) -> None:
    """Tall vertical bars with white job-count labels; width scales with viewport."""
    if isinstance(load_rows, pd.DataFrame):
        rows = load_rows.sort_values("jobs", ascending=False).to_dict("records")
    else:
        rows = sorted(load_rows, key=lambda r: r["jobs"], reverse=True)
    rows = [r for r in rows if int(r["jobs"]) > 0]
    if not rows:
        return

    max_jobs = max(int(r["jobs"]) for r in rows) or 1
    bar_slots: list[str] = []
    label_slots: list[str] = []

    for row in rows:
        region = str(row["region"])
        jobs = int(row["jobs"])
        share = float(row.get("share_pct", 0))
        h_pct = max(16, int((jobs / max_jobs) * 100))
        fill_px = int(chart_height * h_pct / 100)
        color = _load_bar_color(jobs, max_jobs)
        geo = REGION_GEO.get(region, {})

        if fill_px >= 36:
            label_html = f'<span class="load-bar-top-label">{jobs}</span>'
            above_html = ""
        else:
            label_html = ""
            above_html = f'<div class="load-bar-value-above">{jobs}</div>'

        bar_slots.append(
            f'<div class="load-bar-slot">'
            f"{above_html}"
            f'<div class="load-bar-wrap" style="height:{chart_height}px">'
            f'<div class="load-bar-fill" style="height:{h_pct}%;background:{color}">'
            f"{label_html}"
            f"</div></div></div>"
        )
        label_slots.append(
            f'<div class="load-label-slot">'
            f'<div class="load-bar-region">{region}</div>'
            f'<div class="load-bar-share">{share:.0f}% of batch</div>'
            f'<div class="load-bar-geo">{geo.get("label", "")}</div>'
            f"</div>"
        )

    bar_count = len(rows)
    st.markdown(
        f'<div class="load-chart-panel">'
        f'<div class="load-chart-scroll">'
        f'<div class="load-chart-plot" style="--bar-count:{bar_count}">'
        f'<div class="load-bars-row">{"".join(bar_slots)}</div>'
        f'<div class="load-baseline"></div>'
        f'<div class="load-labels-row">{"".join(label_slots)}</div>'
        f"</div></div></div>",
        unsafe_allow_html=True,
    )


def _sync_grid_session() -> None:
    """Ensure grid/tariffs include every region (fixes stale Streamlit sessions)."""
    if "grid_status" not in st.session_state:
        return
    carbon = st.session_state.grid_status or {}
    tariffs = st.session_state.tariffs or {}
    src = st.session_state.get("grid_source", "simulated")
    fresh = get_grid_telemetry(source=src)
    base_carbon = fresh["carbon_gco2_per_kwh"]
    base_tariffs = fresh["cost_usd_per_kwh"]
    missing = [r for r in REGIONS if r not in carbon]
    extra = [r for r in carbon if r not in REGIONS]
    if not missing and not extra and len(tariffs) == len(REGIONS):
        return
    st.session_state.grid_status = {
        r: int(carbon.get(r, base_carbon[r])) for r in REGIONS
    }
    st.session_state.tariffs = {
        r: float(tariffs.get(r, base_tariffs[r])) for r in REGIONS
    }
    telemetry = dict(st.session_state.get("grid_telemetry") or fresh)
    telemetry["carbon_gco2_per_kwh"] = st.session_state.grid_status
    telemetry["cost_usd_per_kwh"] = st.session_state.tariffs
    telemetry["region_count"] = len(REGIONS)
    greenest = min(st.session_state.grid_status, key=st.session_state.grid_status.get)
    telemetry["greenest_region"] = greenest
    telemetry["greenest_intensity"] = st.session_state.grid_status[greenest]
    st.session_state.grid_telemetry = telemetry


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
        "jobs": [],
        "assignments": None,
        "baseline_assignments": None,
        "comparison": None,
        "router": None,
        "model": None,
        "optimized": False,
        "num_jobs": 6,
        "routing_mode": "pareto",
        "carbon_weight": 0.6,
        "use_forecast": False,
        "baseline_type": "static",
        "forecast": None,
        "deferral": None,
        "run_history": [],
        "rr_index": 0,
        "custom_jobs_loaded": False,
        "grid_chart_expanded": True,
        "carbon_bar_width": 56,
        "carbon_chart_height": 180,
        "user_display_name": "",
        "user_home_region": "us-east-1",
        "batch_locality_mode": "scenario_mix",
        "batch_lock_region": "us-east-1",
        "_job_queue_sig": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val
    st.session_state.theme = THEME
    if st.session_state.user_home_region not in REGIONS:
        st.session_state.user_home_region = REGIONS[0]
    if st.session_state.batch_lock_region not in REGIONS:
        st.session_state.batch_lock_region = REGIONS[0]
    if st.session_state.batch_locality_mode not in BATCH_LOCALITY_MODES:
        st.session_state.batch_locality_mode = "scenario_mix"
    if not st.session_state.jobs:
        st.session_state.jobs = build_job_batch(
            st.session_state.num_jobs,
            locality_mode=st.session_state.batch_locality_mode,
            home_region=st.session_state.user_home_region,
            lock_region=st.session_state.batch_lock_region,
        )
        st.session_state._job_queue_sig = (
            st.session_state.num_jobs,
            st.session_state.batch_locality_mode,
            st.session_state.user_home_region,
            st.session_state.batch_lock_region,
        )
    _sync_grid_session()


def _job_queue_signature() -> tuple[Any, ...]:
    return (
        st.session_state.num_jobs,
        st.session_state.batch_locality_mode,
        st.session_state.user_home_region,
        st.session_state.batch_lock_region,
    )


def _rebuild_job_queue(clear_optimization: bool = True) -> None:
    st.session_state.jobs = build_job_batch(
        st.session_state.num_jobs,
        locality_mode=st.session_state.batch_locality_mode,
        home_region=st.session_state.user_home_region,
        lock_region=st.session_state.batch_lock_region,
    )
    st.session_state.custom_jobs_loaded = False
    st.session_state._job_queue_sig = _job_queue_signature()
    if clear_optimization:
        st.session_state.assignments = None
        st.session_state.baseline_assignments = None
        st.session_state.comparison = None
        st.session_state.optimized = False


def _refresh_telemetry(fluctuate: bool = False, reload_jobs: bool = True) -> None:
    telemetry = _load_grid(fluctuate=fluctuate)
    st.session_state.grid_telemetry = telemetry
    st.session_state.grid_status = telemetry["carbon_gco2_per_kwh"]
    st.session_state.tariffs = telemetry["cost_usd_per_kwh"]
    if reload_jobs and not st.session_state.custom_jobs_loaded:
        _rebuild_job_queue(clear_optimization=True)
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
    baseline_assignments: list[dict[str, Any]] | None = None,
    tariffs: dict[str, float] | None = None,
) -> pd.DataFrame:
    tariffs = tariffs or st.session_state.tariffs
    eco_by = {a["job_id"]: a for a in assignments}
    base_by = {a["job_id"]: a for a in (baseline_assignments or [])}
    rows: list[dict[str, Any]] = []

    for job in jobs:
        eco = eco_by.get(job["job_id"])
        if not eco:
            continue
        eco_region = eco["target_region"]
        base = base_by.get(job["job_id"])
        base_region = base["target_region"] if base else "—"
        hours = job["compute_hours"]
        eco_carbon = grid[eco_region] * hours
        base_carbon = grid[base_region] * hours if base else None
        eco_cost = round(tariffs.get(eco_region, 0.10) * hours, 2)
        base_cost = round(tariffs.get(base_region, 0.10) * hours, 2) if base else None
        region_changed = base and base_region != eco_region

        rows.append(
            {
                "Job ID": job["job_id"],
                "Workload": job["task"],
                "Priority": "Urgent" if job.get("is_urgent") else "Flexible",
                "Locality": _format_locality(job.get("locality_constraint")),
                "Baseline region": base_region,
                "EcoRouter region": eco_region,
                "Route change": (
                    f"{base_region} → {eco_region}" if region_changed else "Same"
                ),
                "Hours": hours,
                "Baseline carbon": base_carbon,
                "Eco carbon": eco_carbon,
                "Carbon Δ": (base_carbon - eco_carbon) if base_carbon is not None else None,
                "Baseline $": base_cost,
                "Eco $": eco_cost,
                "Cost Δ": round(base_cost - eco_cost, 2) if base_cost is not None else None,
                "SLA": "PASS" if eco.get("sla_met", True) else "FAIL",
                "Status": _assignment_status(job, eco, greenest),
                "Reasoning": eco.get("reasoning", ""),
            }
        )
    return pd.DataFrame(rows)


def _style_assignment_overview(df: pd.DataFrame, theme: str = "light") -> Any:
    """Color-code rows: green = improved, amber = rerouted, neutral = unchanged."""
    palette = assignment_row_colors(theme)

    def _row_style(row: pd.Series) -> list[str]:
        changed = row.get("Route change", "Same") != "Same"
        carbon_delta = row.get("Carbon Δ")
        if changed and carbon_delta is not None and carbon_delta > 0:
            bg, color = palette["improved"]
        elif changed:
            bg, color = palette["changed"]
        elif carbon_delta is not None and carbon_delta > 0:
            bg, color = palette["saved"]
        else:
            bg, color = palette["neutral"]
        style = f"background-color: {bg}; color: {color}"
        return [style] * len(row)

    def _highlight_delta(val: Any) -> str:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return ""
        if isinstance(val, (int, float)) and val > 0:
            return f"color: {palette['pos']}; font-weight: 700"
        if isinstance(val, (int, float)) and val < 0:
            return f"color: {palette['neg']}; font-weight: 700"
        return f"color: {palette['zero']}"

    styled = df.style.apply(_row_style, axis=1)
    for col in ("Carbon Δ", "Cost Δ"):
        if col in df.columns:
            styled = styled.map(_highlight_delta, subset=[col])
    return styled


def _render_dispatch_cards(
    jobs: list[dict[str, Any]],
    assignments: list[dict[str, Any]],
    grid: dict[str, int],
    greenest: str,
    baseline_assignments: list[dict[str, Any]] | None = None,
    tariffs: dict[str, float] | None = None,
) -> None:
    tariffs = tariffs or st.session_state.tariffs
    eco_by = {a["job_id"]: a for a in assignments}
    base_by = {a["job_id"]: a for a in (baseline_assignments or [])}

    for job in jobs:
        eco = eco_by.get(job["job_id"])
        if not eco:
            st.warning(f"No assignment for **{job['job_id']}** ({job['task']})")
            continue

        eco_region = eco["target_region"]
        base = base_by.get(job["job_id"])
        base_region = base["target_region"] if base else None
        hours = job["compute_hours"]
        eco_carbon = grid[eco_region] * hours
        base_carbon = grid[base_region] * hours if base_region else None
        status = _assignment_status(job, eco, greenest)
        changed = base_region and base_region != eco_region

        with st.container(border=True):
            h1, h2, h3 = st.columns([2.2, 1.2, 1.2])
            with h1:
                st.markdown(f"**{job['task']}**")
                st.caption(
                    f"`{job['job_id']}` · {hours}h · "
                    f"{'Urgent' if job.get('is_urgent') else 'Flexible'}"
                )
            with h2:
                if base_carbon is not None:
                    st.metric("Baseline carbon", f"{base_carbon:,}", label_visibility="visible")
                else:
                    st.metric("Carbon", f"{eco_carbon:,}")
            with h3:
                delta = (base_carbon - eco_carbon) if base_carbon else None
                st.metric(
                    "Eco carbon",
                    f"{eco_carbon:,}",
                    f"−{delta:,}" if delta and delta > 0 else None,
                )

            if base_region:
                st.markdown(
                    f'<span class="compare-baseline">{base_region}</span>'
                    f' &nbsp;→&nbsp; <span class="compare-eco">{eco_region}</span>',
                    unsafe_allow_html=True,
                )
                if changed:
                    st.caption(f"Region changed · carbon Δ {base_carbon - eco_carbon:,} gCO₂")
            else:
                st.markdown(f"**→ {eco_region}**")

            if "Forecast deferral" in status:
                st.info(status)
            elif "Locality" in status:
                st.warning(status)
            elif "Optimal" in status:
                st.success(status)
            elif changed:
                st.success("✓ Re-routed vs baseline")
            else:
                st.write(status)

            st.caption(eco.get("reasoning", ""))


_init_session()
if st.session_state.forecast is None:
    _update_forecast()

# --- Sidebar ---
with st.sidebar:
    st.markdown(build_theme_css(THEME), unsafe_allow_html=True)
    st.markdown("### 👤 Your workspace")
    st.session_state.user_display_name = st.text_input(
        "Your name",
        value=st.session_state.user_display_name,
        placeholder="e.g. Alex Chen",
        help="Personalizes the dashboard header and summaries",
    )
    st.session_state.user_home_region = st.selectbox(
        "Your home region",
        REGIONS,
        index=REGIONS.index(st.session_state.user_home_region),
        format_func=_region_label,
        help="Used when job region policy is set to your home region",
    )
    st.session_state.batch_locality_mode = st.radio(
        "Job region policy",
        BATCH_LOCALITY_MODES,
        index=BATCH_LOCALITY_MODES.index(st.session_state.batch_locality_mode),
        format_func=lambda m: BATCH_LOCALITY_LABELS.get(m, m),
        help="Controls whether queued jobs are region-locked or carbon-flexible",
    )
    if st.session_state.batch_locality_mode == "specific_region":
        st.session_state.batch_lock_region = st.selectbox(
            "Lock all jobs to",
            REGIONS,
            index=REGIONS.index(st.session_state.batch_lock_region),
            format_func=_region_label,
        )
    st.markdown("---")
    st.markdown("### ⚙️ Controls")
    cap = min(40, MAX_BATCH_JOBS)
    if st.session_state.num_jobs > cap:
        st.session_state.num_jobs = cap
    job_col_slider, job_col_num = st.columns([4, 1])
    with job_col_num:
        num_jobs_val = st.number_input(
            "Jobs #",
            min_value=2,
            max_value=cap,
            value=int(st.session_state.num_jobs),
            step=1,
            help=f"Type a batch size (2–{cap})",
        )
    with job_col_slider:
        num_jobs_val = st.slider(
            "Jobs per batch",
            2,
            cap,
            int(num_jobs_val),
            help=f"Slide or type up to {cap} workloads per optimization run",
        )
    st.session_state.num_jobs = int(num_jobs_val)
    queue_sig = _job_queue_signature()
    if queue_sig != st.session_state.get("_job_queue_sig"):
        _rebuild_job_queue(clear_optimization=True)
        st.rerun()
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
        help=(
            "When enabled, flexible jobs may defer to greener 12h forecast windows "
            "on top of the selected routing engine (Pareto, cost-aware, etc.)."
        ),
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
    st.markdown("---")
    st.markdown("**Carbon chart display**")
    st.session_state.grid_chart_expanded = st.toggle(
        "Expand carbon chart panel",
        value=st.session_state.grid_chart_expanded,
    )
    st.session_state.carbon_bar_width = st.slider(
        "Bar width (px)", 36, 96, st.session_state.carbon_bar_width, 4,
    )
    st.session_state.carbon_chart_height = st.slider(
        "Bar height (px)", 100, 280, st.session_state.carbon_chart_height, 10,
    )

st.markdown(build_theme_css(THEME), unsafe_allow_html=True)

grid = st.session_state.grid_status
tariffs = st.session_state.tariffs
jobs = st.session_state.jobs
greenest = min(grid, key=grid.get)

_render_hero(
    len(REGIONS),
    grid,
    greenest,
    st.session_state.comparison,
    user_name=st.session_state.user_display_name,
    user_home_region=st.session_state.user_home_region,
    locality_mode=st.session_state.batch_locality_mode,
)

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
    user = st.session_state.user_display_name.strip()
    greet = f"{user}, m" if user else "M"
    policy = BATCH_LOCALITY_LABELS.get(st.session_state.batch_locality_mode, "")
    _tab_intro(
        f"{greet}onitor live grid carbon across {len(REGIONS)} AWS regions. "
        f"Queue policy: <strong>{policy}</strong>"
        + (
            f" (home: {_region_label(st.session_state.user_home_region)})."
            if st.session_state.batch_locality_mode == "home_region"
            else "."
        )
        + " Run optimization to see jobs spread across green regions where flexible. "
        "The assignment overview highlights <strong>baseline → EcoRouter</strong> with color-coded savings."
    )
    cheapest = min(tariffs, key=tariffs.get)
    _render_stat_cards([
        ("🌍", "Regions", str(len(REGIONS)), None, "blue"),
        ("🌿", "Greenest Region", _region_label(greenest), f"{grid[greenest]:,} gCO₂/kWh", "green"),
        ("💰", "Cheapest", cheapest, f"${tariffs[cheapest]:.3f}/kWh", "amber"),
        ("📋", "Pending Jobs", str(len(jobs)), None, "purple"),
        ("🧭", "Routing", ROUTING_MODE_LABELS.get(st.session_state.routing_mode, "—"), None, "slate"),
        ("📡", "Grid Source", st.session_state.grid_telemetry.get("source", "simulated")[:12], None, "blue"),
    ])

    st.markdown("<p class='section-title'>🌍 Live Grid Carbon Intensity</p>", unsafe_allow_html=True)
    if st.session_state.grid_chart_expanded:
        _render_scrollable_carbon_chart(
            grid,
            tariffs,
            bar_width=st.session_state.carbon_bar_width,
            chart_height=st.session_state.carbon_chart_height,
        )
        with st.expander("Full region data table", expanded=False):
            df_grid = pd.DataFrame([
                {
                    "Region": r,
                    "Location": REGION_GEO[r]["label"],
                    "Carbon (gCO₂/kWh)": grid[r],
                    "$/kWh": tariffs[r],
                    "Status": "🟢 Greenest" if r == greenest else "",
                }
                for r in REGIONS
            ])
            st.dataframe(
                df_grid.sort_values("Carbon (gCO₂/kWh)"),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Carbon (gCO₂/kWh)": st.column_config.NumberColumn(format="%d"),
                    "$/kWh": st.column_config.NumberColumn(format="$%.3f"),
                },
            )
    else:
        _render_compact_carbon_strip(grid, max_rows=6)
        if st.button("Expand full carbon chart", use_container_width=True):
            st.session_state.grid_chart_expanded = True
            st.rerun()

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
        eco_total = comp["eco_total_gco2"] if comp else total_carbon_cost(
            jobs, grid, st.session_state.assignments
        )
        eco_cost_total = comp["eco_total_cost_usd"] if comp else total_energy_cost_usd(
            jobs, tariffs, st.session_state.assignments
        )
        summary_cards: list[tuple[str, str, str, str | None, str]] = [
            ("✅", "Jobs Routed", str(len(st.session_state.assignments)), None, "green"),
            ("🌱", "EcoRouter Carbon", f"{eco_total:,} gCO₂", None, "green"),
            ("💵", "EcoRouter Cost", f"${eco_cost_total:.2f}", "USD energy spend", "amber"),
        ]
        if comp:
            summary_cards.extend([
                (
                    "📉",
                    "Carbon Saved",
                    f"{comp['carbon_saved_gco2']:,} gCO₂",
                    f"{comp['savings_pct']}% vs baseline",
                    "green",
                ),
                (
                    "💰",
                    "Cost Saved",
                    f"${comp['cost_saved_usd']:.2f}",
                    f"{comp['cost_savings_pct']}% vs baseline",
                    "blue",
                ),
            ])
        _render_stat_cards(summary_cards)
        routed_regions = {a["target_region"] for a in st.session_state.assignments}
        st.caption(
            f"Routed across **{len(routed_regions)}** region(s): "
            + ", ".join(_region_label(r) for r in sorted(routed_regions))
        )
        if comp:
            tradeoff = comp.get("tradeoff_type", "")
            if tradeoff == "win_win":
                st.success(comp.get("tradeoff_message", ""))
            elif tradeoff == "carbon_tradeoff":
                st.warning(comp.get("tradeoff_message", ""))
            elif comp.get("tradeoff_message"):
                st.info(comp.get("tradeoff_message", ""))
        st.caption(f"Engine: **{st.session_state.router}**")

        dispatch_df = _build_dispatch_table(
            jobs,
            st.session_state.assignments,
            grid,
            greenest,
            baseline_assignments=st.session_state.baseline_assignments,
            tariffs=tariffs,
        )
        st.markdown("#### Assignment overview — baseline vs EcoRouter")
        st.caption(
            "🟢 Green rows = region changed with carbon savings · "
            "🟠 Amber = rerouted · ⬜ Gray = same as baseline"
        )
        st.dataframe(
            _style_assignment_overview(dispatch_df, THEME),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Baseline carbon": st.column_config.NumberColumn(format="%d"),
                "Eco carbon": st.column_config.NumberColumn(format="%d"),
                "Carbon Δ": st.column_config.NumberColumn(format="%+d"),
                "Baseline $": st.column_config.NumberColumn(format="$%.2f"),
                "Eco $": st.column_config.NumberColumn(format="$%.2f"),
                "Cost Δ": st.column_config.NumberColumn(format="$%+.2f"),
            },
        )

        load_df = pd.DataFrame(compute_load_distribution(st.session_state.assignments))
        active_load = load_df[load_df["jobs"] > 0].sort_values("jobs", ascending=False)
        if not active_load.empty:
            st.markdown("#### Regional load distribution")
            st.dataframe(
                active_load.rename(columns={
                    "region": "Region", "jobs": "Jobs", "share_pct": "Share %",
                }),
                use_container_width=True,
                hide_index=True,
            )
            _render_load_distribution_chart(active_load, chart_height=300)
            st.caption(
                f"Jobs spread across **{len(active_load)}** of {len(REGIONS)} regions. "
                "White numbers show job count at the top of each bar."
            )

        with st.expander("Per-job detail cards (before → after)"):
            _render_dispatch_cards(
                jobs,
                st.session_state.assignments,
                grid,
                greenest,
                baseline_assignments=st.session_state.baseline_assignments,
                tariffs=tariffs,
            )

# ===================== TAB 2: REGION OPTIMIZER =====================
with tab_optimizer:
    _tab_intro(
        "Rank all regions by carbon, cost, and Pareto eligibility. "
        "Use the global map and what-if analyzer to preview routing decisions "
        "before running a full batch."
    )
    st.markdown("<p class='section-title'>🧭 Region Optimizer Tools</p>", unsafe_allow_html=True)

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
    _tab_intro(
        "See 12-hour carbon forecasts per region and deferral recommendations. "
        "Enable forecast-aware routing in the sidebar to shift flexible jobs "
        "to greener time windows."
    )
    st.markdown("<p class='section-title'>📈 12-Hour Carbon Intensity Forecast</p>", unsafe_allow_html=True)

    if st.button("🔮 Regenerate Forecast", use_container_width=False):
        _update_forecast()
        st.rerun()

    deferral = st.session_state.deferral or {}
    _render_stat_cards([
        ("🌿", "Greenest Now", deferral.get("current_greenest", greenest), None, "green"),
        ("🔮", "Best Forecast", deferral.get("recommended_region", "—"), "12h window", "purple"),
        ("📉", "Forecast Savings", f"{deferral.get('estimated_savings_pct', 0)}%", None, "blue"),
    ])

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

# ===================== TAB 4: A/B COMPARISON =====================
with tab_ab:
    _tab_intro(
        "Compare EcoRouter against a naive baseline (static us-east-1 or round-robin). "
        "View total carbon and cost savings, tradeoff messaging, and per-job breakdowns."
    )
    st.markdown("<p class='section-title'>⚖️ EcoRouter vs Baseline Scheduler</p>", unsafe_allow_html=True)

    if not st.session_state.comparison:
        st.info("Run **EcoRouter Optimization** on the Live Dashboard tab to generate comparison data.")
    else:
        comp = st.session_state.comparison
        _render_stat_cards([
            ("🌱", "EcoRouter Carbon", f"{comp['eco_total_gco2']:,} gCO₂", None, "green"),
            ("🏭", "Baseline Carbon", f"{comp['baseline_total_gco2']:,} gCO₂", None, "red"),
            (
                "📉",
                "Carbon Saved",
                f"{comp['carbon_saved_gco2']:,} gCO₂",
                f"{comp['savings_pct']}% vs baseline",
                "green",
            ),
            (
                "💰",
                "Cost Saved",
                f"${comp['cost_saved_usd']:.2f}",
                f"{comp['cost_savings_pct']}%",
                "blue",
            ),
        ])

        tradeoff = comp.get("tradeoff_type", "")
        if tradeoff == "win_win":
            st.success(comp.get("tradeoff_message", ""))
        elif tradeoff == "carbon_tradeoff":
            st.warning(comp.get("tradeoff_message", ""))
        elif comp.get("tradeoff_message"):
            st.info(comp.get("tradeoff_message", ""))

        c1, c2 = st.columns(2)
        with c1:
            chart_df = pd.DataFrame(
                {"Carbon (gCO₂)": [comp["eco_total_gco2"], comp["baseline_total_gco2"]]},
                index=[comp["eco_name"], comp["baseline_name"]],
            )
            st.markdown("**Carbon (gCO₂)**")
            st.bar_chart(chart_df, height=320)
        with c2:
            cost_df = pd.DataFrame(
                {"Cost (USD)": [comp["eco_total_cost_usd"], comp["baseline_total_cost_usd"]]},
                index=[comp["eco_name"], comp["baseline_name"]],
            )
            st.markdown("**Energy cost (USD)**")
            st.bar_chart(cost_df, height=320)

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
    _tab_intro(
        "Upload custom job queues (JSON/CSV), inspect regional tariffs across all zones, "
        "and export ESG / Scope 2 PDF reports for compliance teams."
    )
    st.markdown("<p class='section-title'>🏢 Enterprise — BYO Jobs, SLA & ESG Reporting</p>", unsafe_allow_html=True)

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
    _tab_intro(
        "Download JSON/CSV exports from your last run, review session history, "
        "and copy REST API commands for programmatic integration."
    )
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
- `GET /api/v1/regions` — 30-region catalog with geo + tariffs
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

    with st.expander("📋 CS 153 Submission — Rubric & Video Guide", expanded=False):
        st.markdown("""
**Track:** Automation / Agent Systems · **Repo:** [github.com/ashwin122705/ecorouter-agent](https://github.com/ashwin122705/ecorouter-agent)

| Rubric (15 pts) | See in this app |
|-----------------|-----------------|
| **Problem & Insight (3)** | Hero + job queue locality constraints |
| **Execution (5)** | Run Optimization · 6 tabs · REST API below |
| **Evaluation (3)** | **A/B Comparison** tab after optimization |
| **Communication (2)** | README · [TA Access Guide](https://github.com/ashwin122705/ecorouter-agent/blob/main/docs/TA_Access_Guide.md) · this walkthrough |
| **Process & Disclosure (2)** | README AI disclosure · limitations · public commit history |

**Demo video questions (≤10 min):**

1. **Why build this?** — AI electricity bottleneck; agent replaces manual FinOps scheduling
2. **How does it work?** — Grid sim → job queue → Gemini tool-calling → Pareto/forecast routers → dashboard + API
3. **Use cases?** — Cloud/AI labs, FinOps, DePIN — Scope 2 reduction without breaking SLAs
4. **What more?** — K8s operator, RL forecasts, per-tenant carbon budgets

**Grading path:** Live Dashboard → **Run EcoRouter Optimization** → **A/B Comparison** → verify gCO₂ savings.

**Teleprompter PDF:** `docs/EcoRouter_Teleprompter_v2.pdf` in the repo.
        """)

    st.markdown("#### Cloudflare edge (roadmap)")
    st.caption(
        "`wrangler.jsonc` is configured for static asset deployment. "
        "The FastAPI service can be containerized or proxied behind a Worker for production edge routing."
    )
