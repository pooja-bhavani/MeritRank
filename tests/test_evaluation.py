import unittest

from talent_ranker.evaluation import parse_labels, ranking_metrics


class EvaluationTest(unittest.TestCase):
    def test_metrics_reward_relevant_candidates_near_the_top(self) -> None:
        shortlist = [{"candidate_id": "A"}, {"candidate_id": "B"}, {"candidate_id": "C"}]
        metrics = ranking_metrics(shortlist, {"A": 2, "B": 1, "C": 0}, k=3)
        self.assertEqual(1.0, metrics["ndcg_at_k"])
        self.assertEqual(1.0, metrics["recall_at_k"])
        self.assertEqual(1.0, metrics["mrr"])

    def test_labels_require_candidate_and_relevance_columns(self) -> None:
        with self.assertRaisesRegex(ValueError, "candidate_id and relevance"):
            parse_labels("candidate_id,label\nA,1\n")


if __name__ == "__main__":
    unittest.main()

