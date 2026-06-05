from __future__ import annotations

import json
import os
import sys
from typing import Any

# Add the root directory to the system path to allow local imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from sim_environment.grid_data import (
    DEFAULT_BASELINE_REGION,
    REGIONS,
    REGION_TARIFFS_USD,
    get_grid_telemetry,
    get_live_grid_status,
)
from sim_environment.grid_forecast import forecast_grid, recommend_deferral_window
from sim_environment.job_queue import generate_mock_jobs
from sim_environment.routing_scores import (
    allowed_regions,
    baseline_reference_region,
    composite_score,
    select_cost_aware_region,
    select_pareto_region,
)
from sim_environment.sla import apply_sla_to_assignments, can_defer

load_dotenv()

SYSTEM_PROMPT = """You are EcoRouter, an autonomous infrastructure scheduler for AI compute workloads.

Your goals:
1. Minimize carbon emissions (gCO₂eq/kWh) by routing each job to an appropriate data center region.
2. Respect hard constraints: if a job has a locality_constraint, the target_region MUST be exactly that region.
3. If is_urgent is true, pick the best allowed region now (no temporal deferral in this simulation).
4. Respect SLA deadlines (deadline_utc): never defer a job if waiting would cause it to miss its deadline.
5. If is_urgent is false and there is no locality constraint, you may still pick the lowest-carbon allowed region now; temporal shifting is not modeled as a separate tool—optimize for current grid telemetry.

Always call get_grid_carbon_intensity at least once before assigning workloads, so decisions are grounded in telemetry.
For every job in the queue, call assign_workload exactly once with a valid target_region from the tool schema.
Order of operations: fetch grid → assign each job → then stop (no further tool calls)."""


# ---------------------------------------------------------------------------
# Tool schema & routing session (shared by LLM and mock paths)
# ---------------------------------------------------------------------------


def _normalize_gemini_model(model_name: str) -> str:
    if model_name.startswith("models/"):
        return model_name
    return f"models/{model_name}"


def _routing_tool() -> types.Tool:
    get_grid = types.FunctionDeclaration(
        name="get_grid_carbon_intensity",
        description=(
            "Returns the current simulated carbon intensity (gCO₂eq/kWh) for each "
            "available cloud region. Call this before routing decisions."
        ),
        parameters=types.Schema(type=types.Type.OBJECT, properties={}),
    )
    assign = types.FunctionDeclaration(
        name="assign_workload",
        description=(
            "Record the routing decision for a single job. Use the job's locality_constraint "
            "as target_region when present; otherwise prefer the lowest-carbon region among all regions."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "job_id": types.Schema(
                    type=types.Type.STRING,
                    description="The job_id from the job queue.",
                ),
                "target_region": types.Schema(
                    type=types.Type.STRING,
                    enum=list(REGIONS),
                    description="Data center region where the workload will run.",
                ),
                "reasoning": types.Schema(
                    type=types.Type.STRING,
                    description="Short justification (carbon, urgency, locality).",
                ),
            },
            required=["job_id", "target_region", "reasoning"],
        ),
    )
    return types.Tool(function_declarations=[get_grid, assign])


def _routing_generate_config() -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=[_routing_tool()],
        tool_config=types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(
                mode=types.FunctionCallingConfigMode.AUTO,
            ),
        ),
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )


def _text_from_response(response: types.GenerateContentResponse) -> str:
    text = response.text
    if text is not None:
        return text
    parts = response.parts or []
    return "".join(p.text or "" for p in parts)


class _RoutingSession:
    """Holds a fixed grid snapshot and accumulates assign_workload tool calls."""

    __slots__ = ("jobs", "grid_snapshot", "assignments")

    def __init__(self, jobs: list[dict[str, Any]], grid_snapshot: dict[str, int]):
        self.jobs = jobs
        self.grid_snapshot = dict(grid_snapshot)
        self.assignments: list[dict[str, Any]] = []

    def get_grid_carbon_intensity(self) -> dict[str, Any]:
        return {"regions_g_co2_per_kwh": self.grid_snapshot}

    def assign_workload(self, job_id: str, target_region: str, reasoning: str) -> dict[str, Any]:
        valid = set(REGIONS)
        if target_region not in valid:
            return {
                "ok": False,
                "error": f"Invalid target_region {target_region!r}. Must be one of: {sorted(valid)}",
            }
        known_ids = {j["job_id"] for j in self.jobs}
        if job_id not in known_ids:
            return {"ok": False, "error": f"Unknown job_id {job_id!r}. Known: {sorted(known_ids)}"}

        locality = next(j.get("locality_constraint") for j in self.jobs if j["job_id"] == job_id)
        if locality and target_region != locality:
            return {
                "ok": False,
                "error": (
                    f"Job {job_id} has locality_constraint={locality!r}; "
                    f"target_region must be {locality!r}."
                ),
            }

        self.assignments = [a for a in self.assignments if a["job_id"] != job_id]
        self.assignments.append(
            {
                "job_id": job_id,
                "target_region": target_region,
                "reasoning": reasoning.strip(),
            }
        )
        return {"ok": True, "recorded": {"job_id": job_id, "target_region": target_region}}


