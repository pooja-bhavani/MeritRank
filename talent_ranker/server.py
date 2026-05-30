import json
import csv
import io
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .models import Candidate, Job
from .ranker import rank_candidates
from .store import Store
from .ai_analyzer import status

ROOT = Path(__file__).resolve().parent.parent
DEMO_PATH = ROOT / "data" / "demo_request.json"
INDEX_PATH = ROOT / "static" / "index.html"
STATE_PATH = ROOT / "data" / "app_state.json"
TEMPLATE_PATH = ROOT / "data" / "candidate_import_template.csv"
LABELS_TEMPLATE_PATH = ROOT / "data" / "evaluation_labels_template.csv"
store = Store(STATE_PATH)


def rank_payload(payload: dict[str, Any]) -> dict[str, Any]:
    job = Job.from_dict(payload["job"])
    candidates = [Candidate.from_dict(candidate) for candidate in payload["candidates"]]
    ranked = rank_candidates(job, candidates)
    return {
        "job_id": job.job_id,
        "candidate_count": len(ranked),
        "shortlist": [candidate.to_dict() for candidate in ranked],
        "scoring_notice": (
            "Names and contact fields are displayed for reviewer convenience but excluded "
            "from scoring. Demo data is synthetic."
        ),
    }


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, value: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(value, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/":
            body = INDEX_PATH.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/health":
            self._send_json({"status": "ok", "service": "meritrank"})
        elif self.path == "/analysis/status":
            self._send_json(status())
        elif self.path == "/template.csv":
            body = TEMPLATE_PATH.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/csv")
            self.send_header("Content-Disposition", 'attachment; filename="candidate_import_template.csv"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/evaluation-template.csv":
            body = LABELS_TEMPLATE_PATH.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/csv")
            self.send_header("Content-Disposition", 'attachment; filename="evaluation_labels_template.csv"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/jobs":
            self._send_json({"jobs": store.list_jobs()})
        elif self.path == "/candidates":
            self._send_json({"candidates": store.list_candidates()})
        elif self.path == "/runs":
            self._send_json({"runs": store.list_runs()})
        elif self.path.startswith("/runs/") and self.path.endswith("/export.csv"):
            run_id = self.path.split("/")[2]
            self._send_csv(store.get_run(run_id))
        elif self.path == "/demo":
            self._send_json(rank_payload(json.loads(DEMO_PATH.read_text())))
        else:
            self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(content_length))
            if self.path == "/rank":
                self._send_json(rank_payload(payload))
            elif self.path == "/jobs":
                self._send_json({"job": store.save_job(payload)}, HTTPStatus.CREATED)
            elif self.path == "/candidates/import":
                self._send_json(store.import_candidates(payload["csv_text"]), HTTPStatus.CREATED)
            elif self.path == "/resumes/import":
                self._send_json(
                    store.import_resume(payload["filename"], payload["content_base64"]),
                    HTTPStatus.CREATED,
                )
            elif self.path == "/runs":
                self._send_json({"run": store.rank(payload["job_id"])}, HTTPStatus.CREATED)
            elif self.path.startswith("/runs/") and self.path.endswith("/evaluate"):
                run_id = self.path.split("/")[2]
                self._send_json({"evaluation": store.evaluate_run(run_id, payload["labels_csv"])})
            else:
                self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)

    def _send_csv(self, run: dict[str, Any]) -> None:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["rank", "candidate_id", "display_name", "score", "matched_required", "missing_required"])
        for candidate in run["shortlist"]:
            writer.writerow([
                candidate["rank"],
                candidate["candidate_id"],
                candidate["display_name"],
                candidate["score"],
                "|".join(candidate["matched_required_skills"]),
                "|".join(candidate["missing_required_skills"]),
            ])
        body = output.getvalue().encode()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/csv")
        self.send_header("Content-Disposition", f'attachment; filename="{run["run_id"]}.csv"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8000), Handler)
    print("MeritRank dashboard: http://127.0.0.1:8000")
    server.serve_forever()


if __name__ == "__main__":
    main()
