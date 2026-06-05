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

JOB_TYPES = [
    "train_llama3_8b",
    "batch_image_processing",
    "whisper_transcription",
    "data_pipeline",
    "llm_fine_tune",
    "embedding_batch",
]


def _default_deadline(hours_from_now: int | None = None) -> str:
    hrs = hours_from_now if hours_from_now is not None else random.randint(4, 72)
    return (datetime.now(timezone.utc) + timedelta(hours=hrs)).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_job(raw: dict[str, Any], index: int = 0) -> dict[str, Any]:
    """Validate and normalize a single job record from any import source."""
    job_id = str(raw.get("job_id") or f"job_{str(uuid.uuid4())[:8]}")
    task = str(raw.get("task") or raw.get("workload") or JOB_TYPES[index % len(JOB_TYPES)])

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


def _pick_locality_constraint(num_jobs: int, locked_so_far: int) -> str | None:
    """Rare locality locks so most jobs can be carbon-optimized across regions."""
    max_locked = max(1, num_jobs // 8)
    if locked_so_far >= max_locked:
        return None
    if random.random() < 0.15:
        return random.choice(REGIONS)
    return None


def generate_mock_jobs(num_jobs: int = 5) -> list[dict[str, Any]]:
    """Generate mock AI compute workloads with SLA deadlines."""
    jobs: list[dict[str, Any]] = []
    locked = 0
    for i in range(num_jobs):
        is_urgent = random.random() < 0.35
        locality = _pick_locality_constraint(num_jobs, locked)
        if locality:
            locked += 1
        jobs.append(
            normalize_job(
                {
                    "task": random.choice(JOB_TYPES),
                    "compute_hours": random.randint(8, 32),
                    "is_urgent": is_urgent,
                    "locality_constraint": locality,
                    "deadline_utc": _default_deadline(6 if is_urgent else random.randint(24, 96)),
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
                    "task": "train_llama3_8b",
                    "compute_hours": 18,
                    "is_urgent": False,
                    "locality_constraint": None,
                    "deadline_utc": _default_deadline(48),
                },
                {
                    "job_id": "infer_002",
                    "task": "batch_image_processing",
                    "compute_hours": 6,
                    "is_urgent": True,
                    "locality_constraint": "eu-central-1",
                    "deadline_utc": _default_deadline(8),
                },
            ]
        },
        indent=2,
    )
