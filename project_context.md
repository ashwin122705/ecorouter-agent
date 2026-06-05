# EcoRouter: Project Context & Architecture

## 1. Project Background

* **Class:** Stanford CS 153 — Large Language Model Agents (Spring 2026)
* **Assignment:** The One-Person Frontier Lab (35% of grade)
* **Track:** Automation / Agent Systems
* **Author:** Ashwin
* **Repository:** https://github.com/ashwin122705/ecorouter-agent

**Core concept:** As AI scales, data-center energy and carbon are primary bottlenecks. EcoRouter is an autonomous LLM agent acting as a global infrastructure manager — routing simulated AI workloads to greener cloud regions based on grid carbon intensity, SLA deadlines, and compliance locality locks.

## 2. CS 153 Rubric Alignment

| Criterion | EcoRouter evidence |
|-----------|-------------------|
| Problem & Insight (3 pts) | AI electricity + regional grid variance; agent replaces manual scheduling |
| Execution & Technical Work (5 pts) | Full stack: grid sim, job queue, Gemini tool-calling, routers, Streamlit, FastAPI, CLI |
| Evaluation & Evidence (3 pts) | A/B comparison vs baseline, constraint checks, iteration log, documented limitations |
| Communication & Presentation (2 pts) | README, TA guide, reproducible quick start |
| Process & Disclosure (2 pts) | Cursor/Gemini AI disclosure, original code, public GitHub history |

**Video Q1–Q4** covered in the demo video and README rubric section.

## 3. Technical Architecture

Pure-software simulation (no live AWS workload dispatch in scope).

1. **Grid Simulator (`src/sim_environment/grid_data.py`)** — 30 AWS commercial regions, gCO₂/kWh, $/kWh tariffs; optional Electricity Maps live feed
2. **Job Queue (`src/sim_environment/job_queue.py`)** — Enterprise scenarios (fine-tune, RAG, GDPR/HIPAA locks, urgent vs flexible)
3. **Agent Brain (`src/agents/ecorouter.py`)** — Gemini 2.5 Flash tool-calling + Pareto / cost-aware / load-balanced / forecast routers + mock fallback
4. **Analytics (`src/sim_environment/`)** — carbon_metrics, grid_forecast, routing_scores, baseline_scheduler, region_analytics
5. **Interfaces** — `app.py` (Streamlit, 6 tabs), `src/api/server.py` (FastAPI), CLI, ESG PDF export

## 4. Directory Structure

```text
ecorouter-agent/
├── app.py                      # Main Streamlit dashboard
├── theme_css.py
├── requirements.txt
├── README.md                   # Rubric alignment + quick start
├── docs/
│   └── TA_Access_Guide.md
└── src/
    ├── agents/ecorouter.py
    ├── api/server.py
    ├── sim_environment/
    └── reports/esg_report.py
```

## 5. Known Limitations

* Simulation environment — not a production Kubernetes operator
* Grid carbon simulated unless `ELECTRICITY_MAPS_API_KEY` is set
* Savings metrics are model-based (gCO₂ × compute-hours), not measured from real hardware
