# EcoRouter: Project Context & Architecture

## 1. Project Background
* **Class:** Stanford CS 153 (Frontier Systems) - Spring 2026.
* **Prompt:** "The One-Person Frontier Lab." Scale yourself using modern AI tools to do the work of a full organization.
* **Timeline:** 3-week sprint.
* **Core Concept:** As AI scales, data center energy constraints and carbon footprints are the primary bottlenecks. EcoRouter simulates an autonomous LLM agent acting as a global infrastructure manager. It routes simulated AI compute workloads to data centers based on real-time grid carbon intensity, replacing the need for a manual DevOps/FinOps team.

## 2. Technical Architecture ("The Digital Twin")
Because of the 3-week timeline, this is a pure-software simulation (no physical server deployments).

1. **The Grid Simulator (`src/sim_environment/grid_data.py`)**
   * Mocks a global cloud network (e.g., US-East, Europe-West, etc.).
   * Generates live, fluctuating carbon intensity metrics (gCO₂/kWh) using baseline historical averages + random variance.
2. **The Job Queue (`src/sim_environment/job_queue.py`)**
   * Generates mock AI computing jobs (e.g., "train_llama3", "batch_image_processing").
   * Injects constraints: `compute_hours`, `is_urgent` (can it be temporally shifted?), and `locality_constraint` (e.g., must stay in EU for GDPR).
3. **The LLM Brain (`src/agents/ecorouter.py`)**
   * A multi-agent system powered by LLM Tool Calling / Function Calling.
   * **Goal:** Evaluate the job queue, call tools to check regional grid status, reason about the optimal location/time, and execute the assignment.
4. **Live Telemetry & UI (`src/ui/app.py`)**
   * Built with Streamlit.
   * Visualizes the agent's real-time routing decisions, global grid status, and the job queue.
   * *Future Feature:* A/B testing to compare the LLM's carbon footprint against a baseline "dumb" scheduler.

## 3. Directory Structure
```text
ecorouter-agent/
├── .gitignore
├── requirements.txt
├── README.md
├── index.html
├── project_context.md         <-- This file
└── src/
    ├── agents/
    │   └── ecorouter.py       (Currently scaffolded, needs LLM integration)
    ├── sim_environment/
    │   ├── grid_data.py       (Complete)
    │   └── job_queue.py       (Complete)
    └── ui/
        └── app.py             (Basic Streamlit UI complete)