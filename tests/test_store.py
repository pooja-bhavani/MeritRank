import tempfile
import unittest
import base64
from pathlib import Path

from talent_ranker.store import Store


CSV_TEXT = """candidate_id,name,headline,summary,skills,roles,years_experience,location,open_to_remote,profile_completeness,response_rate,active_days_ago
C-1,Strong Candidate,Search engineer,Builds semantic ranking APIs,Python|Semantic Search|AWS,Search Engineer,5,Remote,true,0.9,0.8,4
C-2,Backend Candidate,Backend engineer,Builds APIs,Python|AWS,Backend Engineer,4,Pune,true,0.8,0.7,20
"""


class StoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tempdir.name) / "state.json")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_import_and_rank_persist_a_run(self) -> None:
        job = self.store.save_job({
            "title": "Search Engineer",
            "description": "Build semantic search APIs",
            "required_skills": ["Python", "Semantic Search"],
            "preferred_skills": ["AWS"],
            "locations": ["Remote"],
            "remote_allowed": True,
        })
        result = self.store.import_candidates(CSV_TEXT)
        run = self.store.rank(job["job_id"])
        self.assertEqual({"imported": 2, "total": 2}, result)
        self.assertEqual("C-1", run["shortlist"][0]["candidate_id"])
        self.assertEqual(1, len(self.store.list_runs()))
        self.assertIn("latency_ms", run)

    def test_evaluation_is_saved_on_the_run(self) -> None:
        job = self.store.save_job({
            "title": "Search Engineer",
            "description": "Build semantic search APIs",
            "required_skills": ["Python"],
        })
        self.store.import_candidates(CSV_TEXT)
        run = self.store.rank(job["job_id"])
        metrics = self.store.evaluate_run(run["run_id"], "candidate_id,relevance\nC-1,2\nC-2,0\n")
        self.assertEqual(1.0, metrics["mrr"])
        self.assertEqual(metrics, self.store.get_run(run["run_id"])["evaluation"])

    def test_candidate_import_updates_existing_candidate(self) -> None:
        self.store.import_candidates(CSV_TEXT)
        self.store.import_candidates(CSV_TEXT.replace("Strong Candidate", "Updated Candidate"))
        candidates = self.store.list_candidates()
        self.assertEqual(2, len(candidates))
        self.assertEqual("Updated Candidate", candidates[0]["name"])

    def test_duplicate_resume_upload_is_skipped(self) -> None:
        resume = base64.b64encode(
            b"Riya Shah\nPlatform Engineer\nBuilt AWS Terraform and Kubernetes systems for 5 years."
        ).decode()
        first = self.store.import_resume("riya.txt", resume)
        second = self.store.import_resume("riya.txt", resume)
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(1, len(self.store.list_candidates()))

    def test_blank_requirements_are_inferred_from_job_description(self) -> None:
        job = self.store.save_job({
            "title": "Platform Engineer",
            "description": "Operate Kubernetes with Terraform, Helm, and ArgoCD",
        })
        self.assertTrue(job["requirements_inferred_from_jd"])
        self.assertIn("kubernetes", job["required_skills"])
        self.assertIn("terraform", job["required_skills"])


if __name__ == "__main__":
    unittest.main()