def _dispatch_tool(session: _RoutingSession, name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name == "get_grid_carbon_intensity":
        return session.get_grid_carbon_intensity()

    if name == "assign_workload":
        return session.assign_workload(
            str(args.get("job_id", "")),
            str(args.get("target_region", "")),
            str(args.get("reasoning", "")),
        )

    return {"ok": False, "error": f"Unknown tool {name!r}"}


def _has_gemini_api_key() -> bool:
    return bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))


def _use_mock_llm() -> bool:
    """Mock scheduler when ECOROUTER_USE_MOCK=1 or no API key is configured."""
    flag = os.getenv("ECOROUTER_USE_MOCK", "").strip().lower()
    if flag in {"1", "true", "yes"}:
        return True
    return not _has_gemini_api_key()


# ---------------------------------------------------------------------------
# Mock LLM — carbon-aware heuristic (no API calls)
# ---------------------------------------------------------------------------


def run_mock_router(
    jobs: list[dict[str, Any]],
    grid_status: dict[str, int],
) -> list[dict[str, Any]]:
    """
    Simulates the LLM routing brain with a deterministic heuristic:
    honour locality constraints; otherwise route to the greenest region.
    """
    greenest_region = min(grid_status, key=grid_status.get)
    greenest_intensity = grid_status[greenest_region]
    assignments: list[dict[str, Any]] = []

    for job in jobs:
        locality = job.get("locality_constraint")
        if locality:
            target = locality
            reasoning = (
                f"Locality constraint requires {locality}; "
                f"grid intensity there is {grid_status[locality]} gCO₂/kWh."
            )
        elif job.get("is_urgent"):
            target = greenest_region
            reasoning = (
                f"Urgent job with no locality limit; routed to greenest region "
                f"{greenest_region} ({greenest_intensity} gCO₂/kWh)."
            )
        else:
            target = greenest_region
            reasoning = (
                f"Flexible job; optimized for lowest carbon at {greenest_region} "
                f"({greenest_intensity} gCO₂/kWh)."
            )

        assignments.append(
            {
                "job_id": job["job_id"],
                "target_region": target,
                "reasoning": reasoning,
            }
        )

    return assignments


