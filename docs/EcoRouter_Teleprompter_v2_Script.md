# EcoRouter — Video Teleprompter Script (v2)
**Ashwin · Stanford CS 153 · Automation / Agent Systems · One-Person Frontier Lab**  
**Target length: 5:30 – 6:00 · Under 10 min limit · Covers all 15 rubric points + video Q1–Q4**

*Updated for official CS 153 submission rubric: Problem & Insight · Execution · Evaluation · Communication · Process & Disclosure.*

---

## BEFORE YOU START (not recorded)

1. Run: `streamlit run app.py` (or use your deployed Streamlit Cloud URL)
2. In `.env`: set `ECOROUTER_USE_MOCK=1` if you want zero API risk during recording
3. Sidebar setup:
   - Enter your name (optional personalization)
   - Jobs per batch: **6** (type or slide)
   - Job region policy: **Realistic scenario mix**
   - Routing engine: **Pareto**
   - Toggle **Forecast-aware scheduling** ON
4. Click **Refresh Grid & Queue**
5. Have ready: **A/B Comparison** tab (after optimization), **Tools & API** tab

---

## [0:00 – 0:25] OPENING

Hi, I'm Ashwin.

This is **EcoRouter Agent** — an autonomous system that routes AI compute workloads to the greenest cloud regions in real time, while respecting urgency deadlines, SLA windows, and data residency rules.

I built it for Stanford CS 153, **Automation and Agent Systems** track, as my **One-Person Frontier Lab** project.

---

## [0:25 – 1:05] VIDEO Q1 + RUBRIC 1 — PROBLEM & INSIGHT (3 pts)

**Why did I build this?**

As AI scales, the bottleneck is not only GPUs — it's **electricity**. Training and batch inference consume massive power, and grid carbon intensity — grams of CO₂ per kilowatt-hour — **changes by region and by hour** as solar, wind, and demand shift.

Today, a DevOps or FinOps team manually watches grid data and decides where jobs run. That does not scale.

**EcoRouter's insight:** replace that manual scheduler with an **intelligent agent** — a digital twin infrastructure manager that reads telemetry, evaluates constraints, and dispatches each job to the best region it can legally reach.

---

## [1:05 – 2:10] VIDEO Q2 + RUBRIC 2 — EXECUTION & TECHNICAL WORK (5 pts)

**How exactly does the product work?** For an agent-systems project, here is the full stack.

**Layer one — Grid simulator:** thirty real AWS regions with simulated carbon and dollar-per-kilowatt-hour tariffs. Optional Electricity Maps integration for live data.

**Layer two — Job queue:** realistic enterprise workloads — fine-tuning, RAG batches, GDPR-locked EU inference, HIPAA US jobs. Each job has compute hours, urgent versus flexible priority, and optional locality locks.

**Layer three — Agent brain** in `ecorouter.py`: Gemini two-point-five Flash with **LLM tool-calling** — `get_grid_carbon_intensity` and `assign_workload`. The agent reasons over telemetry, then executes assignments. Plus production routers: **Pareto**, cost-aware, load-balanced, and **forecast-aware deferral** over a twelve-hour window. A mock heuristic fallback guarantees the demo never breaks.

**Layer four — Interfaces:** this Streamlit dashboard, a **FastAPI REST layer**, CLI agent loop, and ESG PDF export.

Same logic runs from CLI, API, or UI — fully reproducible from the public GitHub repo with `requirements.txt`.

---

## [2:10 – 2:35] DEMO — SETUP

Let me show it live.

At the top: personalized workspace stats — thirty regions, today's greenest region, and carbon upside versus a static us-east-1 baseline.

Scroll the **live carbon chart** — low-carbon Nordic and Canadian hydro versus high-carbon APAC coal regions.

The **job queue** shows realistic scenarios: most jobs are carbon-flexible; a few are locked for GDPR or US latency compliance.

Sidebar: I'll run **Pareto routing** with **forecast-aware scheduling** enabled.

---

## [2:35 – 3:20] DEMO — OPTIMIZATION

*[Click: Run EcoRouter Optimization — wait for spinner]*

Done. Look at the **Dispatch Summary**.

**EcoRouter Carbon** and **Carbon Saved** are in **grams of CO₂**, with concrete totals.

Jobs routed across **multiple green regions** — not one datacenter hotspot — because Pareto load-spreading balances carbon and cost.

The **assignment table** shows baseline versus EcoRouter per job: green rows mean region changed with carbon savings; amber means rerouted; gray means unchanged.

---

## [3:20 – 3:50] DEMO — A/B & FORECAST

Switch to **A/B Comparison**.

EcoRouter is measured against a naive baseline — static us-east-1 or round-robin. You see total carbon, cost in dollars, and **percent savings**. This is hard evidence the agent makes a difference — often fifty to ninety percent carbon reduction on flexible batches.

