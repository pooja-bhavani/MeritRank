from .models import Candidate, Job, RankedCandidate
from .text import bm25_scores, extract_ats_keywords, jaccard, normalize_skill, semantic_similarity, tokenize

WEIGHTS = {
    "text_relevance": 0.20,
    "semantic_similarity": 0.16,
    "required_skills": 0.27,
    "preferred_skills": 0.10,
    "role_similarity": 0.07,
    "experience_fit": 0.08,
    "activity_signal": 0.06,
    "location_fit": 0.06,
}


def _bounded(value: float) -> float:
    return max(0.0, min(1.0, value))


def _coverage(target: list[str], candidate_skills: list[str]) -> tuple[float, list[str], list[str]]:
    normalized_candidate = {normalize_skill(skill) for skill in candidate_skills}
    normalized_target = [normalize_skill(skill) for skill in target]
    matched = sorted(skill for skill in normalized_target if skill in normalized_candidate)
    missing = sorted(skill for skill in normalized_target if skill not in normalized_candidate)
    return (len(matched) / len(normalized_target) if normalized_target else 1.0, matched, missing)


def _experience_fit(job: Job, candidate: Candidate) -> float:
    if candidate.years_experience < job.min_years_experience:
        return _bounded(candidate.years_experience / max(job.min_years_experience, 1))
    preferred = max(job.preferred_years_experience, job.min_years_experience, 1)
    return _bounded(0.8 + 0.2 * candidate.years_experience / preferred)


def _activity_signal(candidate: Candidate) -> float:
    freshness = _bounded(1 - candidate.activity.active_days_ago / 180)
    return (
        0.35 * _bounded(candidate.activity.profile_completeness)
        + 0.35 * _bounded(candidate.activity.response_rate)
        + 0.30 * freshness
    )


def _location_fit(job: Job, candidate: Candidate) -> float:
    if not job.locations:
        return 1.0
    if candidate.location.lower() in {location.lower() for location in job.locations}:
        return 1.0
    if job.remote_allowed and candidate.open_to_remote:
        return 0.9
    return 0.0


def _profile_document(candidate: Candidate) -> str:
    # Identifying fields are deliberately excluded from the scoring document.
    return " ".join([
        candidate.headline,
        candidate.summary,
        " ".join(candidate.skills),
        " ".join(candidate.roles),
    ])


