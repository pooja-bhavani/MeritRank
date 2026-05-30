import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from talent_ranker.evaluation import ranking_metrics  # noqa: E402
from talent_ranker.server import rank_payload  # noqa: E402


def main() -> None:
    result = rank_payload(json.loads((ROOT / "data" / "demo_request.json").read_text()))
    labels = {"C-101": 2, "C-105": 2, "C-102": 1, "C-103": 1, "C-104": 0}
    metrics = ranking_metrics(result["shortlist"], labels, k=5)
    print("Synthetic smoke-test metrics. Do not report these as official benchmark results.")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()