Open **Forecast and Deferral**: twelve-hour per-region forecast and deferral recommendations for flexible jobs.

---

## [3:50 – 4:15] VIDEO Q3 — USE CASES & SOCIETAL IMPACT

**Who uses this and why does it matter?**

**Cloud providers and AI labs** plug it into batch schedulers to cut Scope 2 emissions without breaking SLAs.

**FinOps teams** trade carbon against cost with Pareto and cost-aware modes.

**DePIN and distributed compute** networks apply the same logic wherever workloads are geographically mobile.

The impact: greener AI infrastructure without asking humans to manually chase grid data every hour.

---

## [4:15 – 4:45] RUBRIC 3 — EVALUATION & EVIDENCE (3 pts)

How do we know it works?

First, **constraint satisfaction**: locality-locked jobs never leave their required region. Urgent jobs respect SLA deadlines — check the assignment table.

Second, **quantified savings**: the A/B tab reports grams of CO₂ and dollars saved versus baseline, with per-job breakdowns.

Third, **iteration and limitations**: I migrated from deprecated `google-generativeai` to `google-genai`, added rate-limit fallback to mock routing, and expanded from four regions to thirty — all documented in the README with public commit history. This is a **simulation** — not production Kubernetes yet — and savings are model-based on compute-hours times grid intensity.

The **Tools and API** tab shows curl examples — graders can hit `/api/v1/optimize` without the UI.

---

## [4:45 – 5:10] RUBRIC 4 — COMMUNICATION & PRESENTATION (2 pts)

For anyone outside the project: the README documents architecture, quick start, and this rubric mapping. The **TA Access Guide** gives a three-minute grading path. Clone, install, and run with mock mode — no API key required. This demo walks tab by tab so the system is understandable and reproducible, not just a static screenshot.

---

## [5:10 – 5:30] VIDEO Q4 — FUTURE WORK

**What more would I add?**

A production **Kubernetes operator** that watches real cluster queues, reinforcement learning over multi-day carbon forecasts, and per-tenant carbon budgets for enterprise ESG reporting.

---

## [5:30 – 5:50] RUBRIC 5 — PROCESS, INTEGRITY & DISCLOSURE (2 pts)

Process and integrity: I used **Cursor and Gemini** as accelerators for boilerplate, debugging, and SDK migration — fully disclosed in the README per CS 153 AI policy. All simulation logic and routing design are original to this project; no forked base repo. Major limitations — simulated grid, mock fallback, no live AWS dispatch — are documented openly.

---

## [5:50 – 6:00] CLOSE

The full project is open source:

**github.com/ashwin122705/ecorouter-agent**

TAs and classmates can run it locally with `streamlit run app.py`, or use the deployed demo link in the README.

Thank you for watching.

---

## ACTION CUES (glance only — do not read aloud)

| Time | On-screen action |
|------|------------------|
| 0:20 | Point at hero stats (regions, greenest, gCO₂ saved) |
| 1:05 | Gesture at four architecture layers (chart → queue → agent → tabs) |
| 2:15 | Scroll carbon bar chart horizontally |
| 2:25 | Point at job queue Locality column (GDPR / Any region) |
| 2:30 | Show sidebar: Pareto + Forecast toggle ON |
| 2:35 | **CLICK: Run EcoRouter Optimization** |
| 2:50 | Point at EcoRouter Carbon and Carbon Saved stat cards (gCO₂ units) |
| 3:00 | Point at multi-region routing caption |
| 3:10 | Scroll assignment overview color-coded table |
| 3:22 | **CLICK: A/B Comparison tab** — point at savings % |
| 3:40 | **CLICK: Forecast tab** — show 12h line chart |
| 4:20 | **CLICK: Tools & API tab** — flash curl + CS 153 rubric expander |
| 5:52 | Show GitHub URL + README rubric section on screen |

---

## RUBRIC & VIDEO CHECKLIST

- [x] Problem & Insight (3 pts) — Q1 @ 0:25
- [x] Execution & Technical Work (5 pts) — Q2 @ 1:05 + live demo
- [x] Evaluation & Evidence (3 pts) — A/B tab + constraints + limitations @ 4:15
- [x] Communication & Presentation (2 pts) — README/TA guide/reproducibility @ 4:45
- [x] Process & Disclosure (2 pts) — AI tools + limitations @ 5:30
- [x] Video Q3 use cases @ 3:50
- [x] Video Q4 future work @ 5:10

**Fallback:** `ECOROUTER_USE_MOCK=1` in `.env` — identical demo, no Gemini quota needed.

**PDF for recording:** [EcoRouter_Teleprompter_v2.pdf](EcoRouter_Teleprompter_v2.pdf) · Regenerate: `./scripts/generate_teleprompter_pdf.sh`
