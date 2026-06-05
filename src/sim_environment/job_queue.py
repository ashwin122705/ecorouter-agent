"""Job queue: mock generation, BYO import (JSON/CSV), SLA deadlines."""

from __future__ import annotations

import json
import uuid
import random
from datetime import datetime, timedelta, timezone
from io import StringIO
from typing import Any

import pandas as pd

from sim_environment.grid_data import REGIONS

# Realistic enterprise AI workload scenarios (compliance-driven locality when set)
JOB_SCENARIOS: list[dict[str, Any]] = [
    {
        "task": "Fine-tune Llama 3 (product catalog)",
        "hours_range": (16, 28),
        "urgent": False,
        "locality": None,
        "deadline_hours": (36, 72),
    },
    {
        "task": "RAG embedding batch (overnight index rebuild)",
        "hours_range": (10, 18),
        "urgent": False,
        "locality": None,
        "deadline_hours": (48, 96),
    },
    {
        "task": "EU customer chat inference (GDPR)",
        "hours_range": (4, 8),
        "urgent": True,
        "locality": "eu-west-1",
        "deadline_hours": (6, 12),
    },
    {
        "task": "US East low-latency API inference",
        "hours_range": (2, 6),
        "urgent": True,
        "locality": "us-east-1",
        "deadline_hours": (4, 8),
    },
    {
        "task": "Whisper transcription backlog",
        "hours_range": (12, 24),
        "urgent": False,
        "locality": None,
        "deadline_hours": (48, 120),
    },
    {
        "task": "Vision model training (research sprint)",
        "hours_range": (24, 40),
        "urgent": False,
        "locality": None,
        "deadline_hours": (72, 168),
    },
    {
        "task": "APAC finance report summarization",
        "hours_range": (6, 12),
        "urgent": False,
        "locality": "ap-southeast-1",
        "deadline_hours": (24, 48),
    },
    {
        "task": "Code review agent batch (flexible)",
        "hours_range": (4, 10),
        "urgent": False,
        "locality": None,
        "deadline_hours": (24, 72),
    },
    {
        "task": "Healthcare doc OCR pipeline (HIPAA US)",
        "hours_range": (8, 16),
        "urgent": False,
        "locality": "us-east-2",
        "deadline_hours": (24, 48),
    },
    {
        "task": "Multimodal eval harness (carbon-flexible)",
        "hours_range": (14, 22),
        "urgent": False,
        "locality": None,
        "deadline_hours": (48, 96),
    },
]


def _default_deadline(hours_from_now: int | None = None) -> str:
    hrs = hours_from_now if hours_from_now is not None else random.randint(4, 72)
    return (datetime.now(timezone.utc) + timedelta(hours=hrs)).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_job(raw: dict[str, Any], index: int = 0) -> dict[str, Any]:
    """Validate and normalize a single job record from any import source."""
    job_id = str(raw.get("job_id") or f"job_{str(uuid.uuid4())[:8]}")
    task = str(raw.get("task") or raw.get("workload") or JOB_SCENARIOS[index % len(JOB_SCENARIOS)]["task"])

    compute_hours = raw.get("compute_hours") or raw.get("hours") or raw.get("gpu_hours") or 8
    compute_hours = max(1, int(compute_hours))

    is_urgent = raw.get("is_urgent")
    if is_urgent is None:
        is_urgent = str(raw.get("priority", "")).lower() in {"urgent", "high", "critical"}
    else:
        is_urgent = bool(is_urgent)

    locality = raw.get("locality_constraint") or raw.get("locality") or raw.get("region_lock")
    if locality in ("", "—", "-", "none", "null"):
        locality = None
    if locality and locality not in REGIONS:
        raise ValueError(f"Job {job_id}: invalid locality {locality!r}. Must be one of {REGIONS}")

    deadline = raw.get("deadline_utc") or raw.get("deadline") or _default_deadline(
        6 if is_urgent else random.randint(12, 96)
    )

    return {
        "job_id": job_id,
        "task": task,
        "compute_hours": compute_hours,
        "is_urgent": is_urgent,
        "locality_constraint": locality,
        "deadline_utc": str(deadline),
    }


def generate_mock_jobs(num_jobs: int = 5) -> list[dict[str, Any]]:
    """Generate realistic AI workload batches with compliance-driven locality locks."""
    scenarios = JOB_SCENARIOS.copy()
    random.shuffle(scenarios)
    jobs: list[dict[str, Any]] = []

    for i in range(num_jobs):
        scenario = scenarios[i % len(scenarios)]
        hours_lo, hours_hi = scenario["hours_range"]
        dl_lo, dl_hi = scenario["deadline_hours"]
        is_urgent = scenario["urgent"]
        jobs.append(
            normalize_job(
                {
                    "task": scenario["task"],
                    "compute_hours": random.randint(hours_lo, hours_hi),
                    "is_urgent": is_urgent,
                    "locality_constraint": scenario["locality"],
                    "deadline_utc": _default_deadline(
                        random.randint(dl_lo, dl_hi) if not is_urgent else random.randint(4, 10)
                    ),
                },
                index=i,
            )
        )
    return jobs


def parse_jobs_from_json(text: str) -> list[dict[str, Any]]:
    """Parse BYO jobs from JSON array or `{ \"jobs\": [...] }` payload."""
    data = json.loads(text)
    if isinstance(data, dict):
        data = data.get("jobs", data.get("queue", []))
    if not isinstance(data, list):
        raise ValueError("JSON must be an array of jobs or an object with a 'jobs' key.")
    return [normalize_job(item, index=i) for i, item in enumerate(data)]


def parse_jobs_from_csv(text: str) -> list[dict[str, Any]]:
    """Parse BYO jobs from CSV with flexible column names."""
    df = pd.read_csv(StringIO(text))
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    jobs: list[dict[str, Any]] = []
    for i, row in df.iterrows():
        jobs.append(normalize_job(row.to_dict(), index=i))
    return jobs


def sample_jobs_json() -> str:
    """Example JSON payload for API docs and UI."""
    return json.dumps(
        {
            "jobs": [
                {
                    "job_id": "train_001",
                    "task": "Fine-tune Llama 3 (product catalog)",
                    "compute_hours": 18,
                    "is_urgent": False,
                    "locality_constraint": None,
                    "deadline_utc": _default_deadline(48),
                },
                {
                    "job_id": "infer_002",
                    "task": "EU customer chat inference (GDPR)",
                    "compute_hours": 6,
                    "is_urgent": True,
                    "locality_constraint": "eu-west-1",
                    "deadline_utc": _default_deadline(8),
                },
            ]
        },
        indent=2,
    )