def run_forecast_aware_router(
    jobs: list[dict[str, Any]],
    grid_status: dict[str, int],
    min_deferral_savings_pct: float = 12.0,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Carbon-aware scheduler that uses 12h grid forecasts for flexible jobs.

    Urgent jobs and locality-constrained jobs behave like the mock router.
    Flexible jobs with no locality may defer to a greener forecast window.
    """
    forecast = forecast_grid(grid_status, hours_ahead=12)
    deferral = recommend_deferral_window(grid_status, forecast, min_deferral_savings_pct)
    greenest_now = min(grid_status, key=grid_status.get)
    assignments: list[dict[str, Any]] = []

    for job in jobs:
        locality = job.get("locality_constraint")
        if locality:
            target = locality
            reasoning = (
                f"Locality constraint requires {locality} "
                f"({grid_status[locality]} gCO₂/kWh)."
            )
            deferred = False
            defer_hours = 0
        elif job.get("is_urgent"):
            target = greenest_now
            reasoning = (
                f"Urgent — dispatch now to greenest region {greenest_now} "
                f"({grid_status[greenest_now]} gCO₂/kWh)."
            )
            deferred = False
            defer_hours = 0
        elif deferral["should_defer"]:
            defer_hours = deferral["recommended_hours_ahead"]
            if can_defer(job, defer_hours):
                target = deferral["recommended_region"]
                reasoning = (
                    f"Flexible job deferred {defer_hours}h per forecast: {target} expected at "
                    f"{deferral['recommended_intensity']} gCO₂/kWh "
                    f"(~{deferral['estimated_savings_pct']}% vs dispatching now)."
                )
                deferred = True
            else:
                target = greenest_now
                reasoning = (
                    f"Flexible job — deferral skipped (SLA deadline {job.get('deadline_utc')}); "
                    f"routing now to {greenest_now} ({grid_status[greenest_now]} gCO₂/kWh)."
                )
                deferred = False
                defer_hours = 0
        else:
            target = greenest_now
            reasoning = (
                f"Flexible job — no strong greener window; routing now to {greenest_now} "
                f"({grid_status[greenest_now]} gCO₂/kWh)."
            )
            deferred = False
            defer_hours = 0

        assignments.append(
            {
                "job_id": job["job_id"],
                "target_region": target,
                "reasoning": reasoning,
                "deferred": deferred,
                "defer_hours": defer_hours,
            }
        )

    return assignments, {"router": "forecast-aware", "forecast": forecast, "deferral": deferral}


def apply_forecast_overlay(
    jobs: list[dict[str, Any]],
    assignments: list[dict[str, Any]],
    grid_status: dict[str, int],
    min_deferral_savings_pct: float = 12.0,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Apply forecast deferral to flexible, non-locality jobs on top of any router."""
    forecast = forecast_grid(grid_status, hours_ahead=12)
    deferral = recommend_deferral_window(
        grid_status, forecast, min_deferral_savings_pct
    )
    if not deferral.get("should_defer"):
        return assignments, {"forecast": forecast, "deferral": deferral}

    defer_hours = deferral["recommended_hours_ahead"]
    by_id = {a["job_id"]: dict(a) for a in assignments}

    for job in jobs:
        if job.get("locality_constraint") or job.get("is_urgent"):
            continue
        if not can_defer(job, defer_hours):
            continue
        entry = by_id[job["job_id"]]
        entry["target_region"] = deferral["recommended_region"]
        entry["deferred"] = True
        entry["defer_hours"] = defer_hours
        prior = entry.get("reasoning", "")
        entry["reasoning"] = (
            f"{prior} | Forecast deferral {defer_hours}h → "
            f"{deferral['recommended_region']} "
            f"(~{deferral['estimated_savings_pct']}% greener vs dispatch now)."
        )

    return list(by_id.values()), {"forecast": forecast, "deferral": deferral}


def _with_forecast_overlay(
    jobs: list[dict[str, Any]],
    assignments: list[dict[str, Any]],
    grid_status: dict[str, int],
    meta: dict[str, Any],
    use_forecast: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not use_forecast:
        return assignments, meta
    updated, forecast_meta = apply_forecast_overlay(jobs, assignments, grid_status)
    meta = {**meta, **forecast_meta}
    meta["router"] = f"{meta.get('router', 'router')} + forecast"
    return updated, meta


def run_cost_aware_router(
    jobs: list[dict[str, Any]],
    grid_status: dict[str, int],
    tariffs: dict[str, float] | None = None,
    carbon_weight: float = 0.6,
) -> list[dict[str, Any]]:
    """Balance carbon and $/kWh using a configurable weighted score."""
    tariffs = tariffs or REGION_TARIFFS_USD
    assignments: list[dict[str, Any]] = []

    for job in jobs:
        candidates = allowed_regions(job)
        if len(candidates) == 1:
            target = candidates[0]
            reasoning = (
                f"Locality locked to {target} "
                f"({grid_status[target]} gCO₂/kWh, ${tariffs.get(target, 0):.3f}/kWh)."
            )
        else:
            target, reasoning = select_cost_aware_region(
                candidates, grid_status, tariffs, carbon_weight=carbon_weight
            )

        assignments.append(
            {
                "job_id": job["job_id"],
                "target_region": target,
                "reasoning": reasoning,
                "routing_objective": "cost_aware",
            }
        )

    return assignments


def run_pareto_router(
    jobs: list[dict[str, Any]],
    grid_status: dict[str, int],
    tariffs: dict[str, float] | None = None,
    baseline_region: str = DEFAULT_BASELINE_REGION,
) -> list[dict[str, Any]]:
    """
    Route to regions that improve carbon vs baseline without increasing cost.
    Falls back to cost-aware when no Pareto-optimal option exists.
    """
    tariffs = tariffs or REGION_TARIFFS_USD
    assignments: list[dict[str, Any]] = []

    for job in jobs:
        candidates = allowed_regions(job)
        ref = baseline_reference_region(job, baseline_region)

        if len(candidates) == 1:
            target = candidates[0]
            reasoning = f"Locality locked to {target}."
            tier = "locality_locked"
        else:
            target, reasoning, tier = select_pareto_region(
                candidates, grid_status, tariffs, reference_region=ref
            )

        assignments.append(
            {
                "job_id": job["job_id"],
                "target_region": target,
                "reasoning": reasoning,
                "routing_objective": "pareto",
                "pareto_tier": tier,
            }
        )

    return assignments


def run_load_balanced_router(
    jobs: list[dict[str, Any]],
    grid_status: dict[str, int],
    tariffs: dict[str, float] | None = None,
    carbon_weight: float = 0.55,
    load_penalty: float = 0.12,
) -> list[dict[str, Any]]:
    """
    Spread jobs across green regions to avoid hotspotting a single data center.
    Processes largest jobs first and penalizes regions already assigned workloads.
    """
    tariffs = tariffs or REGION_TARIFFS_USD
    region_load: dict[str, int] = {r: 0 for r in REGIONS}
    assignments: list[dict[str, Any]] = []
    sorted_jobs = sorted(jobs, key=lambda j: j.get("compute_hours", 0), reverse=True)
    max_load = max(len(jobs), 1)

    for job in sorted_jobs:
        candidates = allowed_regions(job)
        if len(candidates) == 1:
            target = candidates[0]
            reasoning = f"Locality locked to {target}."
        else:
            target = min(
                candidates,
                key=lambda r: composite_score(
                    r,
                    candidates,
                    grid_status,
                    tariffs,
                    carbon_weight=carbon_weight,
                    load_fraction=region_load[r] / max_load,
                    load_penalty=load_penalty,
                ),
            )
            reasoning = (
                f"Load-balanced: {target} (assigned={region_load[target]}, "
                f"{grid_status[target]} gCO₂/kWh, ${tariffs.get(target, 0):.3f}/kWh)."
            )

        region_load[target] += 1
        assignments.append(
            {
                "job_id": job["job_id"],
                "target_region": target,
                "reasoning": reasoning,
                "routing_objective": "load_balanced",
            }
        )

    return assignments


# ---------------------------------------------------------------------------
# Gemini LLM — tool-calling agent
# ---------------------------------------------------------------------------


def run_gemini_router(
    jobs: list[dict[str, Any]],
    grid_status: dict[str, int],
    model: str | None = None,
    max_tool_rounds: int = 12,
) -> dict[str, Any]:
    """
    Route jobs via Gemini function calling. Expects pre-fetched jobs and grid telemetry.
    """
    if not _has_gemini_api_key():
        raise RuntimeError(
            "No API key found. Set GEMINI_API_KEY or GOOGLE_API_KEY in .env, "
            "or set ECOROUTER_USE_MOCK=1 to use the mock scheduler."
        )

    model_name = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    resolved_model = _normalize_gemini_model(model_name)
    session = _RoutingSession(jobs, grid_status)

    client = genai.Client()
    chat = client.chats.create(model=resolved_model, config=_routing_generate_config())

    user_payload = {
        "jobs": jobs,
        "grid_status": grid_status,
        "note": (
            "Regions: "
            + ", ".join(REGIONS)
            + ". Call get_grid_carbon_intensity, then assign_workload for every job."
        ),
    }

    response = chat.send_message(json.dumps(user_payload, indent=2))
    assistant_final_text = ""

    for _ in range(max_tool_rounds):
        calls = response.function_calls
        if not calls:
            assistant_final_text = _text_from_response(response)
            break

        response_parts: list[types.Part] = []
        for fc in calls:
            name = fc.name or ""
            args = dict(fc.args) if fc.args else {}
            result = _dispatch_tool(session, name, args)
            response_parts.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        id=fc.id,
                        name=name,
                        response=result,
                    )
                )
            )

        response = chat.send_message(response_parts)
    else:
        assistant_final_text = _text_from_response(response)

    assigned_ids = {a["job_id"] for a in session.assignments}
    required_ids = {j["job_id"] for j in jobs}
    incomplete = sorted(required_ids - assigned_ids)

    # Fill any gaps the LLM missed with the mock heuristic so the run always completes.
    if incomplete:
        missing_jobs = [j for j in jobs if j["job_id"] in incomplete]
        fallback = run_mock_router(missing_jobs, grid_status)
        session.assignments.extend(fallback)

    return {
        "assignments": list(session.assignments),
        "model": resolved_model,
        "incomplete_job_ids": incomplete,
        "assistant_final_text": assistant_final_text,
        "router": "gemini",
    }


