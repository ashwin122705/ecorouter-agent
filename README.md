# EcoRouter Agent 🌿

**The One-Person Frontier Lab · Stanford CS 153: Large Language Model Agents**

| | |
|---|---|
| **Author** | Ashwin |
| **Track** | Automation / Agent Systems |
| **Repository** | https://github.com/ashwin122705/ecorouter-agent |
| **Live demo** | Deploy via [Streamlit Cloud](https://share.streamlit.io) — see [TA Access Guide](docs/TA_Access_Guide.md) |
| **Demo video** | ≤10 min · covers rubric + Q1–Q4 (submit via Canvas) |

EcoRouter is an autonomous **carbon-aware AI workload orchestration agent**. It reads live (or simulated) grid telemetry across **30 AWS regions**, routes enterprise AI jobs to greener datacenters, respects SLA deadlines and compliance locality locks, and quantifies savings versus naive baselines — all through an interactive dashboard, REST API, and LLM tool-calling brain.

---

## What It Does Today

### Dashboard (6 tabs)

| Tab | Capabilities |
|-----|----------------|
| **Live Dashboard** | Scrollable 30-region carbon chart, realistic job queue, one-click optimization, dispatch summary with **gCO₂** totals, color-coded baseline → EcoRouter assignment table, regional load distribution |
| **Region Optimizer** | Full region score matrix, global carbon scatter map, what-if job analyzer |
| **Forecast & Deferral** | 12-hour per-region carbon forecast, deferral recommendations, forecast-aware routing toggle |
| **A/B Comparison** | EcoRouter vs static `us-east-1` or round-robin baseline — carbon **and** cost savings with tradeoff messaging |
| **Enterprise** | Bring-your-own jobs (JSON/CSV), ESG PDF report export |
| **Tools & API** | Region/tariff exports, curl examples, deployment notes |

### Routing engines

| Mode | Description |
|------|-------------|
| **Pareto** (default) | Lower carbon without raising $/kWh vs baseline; spreads jobs across qualifying green regions |
| **Cost-aware** | Tunable carbon vs energy cost weight (sidebar slider) |
| **Load-balanced** | Spread workloads across green regions to avoid hotspotting |
| **Forecast** | Defer flexible jobs to greener 12h windows |
| **Gemini / Auto** | LLM tool-calling via `gemini-2.5-flash` (`get_grid_carbon_intensity`, `assign_workload`) |
| **Mock** | Deterministic carbon-first heuristic — no API key required |

Forecast-aware scheduling can be **layered on top** of Pareto, cost-aware, or load-balanced modes.

### Personalization (sidebar)

- **Your name** — personalized hero header
- **Home region** — pick your AWS metro (e.g. `us-west-2 (Oregon)`)
- **Job region policy** — realistic scenario mix, any region (carbon-flexible), lock to home region, or lock to a specific region
- **Jobs per batch** — slider **or** typed number (2–40)
- Simulated vs live grid (Electricity Maps when `ELECTRICITY_MAPS_API_KEY` is set)

### Job scenarios (realistic enterprise workloads)

- Fine-tune Llama 3, RAG embedding batches, Whisper transcription
- GDPR EU inference (`eu-west-1`), US low-latency API (`us-east-1`), HIPAA US (`us-east-2`)
- APAC finance jobs (`ap-southeast-1`), flexible research training — with urgent/flexible priority and SLA deadlines

---

## Quick Start

### Streamlit dashboard (recommended)

```bash
git clone https://github.com/ashwin122705/ecorouter-agent.git
cd ecorouter-agent
pip install -r requirements.txt

# Optional — mock routing works without any key (best for demos/TAs)
echo "ECOROUTER_USE_MOCK=1" >> .env

# Optional — enable Gemini LLM routing
echo "GEMINI_API_KEY=your_key_here" >> .env

streamlit run app.py
```

Open http://localhost:8501 → **Refresh Grid & Queue** → **Run EcoRouter Optimization**.

### REST API

```bash
pip install -r requirements.txt
uvicorn api.server:app --reload --app-dir src --port 8000
```

Interactive docs: http://localhost:8000/docs

```bash
# Grid telemetry
curl http://localhost:8000/api/v1/grid

# Optimize a batch (Pareto, 6 jobs)
curl -X POST "http://localhost:8000/api/v1/optimize?num_jobs=6&mode=pareto"

# A/B vs static baseline
curl "http://localhost:8000/api/v1/compare?num_jobs=6&mode=pareto&baseline=static"
```

### CLI agent loop

```bash
ECOROUTER_USE_MOCK=1 python -m agents.ecorouter
```

---

## System Architecture

```
ecorouter-agent/
├── app.py                      # Streamlit dashboard (main entry)
├── theme_css.py                # Dark-theme UI styles
├── requirements.txt
├── .streamlit/config.toml      # Streamlit Cloud theme
├── docs/                       # TA guide
└── src/
    ├── agents/ecorouter.py     # LLM tool-calling + all routing engines
    ├── api/server.py           # FastAPI REST layer
    ├── sim_environment/
    │   ├── grid_data.py        # 30 AWS regions, carbon + tariffs
    │   ├── job_queue.py        # Realistic job scenarios + BYO import
    │   ├── grid_forecast.py    # 12h carbon forecast + deferral
    │   ├── routing_scores.py   # Pareto, cost-aware, load-spread scoring
    │   ├── carbon_metrics.py   # A/B comparison + tradeoff classification
    │   ├── baseline_scheduler.py
    │   └── region_analytics.py # Matrix, what-if, load distribution
    └── reports/esg_report.py   # ESG PDF export
```

### Four layers

1. **Grid simulator** — 30 AWS commercial regions with gCO₂/kWh, $/kWh tariffs, geographic metadata; optional [Electricity Maps](https://www.electricitymaps.com/) live data
2. **Job queue** — Enterprise AI workloads with `compute_hours`, `is_urgent`, `locality_constraint`, `deadline_utc`
3. **Agent brain** — Gemini 2.5 Flash tool-calling + Pareto / cost-aware / load-balanced / forecast routers with mock fallback
4. **Dashboard + API** — Streamlit UI, FastAPI endpoints, ESG PDF export

---

## Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `GEMINI_API_KEY` | No | Gemini LLM routing (falls back to mock if unset) |
| `ECOROUTER_USE_MOCK=1` | No | Force mock/Pareto routing — **recommended for TAs and video recording** |
| `ELECTRICITY_MAPS_API_KEY` | No | Live grid carbon data (simulated fallback) |

**Streamlit Cloud secrets** (Settings → Secrets):

```toml
ECOROUTER_USE_MOCK = "1"
# GEMINI_API_KEY = "optional"
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/api/v1/regions` | Region catalog (30 AWS metros) |
| `GET` | `/api/v1/regions/matrix` | Carbon/cost/Pareto score matrix |
| `GET` | `/api/v1/grid` | Live grid telemetry |
| `GET` | `/api/v1/forecast` | 12h carbon forecast |
| `POST` | `/api/v1/optimize` | Route a mock job batch |
| `POST` | `/api/v1/jobs` | Route custom BYO jobs (JSON body) |
| `GET` | `/api/v1/compare` | EcoRouter vs baseline comparison |
| `POST` | `/api/v1/analyze` | What-if single job analysis |

---

## For TAs & Graders

See **[docs/TA_Access_Guide.md](docs/TA_Access_Guide.md)** for:

- Streamlit Cloud one-click deploy (public interactive URL)
- Local run instructions (no API key needed)
- Suggested 3-minute grading walkthrough
- Troubleshooting

**Minimum grading path:** Live Dashboard → Run Optimization → A/B Comparison tab → verify gCO₂ savings.

---

## CS 153 Submission Rubric (15 Points)

*Stanford CS 153 · The One-Person Frontier Lab · Track: **Automation / Agent Systems***

| Rubric criterion | Where to see it |
|------------------|-----------------|
| Problem & Insight (3 pts) | README below · Video **Q1** · Live Dashboard problem framing |
| Execution & Technical Work (5 pts) | README + architecture · Video **Q2** · Full app + API + CLI |
| Evaluation & Evidence (3 pts) | A/B Comparison tab · constraint checks · iteration log below |
| Communication & Presentation (2 pts) | This README · [TA Access Guide](docs/TA_Access_Guide.md) · demo video |
| Process, Integrity & Disclosure (2 pts) | AI disclosure below · public GitHub · limitations below |

### Video requirements mapping (demo ≤ 10 min; script targets ~6 min)

| Video question | Script section | What you show |
|----------------|----------------|---------------|
| **Q1: Why did you build this?** | Problem & Insight | Bottleneck: AI electricity + regional grid carbon variance; manual FinOps does not scale |
| **Q2: How does the product work?** | Execution (Agent Systems) | Grid sim → job queue → Gemini tool-calling agent → Pareto/forecast routers → dashboard + API |
| **Q3: Use cases & societal impact?** | Use Cases | Cloud/AI labs, FinOps, DePIN — Scope 2 reduction without breaking SLAs |
| **Q4: What more would you add?** | Future Work | K8s operator, RL over forecasts, per-tenant carbon budgets |

---

### 1. Problem & Insight (3 pts)

**Problem:** AI training and inference consume catastrophic electricity; grid carbon intensity (gCO₂/kWh) varies by **region and hour** as renewables and demand shift.

**Motivation:** Data-center siting and batch scheduling are still largely manual — a bottleneck as AI workloads scale.

**Insight:** Replace manual DevOps/FinOps scheduling with an **autonomous agent** that reads grid telemetry, respects SLA/compliance locality locks, and dispatches each job to the lowest-carbon region it can legally reach.

### 2. Execution & Technical Work (5 pts)

**Built artifact:** End-to-end Python agent system — not a slide deck or prototype UI only.

| Component | Implementation |
|-----------|----------------|
| Grid simulator | 30 AWS regions, gCO₂/kWh + $/kWh tariffs; optional [Electricity Maps](https://www.electricitymaps.com/) live feed |
| Job queue | Enterprise scenarios (fine-tune, RAG, GDPR/HIPAA locks, urgent vs flexible) |
| Agent brain | Gemini 2.5 Flash **tool-calling** (`get_grid_carbon_intensity`, `assign_workload`) + Pareto / cost-aware / load-balanced / forecast routers + mock fallback |
| Interfaces | Streamlit dashboard (6 tabs), FastAPI REST API, CLI agent loop, ESG PDF export |

**Reproducibility:** `git clone` → `pip install -r requirements.txt` → `streamlit run app.py` (mock mode works with zero API keys). See [TA Access Guide](docs/TA_Access_Guide.md).

**Iteration log (meaningful progress over time):**

- Scaffold → functional agent with LLM tool-calling
- SDK migration: `google-generativeai` → `google-genai`
- Scale: 4 → **30** real AWS commercial regions
- Added Pareto routing, 12h forecast deferral, A/B baseline comparison, load-spreading, BYO jobs, REST API
- Public commit history: https://github.com/ashwin122705/ecorouter-agent/commits/main

### 3. Evaluation & Evidence (3 pts)

| Evidence type | How EcoRouter validates claims |
|---------------|-------------------------------|
| **A/B comparison** | EcoRouter vs static `us-east-1` or round-robin — grams CO₂ and USD saved (often 50–90%+ on flexible batches) |
| **Constraint satisfaction** | Locality-locked jobs never leave required region; urgent jobs respect deadlines (visible in assignment table) |
| **Failure / fallback analysis** | Rate-limit and missing-key paths fall back to mock/Pareto — demo and grading never break |
| **Limitations acknowledged** | Simulation environment (not production K8s); grid data simulated unless `ELECTRICITY_MAPS_API_KEY` set; savings are model-based on gCO₂ × compute-hours |
| **External grounding** | Carbon intensity concept aligned with grid emissions data providers (Electricity Maps); AWS region catalog |

Graders: **Live Dashboard → Run Optimization → A/B Comparison** tab for quantified savings.

### 4. Communication & Presentation (2 pts)

- **README** (this file): problem, architecture, quick start, API, rubric alignment
- **TA Access Guide:** 3-minute grading path, Streamlit Cloud deploy, troubleshooting
- **Demo video:** Structured walkthrough covering Q1–Q4
- **In-app clarity:** Six labeled tabs, sidebar controls, color-coded assignment table, gCO₂ units on stat cards
- **Engagement:** Interactive optimization — not a static recording of fake output

### 5. Process, Integrity & Disclosure (2 pts)

**AI tools used (required CS 153 disclosure):**

| Tool | How used |
|------|----------|
| **Cursor AI** | Boilerplate, debugging, UI/CSS iteration, SDK migration assistance, documentation drafts |
| **Gemini API** | Runtime LLM tool-calling in the agent (`gemini-2.5-flash`) |

All simulation logic, routing algorithms (Pareto, forecast overlay, load-spreading), and system architecture are **original to this project**. No forked base repository — built from scratch for CS 153.

**Known limitations (honest scope):**

- Software simulation — does not deploy real workloads to AWS
- Carbon figures are illustrative unless live Electricity Maps key is configured
- Peer-scale production hardening (auth, multi-tenant isolation) out of scope for 10-week sprint

**Public artifacts:** Open GitHub repo, commit history, `docs/` folder (TA guide), session export JSON/CSV in app.

---

## Deployment Notes

| Platform | What it hosts |
|----------|----------------|
| **[Streamlit Cloud](https://share.streamlit.io)** | ✅ Full interactive dashboard (`app.py`) — **use this for TAs** |
| **Local** | ✅ Dashboard + API + CLI |
| **Cloudflare Workers** (`wrangler deploy`) | Static landing page only (`public/`) — not the Streamlit app |

---

## License & Attribution

Built for Stanford CS 153 Spring 2026. All core simulation and routing logic written for this submission.
