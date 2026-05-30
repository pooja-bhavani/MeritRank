from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Job:
    job_id: str
    title: str
    description: str
    required_skills: list[str] = field(default_factory=list)
    preferred_skills: list[str] = field(default_factory=list)
    min_years_experience: float = 0
    preferred_years_experience: float = 0
    locations: list[str] = field(default_factory=list)
    remote_allowed: bool = False
    company: str = ""
    source_url: str = ""
    requirements_inferred_from_jd: bool = False

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Job":
        return cls(**value)


@dataclass
class ActivitySignals:
    profile_completeness: float = 0.5
    response_rate: float = 0.5
    active_days_ago: int = 90

    @classmethod
    def from_dict(cls, value: dict[str, Any] | None) -> "ActivitySignals":
        return cls(**(value or {}))


@dataclass
class Candidate:
    candidate_id: str
    headline: str
    summary: str
    skills: list[str]
    roles: list[str]
    years_experience: float
    location: str
    open_to_remote: bool = False
    activity: ActivitySignals = field(default_factory=ActivitySignals)
    name: str = ""
    email: str = ""
    phone: str = ""

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Candidate":
        data = dict(value)
        data["activity"] = ActivitySignals.from_dict(data.get("activity"))
        fields = cls.__dataclass_fields__
        return cls(**{key: data[key] for key in fields if key in data})


@dataclass
class RankedCandidate:
    rank: int
    candidate_id: str
    display_name: str
    score: float
    recommendation: str
    components: dict[str, float]
    contributions: dict[str, float]
    matched_required_skills: list[str]
    missing_required_skills: list[str]
    matched_preferred_skills: list[str]
    matched_job_keywords: list[str]
    missing_job_keywords: list[str]
    keyword_coverage: float
    improvement_suggestions: list[str]
    evidence_summary: str
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
