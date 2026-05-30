import json
import unittest
from pathlib import Path

from talent_ranker.server import rank_payload


class ServerTest(unittest.TestCase):
    def test_demo_payload_ranks_all_candidates(self) -> None:
        payload = json.loads(Path("data/demo_request.json").read_text())
        result = rank_payload(payload)
        self.assertEqual(5, result["candidate_count"])
        self.assertEqual("C-101", result["shortlist"][0]["candidate_id"])
        self.assertIn("excluded from scoring", result["scoring_notice"])


if __name__ == "__main__":
    unittest.main()

