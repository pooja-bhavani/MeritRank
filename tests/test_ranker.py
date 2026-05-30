import unittest

from talent_ranker.models import Candidate, Job
from talent_ranker.ranker import rank_candidates


class RankerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.job = Job(
            job_id="job",
            title="Python Search Engineer",
            description="Build semantic search APIs",
            required_skills=["Python", "Semantic Search"],
            preferred_skills=["AWS"],
            min_years_experience=3,
            preferred_years_experience=5,
            locations=["Remote"],
            remote_allowed=True,
        )

    def candidate(self, candidate_id: str, **overrides: object) -> Candidate:
        defaults = {
            "candidate_id": candidate_id,
            "headline": "Search engineer",
            "summary": "Builds ranking systems",
            "skills": ["Python", "Semantic Search", "AWS"],
            "roles": ["Search Engineer"],
            "years_experience": 5,
            "location": "Remote",
            "open_to_remote": True,
        }
        defaults.update(overrides)
        return Candidate(**defaults)

    def test_complete_required_skill_match_ranks_first(self) -> None:
        complete = self.candidate("complete")
        incomplete = self.candidate("incomplete", skills=["Python", "AWS"])
        ranked = rank_candidates(self.job, [incomplete, complete])
        self.assertEqual("complete", ranked[0].candidate_id)
        self.assertEqual(["semantic search"], ranked[1].missing_required_skills)

    def test_skill_aliases_are_normalized(self) -> None:
        job = Job(job_id="job", title="Platform Engineer", description="", required_skills=["Kubernetes"])
        ranked = rank_candidates(job, [self.candidate("alias", skills=["k8s"])])
        self.assertEqual(["kubernetes"], ranked[0].matched_required_skills)

    def test_cicd_spelling_is_normalized(self) -> None:
        job = Job(job_id="job", title="DevOps Engineer", description="", required_skills=["CICD"])
        ranked = rank_candidates(job, [self.candidate("alias", skills=["CI/CD"])])
        self.assertEqual(["ci/cd"], ranked[0].matched_required_skills)

    def test_name_and_contact_details_do_not_affect_score(self) -> None:
        first = self.candidate("A", name="One", email="one@example.invalid")
        second = self.candidate("B", name="Completely Different", email="two@example.invalid")
        ranked = rank_candidates(self.job, [first, second])
        self.assertEqual(ranked[0].score, ranked[1].score)

    def test_missing_job_keywords_generate_truthful_improvement_advice(self) -> None:
        job = Job(
            job_id="job",
            title="DevOps Engineer",
            description="Operate Kubernetes workloads using Terraform and Jenkins",
            required_skills=["Kubernetes", "Terraform"],
            preferred_skills=["Jenkins"],
        )
        ranked = rank_candidates(job, [self.candidate("candidate", skills=["Kubernetes"])])
        self.assertIn("terraform", ranked[0].missing_job_keywords)
        self.assertIn("jenkins", ranked[0].missing_job_keywords)
        self.assertIn("If accurate", ranked[0].improvement_suggestions[0])

    def test_ranked_candidate_exposes_semantic_score_and_contributions(self) -> None:
        ranked = rank_candidates(self.job, [self.candidate("candidate")])
        self.assertIn("semantic_similarity", ranked[0].components)
        self.assertIn("semantic_similarity", ranked[0].contributions)
        self.assertEqual("Shortlist", ranked[0].recommendation)


if __name__ == "__main__":
    unittest.main()
