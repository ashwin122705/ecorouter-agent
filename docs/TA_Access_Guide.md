# EcoRouter — Guide for TAs & Graders

How to view and interact with this project without the author present.

---

## Option 1: Public Streamlit Cloud URL (recommended)

Streamlit Community Cloud hosts the **full interactive dashboard** (not just static HTML).

### One-time setup (author)

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
2. **New app** → Repository: `ashwin122705/ecorouter-agent` → Main file: `app.py`.
3. **Advanced settings → Secrets** (optional):
   ```toml
   GEMINI_API_KEY = "your-key"
   ```
   If omitted, the app uses mock routing automatically when no key is set.
4. Deploy. Copy the URL (e.g. `https://ecorouter-agent.streamlit.app`).
5. Add that URL to:
   - README.md (top banner)
   - Canvas submission / project write-up

### For TAs

1. Open the Streamlit URL in any browser — no install required.
2. Click **Refresh Grid & Queue** in the sidebar.
3. Click **Run EcoRouter Optimization** on the Live Dashboard tab.
4. Explore tabs: Region Optimizer, Forecast, A/B Comparison, Tools & API.

**No API key needed:** The app falls back to mock/Pareto routers if `GEMINI_API_KEY` is missing.

---

## Option 2: Run locally (5 minutes)

```bash
git clone https://github.com/ashwin122705/ecorouter-agent.git
cd ecorouter-agent
pip install -r requirements.txt

# Optional — forces mock routing (safest for grading)
echo "ECOROUTER_USE_MOCK=1" >> .env

streamlit run app.py
```

Open http://localhost:8501

---

## Option 3: REST API only (headless)

```bash
pip install -r requirements.txt
uvicorn api.server:app --reload --app-dir src --port 8000
```

Then:

```bash
curl http://localhost:8000/api/v1/regions
curl -X POST http://localhost:8000/api/v1/optimize \
  -H "Content-Type: application/json" \
  -d '{"num_jobs": 4, "routing_mode": "pareto"}'
```

Interactive docs: http://localhost:8000/docs

---

## Option 4: CLI agent loop

```bash
cd ecorouter-agent
pip install -r requirements.txt
ECOROUTER_USE_MOCK=1 python -m agents.ecorouter
```

---

## What is NOT the interactive app

| URL type | Interactive? |
|----------|----------------|
| **Streamlit Cloud** / `localhost:8501` | ✅ Full UI |
| **Cloudflare Workers** (`wrangler deploy`) | ❌ Static landing page only (`public/`) |
| **GitHub repo** | ✅ Clone + run locally |

---

## Suggested grading walkthrough (3 min)

1. **Live Dashboard** — Run optimization; verify gCO₂ savings in Dispatch Summary.
2. **A/B Comparison** — Confirm EcoRouter beats static us-east-1 baseline.
3. **Assignment table** — Green rows = rerouted with savings; locked jobs stay in locality column.
4. **Tools & API** — Confirm `/api/v1/optimize` responds.
5. **README** — Execution log, failure analysis, AI disclosure.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Gemini rate limit | Set `ECOROUTER_USE_MOCK=1` in `.env` or Streamlit secrets |
| Empty comparison tab | Run optimization on Live Dashboard first |
| Port in use | `streamlit run app.py --server.port 8502` |

---

**Repo:** https://github.com/ashwin122705/ecorouter-agent
