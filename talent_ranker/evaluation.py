import csv
import io
import math
from typing import Any


def parse_labels(csv_text: str) -> dict[str, float]:
    reader = csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames or not {"candidate_id", "relevance"}.issubset(reader.fieldnames):
        raise ValueError("Labels CSV must contain candidate_id and relevance columns")
    labels = {}
    for row in reader:
        candidate_id = row["candidate_id"].strip()
        if candidate_id:
            labels[candidate_id] = float(row["relevance"])
    if not labels:
        raise ValueError("Labels CSV contains no labeled candidates")
    return labels


def ranking_metrics(shortlist: list[dict[str, Any]], labels: dict[str, float], k: int = 10) -> dict[str, Any]:
    ranked_ids = [candidate["candidate_id"] for candidate in shortlist[:k]]
    relevant_ids = {candidate_id for candidate_id, relevance in labels.items() if relevance > 0}
    hits = [candidate_id for candidate_id in ranked_ids if candidate_id in relevant_ids]
    ideal = sorted(labels.values(), reverse=True)[:k]
    dcg = _dcg([labels.get(candidate_id, 0) for candidate_id in ranked_ids])
    ideal_dcg = _dcg(ideal)
    first_relevant = next(
        (index for index, candidate_id in enumerate(ranked_ids, start=1) if candidate_id in relevant_ids),
        None,
    )
    return {
        "k": k,
        "labeled_candidates": len(labels),
        "relevant_candidates": len(relevant_ids),
        "precision_at_k": round(len(hits) / k, 4),
        "recall_at_k": round(len(hits) / len(relevant_ids), 4) if relevant_ids else 0.0,
        "ndcg_at_k": round(dcg / ideal_dcg, 4) if ideal_dcg else 0.0,
        "mrr": round(1 / first_relevant, 4) if first_relevant else 0.0,
    }


def _dcg(relevances: list[float]) -> float:
    return sum(
        (2 ** relevance - 1) / math.log2(index + 1)
        for index, relevance in enumerate(relevances, start=1)
    )