def rank_candidates(job: Job, candidates: list[Candidate]) -> list[RankedCandidate]:
    query = " ".join([
        job.title,
        job.description,
        " ".join(job.required_skills),
        " ".join(job.preferred_skills),
    ])
    text_scores = bm25_scores(query, [_profile_document(candidate) for candidate in candidates])
    scored: list[RankedCandidate] = []

    for candidate, text_score in zip(candidates, text_scores):
        required_score, matched_required, missing_required = _coverage(
            job.required_skills, candidate.skills
        )
        preferred_score, matched_preferred, _ = _coverage(
            job.preferred_skills, candidate.skills
        )
        components = {
            "text_relevance": text_score,
            "semantic_similarity": semantic_similarity(query, _profile_document(candidate)),
            "required_skills": required_score,
            "preferred_skills": preferred_score,
            "role_similarity": jaccard(tokenize(job.title), tokenize(" ".join(candidate.roles))),
            "experience_fit": _experience_fit(job, candidate),
            "activity_signal": _activity_signal(candidate),
            "location_fit": _location_fit(job, candidate),
        }
        raw_score = sum(WEIGHTS[name] * value for name, value in components.items())
        # Missing hard requirements remain visible and also reduce the shortlist score.
        requirement_penalty = min(0.24, len(missing_required) * 0.06)
        score = round(100 * _bounded(raw_score - requirement_penalty), 2)
        contributions = {
            name: round(100 * WEIGHTS[name] * value, 2)
            for name, value in components.items()
        }
        profile_document = _profile_document(candidate)
        job_keywords = sorted({
            *extract_ats_keywords(job.description),
            *(normalize_skill(skill) for skill in job.required_skills),
            *(normalize_skill(skill) for skill in job.preferred_skills),
        })
        candidate_keywords = set(extract_ats_keywords(profile_document))
        candidate_keywords.update(normalize_skill(skill) for skill in candidate.skills)
        matched_job_keywords = sorted(set(job_keywords) & candidate_keywords)
        missing_job_keywords = sorted(set(job_keywords) - candidate_keywords)
        keyword_coverage = round(
            100 * len(matched_job_keywords) / len(job_keywords), 1
        ) if job_keywords else 100.0
        improvement_suggestions = _improvement_suggestions(
            missing_required, missing_job_keywords, job, candidate
        )
        reasons = []
        if matched_required:
            reasons.append(f"Matches {len(matched_required)}/{len(job.required_skills)} required skills")
        if matched_preferred:
            reasons.append(f"Adds preferred skills: {', '.join(matched_preferred)}")
        if components["activity_signal"] >= 0.75:
            reasons.append("Recent, complete profile with strong response signals")
        if components["location_fit"] >= 0.9:
            reasons.append("Matches the role's location preference")
        if missing_required:
            reasons.append(f"Review required-skill gaps: {', '.join(missing_required)}")
        scored.append(RankedCandidate(
            rank=0,
            candidate_id=candidate.candidate_id,
            display_name=candidate.name or candidate.candidate_id,
            score=score,
            recommendation=_recommendation(score, missing_required),
            components={name: round(value, 3) for name, value in components.items()},
            contributions=contributions,
            matched_required_skills=matched_required,
            missing_required_skills=missing_required,
            matched_preferred_skills=matched_preferred,
            matched_job_keywords=matched_job_keywords,
            missing_job_keywords=missing_job_keywords,
            keyword_coverage=keyword_coverage,
            improvement_suggestions=improvement_suggestions,
            evidence_summary=_evidence_summary(matched_required, missing_required, matched_job_keywords),
            reasons=reasons,
        ))

    scored.sort(key=lambda candidate: (-candidate.score, candidate.candidate_id))
    for index, candidate in enumerate(scored, start=1):
        candidate.rank = index
    return scored


def _recommendation(score: float, missing_required: list[str]) -> str:
    if score >= 75 and not missing_required:
        return "Shortlist"
    if score >= 50 or len(missing_required) <= 1:
        return "Review"
    return "Hold"


def _evidence_summary(
    matched_required: list[str],
    missing_required: list[str],
    matched_job_keywords: list[str],
) -> str:
    return (
        f"{len(matched_required)} required skills verified; "
        f"{len(missing_required)} required gaps; "
        f"{len(matched_job_keywords)} JD keywords evidenced in the profile."
    )


def _improvement_suggestions(
    missing_required: list[str],
    missing_job_keywords: list[str],
    job: Job,
    candidate: Candidate,
) -> list[str]:
    suggestions = []
    if missing_required:
        suggestions.append(
            "If accurate, add evidence for required skills: "
            + ", ".join(missing_required)
            + ". Mention the project, your contribution, and a measurable outcome."
        )
    broader_gaps = [keyword for keyword in missing_job_keywords if keyword not in missing_required]
    if broader_gaps:
        suggestions.append(
            "The job description also emphasizes: "
            + ", ".join(broader_gaps[:10])
            + ". Add only the terms you can support with real experience."
        )
    if not candidate.roles:
        suggestions.append(
            "Use clear role headings so recruiters can connect your experience to the target role."
        )
    if candidate.years_experience < job.min_years_experience:
        suggestions.append(
            f"The role asks for {job.min_years_experience:g}+ years. Make dates and relevant "
            "experience easy to verify; do not inflate tenure."
        )
    suggestions.append(
        "Rewrite relevant bullets as: action + tool or skill + scale + measurable result."
    )
    return suggestions