# ---------------------------------------------------------------------------
# Final execution loop
# ---------------------------------------------------------------------------


def print_execution_summary(
    jobs: list[dict[str, Any]],
    grid_status: dict[str, int],
    assignments: list[dict[str, Any]],
    router: str,
    model: str | None = None,
) -> None:
    """Print a human-readable summary of the routing run."""
    assignment_by_job = {a["job_id"]: a for a in assignments}
    greenest = min(grid_status, key=grid_status.get)

    print("\n" + "=" * 72)
    print("ECOROUTER — FINAL DISPATCH SUMMARY")
    print("=" * 72)

    print(f"\nRouter: {router}" + (f" ({model})" if model else ""))
    print(f"Greenest region this cycle: {greenest} ({grid_status[greenest]} gCO₂/kWh)")

    print("\n--- Grid Telemetry (gCO₂/kWh) ---")
    for region in REGIONS:
        intensity = grid_status.get(region, "N/A")
        marker = "  ← greenest" if region == greenest else ""
        print(f"  {region:16} {intensity}{marker}")

    print("\n--- Job Assignments ---")
    total_carbon_hours = 0
    for job in jobs:
        a = assignment_by_job.get(job["job_id"])
        if not a:
            print(f"  [{job['job_id']}] {job['task']:28}  UNASSIGNED")
            continue

        region = a["target_region"]
        intensity = grid_status.get(region, 0)
        carbon_cost = intensity * job["compute_hours"]
        total_carbon_hours += carbon_cost

        locality = job.get("locality_constraint") or "none"
        urgency = "urgent" if job.get("is_urgent") else "flexible"
        print(
            f"  [{job['job_id']}] {job['task']:28}  →  {region:14}  "
            f"({urgency}, locality={locality}, {job['compute_hours']}h)"
        )
        print(f"       Carbon cost: ~{carbon_cost:,} gCO₂  |  {a['reasoning']}")

    print(f"\nEstimated total carbon cost: ~{total_carbon_hours:,} gCO₂ (intensity × compute_hours)")
    print("=" * 72 + "\n")


