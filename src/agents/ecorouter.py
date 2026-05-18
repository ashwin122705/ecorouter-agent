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

from sim_environment.grid_data import REGIONS, get_live_grid_status
from sim_environment.job_queue import generate_mock_jobs

load_dotenv()

SYSTEM_PROMPT = """You are EcoRouter, an autonomous infrastructure scheduler for AI compute workloads.

Your goals:
1. Minimize carbon emissions (gCO₂eq/kWh) by routing each job to an appropriate data center region.
2. Respect hard constraints: if a job has a locality_constraint, the target_region MUST be exactly that region.
3. If is_urgent is true, pick the best allowed region now (no temporal deferral in this simulation).
4. If is_urgent is false and there is no locality constraint, you may still pick the lowest-carbon allowed region now; temporal shifting is not modeled as a separate tool—optimize for current grid telemetry.

Always call get_grid_carbon_intensity at least once before assigning workloads, so decisions are grounded in telemetry.
For every job in the queue, call assign_workload exactly once with a valid target_region from the tool schema.
Order of operations: fetch grid → assign each job → then stop (no further tool calls)."""


def _normalize_gemini_model(model_name: str) -> str:
    """Gemini API accepts either `gemini-…` or `models/gemini-…`; normalize to the latter."""
    if model_name.startswith("models/"):
        return model_name
    return f"models/{model_name}"


def _routing_tool() -> types.Tool:
    """Single Tool carrying FunctionDeclarations (google.genai / Gemini API shape)."""
    get_grid = types.FunctionDeclaration(
        name="get_grid_carbon_intensity",
        description=(
            "Returns the current simulated carbon intensity (gCO₂eq/kWh) for each "
            "available cloud region. Call this before routing decisions."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={},
        ),
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
    """Tools + system instruction; AFC disabled so we execute tools and send FunctionResponse parts."""
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
    """Prefer `response.text`; fall back to concatenating text parts if needed."""
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


def _ensure_gemini_api_key() -> None:
    if not (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")):
        raise RuntimeError(
            "No API key found. Set GEMINI_API_KEY or GOOGLE_API_KEY in the environment or in a "
            ".env file at the project root (genai.Client() reads the same variables as the SDK)."
        )


def run_ecorouter_agent(
    num_jobs: int = 3,
    model: str | None = None,
    max_tool_rounds: int = 12,
) -> dict[str, Any]:
    """
    Run the EcoRouter agent with Gemini function calling via google.genai.

    Returns: grid_status, jobs, assignments, model, incomplete_job_ids, assistant_final_text.
    Authentication: GEMINI_API_KEY or GOOGLE_API_KEY (after load_dotenv()).
    """
    _ensure_gemini_api_key()

    model_name = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    resolved_model = _normalize_gemini_model(model_name)

    jobs = generate_mock_jobs(num_jobs=num_jobs)
    grid_snapshot = get_live_grid_status()
    session = _RoutingSession(jobs, grid_snapshot)

    client = genai.Client()
    chat = client.chats.create(model=resolved_model, config=_routing_generate_config())

    user_payload = {
        "jobs": jobs,
        "note": (
            "Regions in this simulation are exactly: "
            + ", ".join(REGIONS)
            + ". Use assign_workload for each job after reading the grid."
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

    return {
        "grid_status": session.grid_snapshot,
        "jobs": jobs,
        "assignments": list(session.assignments),
        "model": resolved_model,
        "incomplete_job_ids": incomplete,
        "assistant_final_text": assistant_final_text,
    }


def run_agent_scaffolding() -> None:
    """CLI entrypoint: runs the real LLM tool-calling agent and prints results."""
    print("🌱 Initializing EcoRouter Agent Environment...\n")

    print("🌍 1. Simulated grid telemetry will be exposed to the model via get_grid_carbon_intensity.\n")

    print("📋 2. Evaluating Job Queue...")
    try:
        result = run_ecorouter_agent(num_jobs=3)
    except RuntimeError as e:
        print(f"❌ {e}")
        sys.exit(1)
    except genai_errors.ClientError as e:
        print(f"❌ Gemini API error: {e}")
        sys.exit(1)

    jobs = result["jobs"]
    grid_status = result["grid_status"]

    print(f"Current Carbon Intensity (gCO2/kWh):\n{json.dumps(grid_status, indent=2)}\n")
    for job in jobs:
        constraint = (
            f"Must run in {job['locality_constraint']}" if job["locality_constraint"] else "No geographic limits"
        )
        urgency = "URGENT" if job["is_urgent"] else "FLEXIBLE (Eligible for temporal shift)"
        print(f"  - [{job['job_id']}] {job['task']} | {urgency} | {constraint}")

    print("\n🤖 3. LLM tool-calling agent execution...")
    print(f"  -> Model: {result['model']}")

    if result["incomplete_job_ids"]:
        print(
            "\n⚠️ Agent did not assign every job within the tool-call budget. Missing: "
            + ", ".join(result["incomplete_job_ids"])
        )

    print("\n✅ Assignments from tool calls (assign_workload):")
    for a in result["assignments"]:
        print(f"  -> Dispatched {a['job_id']} to {a['target_region']} ({a['reasoning']})")

    if result.get("assistant_final_text"):
        print("\n📝 Model closing message:")
        print(result["assistant_final_text"])


if __name__ == "__main__":
    run_agent_scaffolding()
