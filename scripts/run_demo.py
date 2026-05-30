import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from talent_ranker.server import rank_payload  # noqa: E402


def main() -> None:
    result = rank_payload(json.loads((ROOT / "data" / "demo_request.json").read_text()))
    output = ROOT / "artifacts" / "ranked_candidates.csv"
    output.parent.mkdir(exist_ok=True)
    with output.open("w", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["rank", "candidate_id", "display_name", "score", "matched_required", "missing_required"])
        for candidate in result["shortlist"]:
            writer.writerow([
                candidate["rank"],
                candidate["candidate_id"],
                candidate["display_name"],
                candidate["score"],
                "|".join(candidate["matched_required_skills"]),
                "|".join(candidate["missing_required_skills"]),
            ])

    print("MeritRank synthetic demo shortlist")
    for candidate in result["shortlist"]:
        print(f'{candidate["rank"]:>2}. {candidate["display_name"]:<18} {candidate["score"]:>6.2f}')
        print(f'    {"; ".join(candidate["reasons"])}')
    print(f"\nCSV export: {output}")


if __name__ == "__main__":
    main()

