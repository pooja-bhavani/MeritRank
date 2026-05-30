import csv
import base64
import hashlib
import io
import json
from datetime import UTC, datetime
from time import perf_counter
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from .models import Candidate, Job
from .ranker import rank_candidates
from .resume_parser import parse_resume
from .ai_analyzer import analyze, status
from .text import extract_ats_keywords
from .evaluation import parse_labels, ranking_metrics

DEFAULT_STATE = {"jobs": [], "candidates": [], "runs": []}


class Store:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock = Lock()
        if not path.exists():
            self._write(DEFAULT_STATE)
        self._dedupe_existing_candidates()

    def _read(self) -> dict[str, Any]:
        return json.loads(self.path.read_text())

    def _write(self, state: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(state, indent=2))

    def reset(self) -> None:
        with self.lock:
            self._write(DEFAULT_STATE)

    def list_jobs(self) -> list[dict[str, Any]]:
        return self._read()["jobs"]

    def list_candidates(self) -> list[dict[str, Any]]:
        return self._read()["candidates"]

    def list_runs(self) -> list[dict[str, Any]]:
        return self._read()["runs"]

    def save_job(self, value: dict[str, Any]) -> dict[str, Any]:
        job = dict(value)
        job["job_id"] = job.get("job_id") or f"JOB-{uuid4().hex[:8].upper()}"
        job.setdefault("required_skills", [])
        if not job["required_skills"]:
            job["required_skills"] = extract_ats_keywords(job.get("description", ""))
            job["requirements_inferred_from_jd"] = True
        else:
            job["requirements_inferred_from_jd"] = False
        job.setdefault("preferred_skills", [])
        job.setdefault("locations", [])
        job.setdefault("description", "")
        job.setdefault("min_years_experience", 0)
        job.setdefault("preferred_years_experience", 0)
        job.setdefault("remote_allowed", False)
        Job.from_dict(job)
        with self.lock:
            state = self._read()
            state["jobs"] = [existing for existing in state["jobs"] if existing["job_id"] != job["job_id"]]
            state["jobs"].append(job)
            self._write(state)
        return job

    def import_candidates(self, csv_text: str) -> dict[str, Any]:
        reader = csv.DictReader(io.StringIO(csv_text))
        if not reader.fieldnames or "candidate_id" not in reader.fieldnames:
            raise ValueError("CSV must contain a candidate_id column")
        candidates = [self._candidate_from_row(row) for row in reader]
        if not candidates:
            raise ValueError("CSV contains no candidate rows")
        with self.lock:
            state = self._read()
            existing = {candidate["candidate_id"]: candidate for candidate in state["candidates"]}
            for candidate in candidates:
                existing[candidate["candidate_id"]] = candidate
            state["candidates"] = list(existing.values())
            self._write(state)
        return {"imported": len(candidates), "total": len(existing)}

    def import_resume(self, filename: str, content_base64: str) -> dict[str, Any]:
        digest = hashlib.sha256(base64.b64decode(content_base64, validate=True)).hexdigest()
        state = self._read()
        existing = next(
            (candidate for candidate in state["candidates"] if candidate.get("content_sha256") == digest),
            None,
        )
        if existing:
            return {"candidate": existing, "total": len(state["candidates"]), "duplicate": True}
        candidate = parse_resume(filename, content_base64)
        candidate["content_sha256"] = digest
        with self.lock:
            state = self._read()
            state["candidates"].append(candidate)
            self._write(state)
        return {
            "candidate": candidate,
            "total": len(state["candidates"]),
            "duplicate": False,
        }

    def rank(self, job_id: str) -> dict[str, Any]:
        started = perf_counter()
        state = self._read()
        job_data = next((job for job in state["jobs"] if job["job_id"] == job_id), None)
        if not job_data:
            raise ValueError(f"Unknown job_id: {job_id}")
        if not state["candidates"]:
            raise ValueError("Import at least one candidate before ranking")
        ranked = rank_candidates(
            Job.from_dict(job_data),
            [Candidate.from_dict(candidate) for candidate in state["candidates"]],
        )
        run = {
            "run_id": f"RUN-{uuid4().hex[:8].upper()}",
            "job_id": job_id,
            "job_title": job_data["title"],
            "created_at": datetime.now(UTC).isoformat(),
            "candidate_count": len(ranked),
            "shortlist": [candidate.to_dict() for candidate in ranked],
            "analysis_mode": status(),
        }
        by_id = {candidate["candidate_id"]: candidate for candidate in state["candidates"]}
        for result in run["shortlist"][:5]:
            result["ai_analysis"] = analyze(job_data, by_id[result["candidate_id"]])
        run["llm_reviewed_candidates"] = min(5, len(run["shortlist"])) if status()["enabled"] else 0
        run["latency_ms"] = round((perf_counter() - started) * 1000, 2)
        with self.lock:
            latest = self._read()
            latest["runs"].insert(0, run)
            latest["runs"] = latest["runs"][:20]
            self._write(latest)
        return run

    def _dedupe_existing_candidates(self) -> None:
        with self.lock:
            state = self._read()
            unique: dict[str, dict[str, Any]] = {}
            for candidate in state["candidates"]:
                key = candidate.get("content_sha256") or hashlib.sha256(
                    (candidate.get("email", "") + candidate.get("summary", "")).encode()
                ).hexdigest()
                candidate["content_sha256"] = key
                unique.setdefault(key, candidate)
            if len(unique) != len(state["candidates"]):
                state["candidates"] = list(unique.values())
                self._write(state)

    def get_run(self, run_id: str) -> dict[str, Any]:
        run = next((run for run in self.list_runs() if run["run_id"] == run_id), None)
        if not run:
            raise ValueError(f"Unknown run_id: {run_id}")
        return run

    def evaluate_run(self, run_id: str, labels_csv: str) -> dict[str, Any]:
        run = self.get_run(run_id)
        metrics = ranking_metrics(run["shortlist"], parse_labels(labels_csv))
        with self.lock:
            state = self._read()
            stored = next(item for item in state["runs"] if item["run_id"] == run_id)
            stored["evaluation"] = metrics
            self._write(state)
        return metrics

    @staticmethod
    def _split(value: str) -> list[str]:
        return [item.strip() for item in value.split("|") if item.strip()]

    @classmethod
    def _candidate_from_row(cls, row: dict[str, str]) -> dict[str, Any]:
        candidate = {
            "candidate_id": row["candidate_id"].strip(),
            "name": row.get("name", "").strip(),
            "email": row.get("email", "").strip(),
            "phone": row.get("phone", "").strip(),
            "headline": row.get("headline", "").strip(),
            "summary": row.get("summary", "").strip(),
            "skills": cls._split(row.get("skills", "")),
            "roles": cls._split(row.get("roles", "")),
            "years_experience": float(row.get("years_experience", 0) or 0),
            "location": row.get("location", "").strip(),
            "open_to_remote": row.get("open_to_remote", "").strip().lower() in {"1", "true", "yes", "y"},
            "activity": {
                "profile_completeness": float(row.get("profile_completeness", 0.5) or 0.5),
                "response_rate": float(row.get("response_rate", 0.5) or 0.5),
                "active_days_ago": int(row.get("active_days_ago", 90) or 90),
            },
        }
        if not candidate["candidate_id"]:
            raise ValueError("Each candidate row must have a candidate_id")
        Candidate.from_dict(candidate)
        return candidate
