# EcoRouter — Video Teleprompter Script (v2)
**Ashwin · Stanford CS 153 · Automation / Agent Systems**  
**Target length: 5:30 – 6:00 · Read at a natural, conversational pace**

*Updated for the full dashboard: 30 AWS regions, Pareto routing, A/B comparison, 12h forecasting, REST API, and personalized workspace.*

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

I built it for Stanford CS 153, Automation and Agent Systems track, as my One-Person Frontier Lab project.

---

## [0:25 – 1:10] RUBRIC 1 — PROBLEM & INSIGHT (3 pts)

Why does this matter?

As AI scales, the bottleneck is not only GPUs — it's **electricity**. Training and batch inference consume massive power, and grid carbon intensity — grams of CO₂ per kilowatt-hour — **changes by region and by hour** as solar, wind, and demand shift.

Today, a DevOps or FinOps team manually watches grid data and decides where jobs run. That does not scale.

**EcoRouter's insight:** replace that manual scheduler with an **intelligent agent** — a digital twin infrastructure manager that reads telemetry, evaluates constraints, and dispatches each job to the best region it can legally reach.

---

## [1:10 – 2:20] RUBRIC 2 — EXECUTION & TECHNICAL WORK (5 pts)

Here is the architecture — four layers, all working end to end.

**Layer one — Grid simulator:** thirty real AWS regions with live simulated carbon and dollar-per-kilowatt-hour tariffs. Optional Electricity Maps integration for live data.

**Layer two — Job queue:** realistic enterprise workloads — fine-tuning, RAG batches, GDPR-locked EU inference, HIPAA US jobs. Each job has compute hours, urgent versus flexible priority, and optional locality locks.

**Layer three — Agent brain** in `ecorouter.py`: Gemini two-point-five Flash with **LLM tool-calling** — `get_grid_carbon_intensity` and `assign_workload`. Plus production routers: **Pareto**, cost-aware, load-balanced, and **forecast-aware deferral** over a twelve-hour window. A mock heuristic fallback guarantees the demo never breaks.

**Layer four — This dashboard:** Streamlit UI with scrollable carbon charts, region optimizer, A/B baseline comparison, enterprise BYO jobs, ESG PDF export, and a **FastAPI REST layer** for headless integration.

Same logic runs from CLI, API, or UI — fully reproducible from the GitHub repo.

---

## [2:20 – 2:45] DEMO — SETUP

Let me show it live.

At the top: personalized workspace stats — thirty regions, today's greenest region, and carbon upside versus a static us-east-1 baseline.

Scroll the **live carbon chart** — low-carbon Nordic and Canadian hydro versus high-carbon APAC coal regions.

The **job queue** shows realistic scenarios: most jobs are carbon-flexible; a few are locked for GDPR or US latency compliance.

Sidebar: I'll run **Pareto routing** with **forecast-aware scheduling** enabled.

---

## [2:45 – 3:30] DEMO — OPTIMIZATION

*[Click: Run EcoRouter Optimization — wait for spinner]*

Done. Look at the **Dispatch Summary**.

**EcoRouter Carbon** and **Carbon Saved** are in **grams of CO₂**, with concrete totals.

Jobs routed across **multiple green regions** — not one datacenter hotspot — because Pareto load-spreading balances carbon and cost.

The **assignment table** shows baseline versus EcoRouter per job: green rows mean region changed with carbon savings; amber means rerouted; gray means unchanged.

---

## [3:30 – 4:00] DEMO — A/B & FORECAST TABS

Switch to **A/B Comparison**.

EcoRouter is measured against a naive baseline — static us-east-1 or round-robin. You see total carbon, cost in dollars, and **percent savings**. This is hard evidence the agent makes a difference — often fifty to ninety percent carbon reduction on flexible batches.

Open **Forecast and Deferral**: twelve-hour per-region forecast and deferral recommendations for flexible jobs.

---

## [4:00 – 4:35] RUBRIC 3 — EVALUATION & EVIDENCE (3 pts)

How do we know it works?

First, **constraint satisfaction**: locality-locked jobs never leave their required region. Urgent jobs respect SLA deadlines.

Second, **quantified savings**: the A/B tab reports grams of CO₂ and dollars saved versus baseline, with per-job breakdowns.

Third, **iteration evidence**: I migrated from deprecated `google-generativeai` to `google-genai`, added rate-limit fallback to mock routing, and expanded from four regions to thirty with Pareto and forecast overlays — documented in the README execution log.

The **Tools and API** tab shows curl examples — graders can hit `/api/v1/optimize` without the UI.

---

## [4:35 – 5:05] RUBRIC 4 — USE CASES & FUTURE (2 pts)

Who uses this?

**Cloud providers and AI labs** plug it into batch schedulers to cut Scope 2 emissions without breaking SLAs.

**FinOps teams** trade carbon against cost with Pareto and cost-aware modes.

**DePIN and distributed compute** networks apply the same logic wherever workloads are geographically mobile.

If I kept building: production Kubernetes operator, reinforcement learning over long-horizon forecasts, and customer-specific carbon budgets per tenant.

---

## [5:05 – 5:35] RUBRIC 5 — PROCESS & DISCLOSURE (2 pts)

Process and integrity: I used **Cursor and Gemini** as accelerators for boilerplate, debugging, and SDK migration — disclosed in the README. All simulation logic and routing design are original to this project.

---

## [5:35 – 6:00] CLOSE

The full project is open source:

**github.com/ashwin122705/ecorouter-agent**

TAs and classmates can run it locally with `streamlit run app.py`, or use the deployed demo link in the README.

Thank you for watching.

---

## ACTION CUES (glance only — do not read aloud)

| Time | On-screen action |
|------|------------------|
| 0:20 | Point at hero stats (regions, greenest, gCO₂ saved) |
| 1:10 | Gesture at four architecture layers (chart → queue → button → tabs) |
| 2:25 | Scroll carbon bar chart horizontally |
| 2:35 | Point at job queue Locality column (GDPR / Any region) |
| 2:42 | Show sidebar: Pareto + Forecast toggle ON |
| 2:45 | **CLICK: Run EcoRouter Optimization** |
| 3:00 | Point at EcoRouter Carbon and Carbon Saved stat cards (gCO₂ units) |
| 3:10 | Point at multi-region routing caption |
| 3:20 | Scroll assignment overview color-coded table |
| 3:32 | **CLICK: A/B Comparison tab** — point at savings % |
| 3:45 | **CLICK: Forecast tab** — show 12h line chart |
| 4:10 | **CLICK: Tools & API tab** — flash curl example |
| 5:40 | Show GitHub URL + README on screen |

---

**Fallback:** `ECOROUTER_USE_MOCK=1` in `.env` — identical demo, no Gemini quota needed.

**PDF for recording:** [EcoRouter_Teleprompter_v2.pdf](EcoRouter_Teleprompter_v2.pdf) (or open `EcoRouter_Teleprompter_v2.html` → Cmd+P → Save as PDF).

**Regenerate PDF:** `./scripts/generate_teleprompter_pdf.sh`