def _route_jobs(
    jobs: list[dict[str, Any]],
    grid_status: dict[str, int],
    *,
    mode: str = "auto",
    use_forecast: bool = False,
    tariffs: dict[str, float] | None = None,
    carbon_weight: float = 0.6,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Route a batch via Gemini, mock heuristic, forecast, cost-aware, or Pareto.

    mode: "auto" | "mock" | "gemini" | "forecast" | "cost_aware" | "pareto" | "load_balanced"
    """
    tariffs = tariffs or REGION_TARIFFS_USD

    if mode == "load_balanced":
        assignments = apply_sla_to_assignments(
            jobs,
            run_load_balanced_router(
                jobs, grid_status, tariffs, carbon_weight=carbon_weight
            ),
        )
        return _with_forecast_overlay(
            jobs, assignments, grid_status,
            {"router": "load-balanced", "model": None},
            use_forecast,
        )

    if mode == "cost_aware":
        assignments = apply_sla_to_assignments(
            jobs, run_cost_aware_router(jobs, grid_status, tariffs, carbon_weight)
        )
        return _with_forecast_overlay(
            jobs, assignments, grid_status,
            {"router": "cost-aware", "carbon_weight": carbon_weight, "model": None},
            use_forecast,
        )

    if mode == "pareto":
        assignments = apply_sla_to_assignments(
            jobs, run_pareto_router(jobs, grid_status, tariffs)
        )
        return _with_forecast_overlay(
            jobs, assignments, grid_status,
            {"router": "pareto", "model": None},
            use_forecast,
        )

    if mode == "forecast":
        assignments, meta = run_forecast_aware_router(jobs, grid_status)
        assignments = apply_sla_to_assignments(jobs, assignments)
        return assignments, meta

    if mode == "mock" or (mode == "auto" and _use_mock_llm()):
        assignments = apply_sla_to_assignments(jobs, run_mock_router(jobs, grid_status))
        return _with_forecast_overlay(
            jobs, assignments, grid_status,
            {"router": "carbon-first (mock)", "model": None},
            use_forecast,
        )

    if mode == "gemini" or mode == "auto":
        try:
            meta = run_gemini_router(jobs, grid_status)
            meta["assignments"] = apply_sla_to_assignments(jobs, meta["assignments"])
            return _with_forecast_overlay(
                jobs, meta["assignments"], grid_status, meta, use_forecast
            )
        except genai_errors.ClientError:
            assignments = apply_sla_to_assignments(jobs, run_mock_router(jobs, grid_status))
            return _with_forecast_overlay(
                jobs, assignments, grid_status,
                {"router": "mock (api fallback)", "model": None},
                use_forecast,
            )

    assignments = apply_sla_to_assignments(jobs, run_mock_router(jobs, grid_status))
    return _with_forecast_overlay(
        jobs, assignments, grid_status,
        {"router": "mock", "model": None},
        use_forecast,
    )


def run_execution_loop(num_jobs: int = 5) -> dict[str, Any]:
    """
    Main EcoRouter execution loop:
      1. Fetch pending jobs from the queue
      2. Fetch live grid carbon intensity
      3. Route each job via Gemini LLM (or mock heuristic fallback)
      4. Return results for UI / downstream use
    """
    print("🌱 EcoRouter — starting execution loop\n")

    # --- Step 1: Pending jobs ---
    print(f"📋 Step 1/4 — Fetching {num_jobs} pending job(s) from queue...")
    jobs = generate_mock_jobs(num_jobs=num_jobs)
    for job in jobs:
        locality = job.get("locality_constraint") or "none"
        urgency = "URGENT" if job.get("is_urgent") else "flexible"
        print(f"   • {job['job_id']}  {job['task']}  ({urgency}, locality={locality}, {job['compute_hours']}h)")

    # --- Step 2: Grid telemetry ---
    print("\n🌍 Step 2/4 — Fetching live grid carbon intensity...")
    grid_status = get_live_grid_status()
    greenest = min(grid_status, key=grid_status.get)
    for region in REGIONS:
        print(f"   • {region:16} {grid_status[region]:4} gCO₂/kWh")
    print(f"   → Greenest right now: {greenest} ({grid_status[greenest]} gCO₂/kWh)")

    # --- Step 3: Route via LLM or mock ---
    use_mock = _use_mock_llm()
    if use_mock:
        reason = "ECOROUTER_USE_MOCK=1" if os.getenv("ECOROUTER_USE_MOCK") else "no API key found"
        print(f"\n🤖 Step 3/4 — Routing with mock scheduler ({reason})...")
        assignments = run_mock_router(jobs, grid_status)
        router_meta = {"router": "mock", "model": None, "incomplete_job_ids": [], "assistant_final_text": ""}
    else:
        print("\n🤖 Step 3/4 — Routing with Gemini tool-calling agent...")
        try:
            router_meta = run_gemini_router(jobs, grid_status)
            assignments = router_meta["assignments"]
            print(f"   → Model: {router_meta['model']}")
            if router_meta["incomplete_job_ids"]:
                print(
                    f"   ⚠ LLM missed {len(router_meta['incomplete_job_ids'])} job(s); "
                    "filled with mock fallback."
                )
        except genai_errors.ClientError as e:
            print(f"   ⚠ Gemini API error ({e}); falling back to mock scheduler.")
            assignments = run_mock_router(jobs, grid_status)
            router_meta = {"router": "mock (api fallback)", "model": None, "incomplete_job_ids": [], "assistant_final_text": ""}

    # --- Step 4: Final summary ---
    print("\n✅ Step 4/4 — Dispatch complete. Printing summary...")
    print_execution_summary(
        jobs=jobs,
        grid_status=grid_status,
        assignments=assignments,
        router=router_meta.get("router", "unknown"),
        model=router_meta.get("model"),
    )

    return {
        "jobs": jobs,
        "grid_status": grid_status,
        "assignments": assignments,
        "router": router_meta.get("router"),
        "model": router_meta.get("model"),
        "incomplete_job_ids": router_meta.get("incomplete_job_ids", []),
        "assistant_final_text": router_meta.get("assistant_final_text", ""),
    }


if __name__ == "__main__":
    num = int(os.getenv("ECOROUTER_NUM_JOBS", "5"))
    run_execution_loop(num_jobs=num)
