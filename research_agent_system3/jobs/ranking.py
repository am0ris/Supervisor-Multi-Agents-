"""
Deterministic ranking for job search results.

Scoring is a weighted sum of explicit, inspectable signals - not an LLM
judgment call - so results are reproducible and the weights can be tuned
without touching prompts. `rank_jobs` sorts in place and also sets
`relevance_score` on each JobPosting.
"""
from dataclasses import dataclass
from difflib import SequenceMatcher

from jobs.date_utils import parse_date_safe, app_now
from jobs.schema import JobPosting, DateConfidence

# Source reliability weights: platforms with structured, verifiable data
# (JSON-LD, official APIs) score higher than generic search-engine hits.
_SOURCE_RELIABILITY = {
    "remoteok": 1.0,
    "weworkremotely": 1.0,
    "company_career_page": 0.95,
    "linkedin": 0.75,
    "indeed": 0.75,
    "glassdoor": 0.7,
    "wuzzuf": 0.75,
    "bayt": 0.75,
    "wellfound": 0.75,
    "search_discovery": 0.5,
}

_DATE_CONFIDENCE_WEIGHT = {
    DateConfidence.PUBLISHED: 1.0,
    DateConfidence.UPDATED: 0.85,
    DateConfidence.INDEXED: 0.4,
    DateConfidence.UNKNOWN: 0.0,
}


@dataclass
class RankingWeights:
    title_relevance: float = 0.30
    skill_match: float = 0.20
    location_match: float = 0.15
    recency: float = 0.15
    source_reliability: float = 0.10
    date_verification: float = 0.10


def _text_relevance(query: str, text: str | None) -> float:
    if not text:
        return 0.0
    return SequenceMatcher(None, query.lower(), text.lower()).ratio()


def _skill_match_score(required_skills_from_query: list[str], job: JobPosting) -> float:
    if not required_skills_from_query:
        return 0.5  # neutral - no skill filter requested
    job_skills = {s.lower() for s in (job.required_skills + job.preferred_skills)}
    if not job_skills:
        return 0.0
    matched = sum(1 for s in required_skills_from_query if s.lower() in job_skills)
    return matched / len(required_skills_from_query)


def _location_match_score(target_location: str | None, job: JobPosting) -> float:
    if not target_location:
        return 0.5  # neutral - no location filter requested
    if not job.location:
        return 0.0
    if target_location.lower() in job.location.lower():
        return 1.0
    if job.remote_type and job.remote_type.lower() == "remote":
        return 0.7  # remote jobs are a reasonable partial match for any location
    return 0.0


def _recency_score(job: JobPosting) -> float:
    confidence_weight = _DATE_CONFIDENCE_WEIGHT.get(job.date_confidence, 0.0)
    if confidence_weight == 0.0 or not job.posted_date:
        return 0.0
    date = parse_date_safe(job.posted_date)
    if date is None:
        return 0.0
    age_days = max(0, (app_now() - date).days)
    # decays smoothly: ~1.0 at 0 days, ~0.5 at 30 days, approaching 0 by ~180 days
    recency = max(0.0, 1.0 - (age_days / 180))
    return recency * confidence_weight


def score_job(
    job: JobPosting,
    query: str,
    required_skills: list[str] | None = None,
    target_location: str | None = None,
    weights: RankingWeights | None = None,
) -> float:
    weights = weights or RankingWeights()
    required_skills = required_skills or []

    title_score = _text_relevance(query, job.title)
    skill_score = _skill_match_score(required_skills, job)
    location_score = _location_match_score(target_location, job)
    recency = _recency_score(job)
    source_score = _SOURCE_RELIABILITY.get(job.source, 0.5)
    date_verification_score = 1.0 if job.date_verified else 0.0

    total = (
        title_score * weights.title_relevance
        + skill_score * weights.skill_match
        + location_score * weights.location_match
        + recency * weights.recency
        + source_score * weights.source_reliability
        + date_verification_score * weights.date_verification
    )
    return round(total, 4)


def rank_jobs(
    jobs: list[JobPosting],
    query: str,
    required_skills: list[str] | None = None,
    target_location: str | None = None,
    weights: RankingWeights | None = None,
) -> list[JobPosting]:
    """Scores and sorts jobs by relevance_score, descending. Mutates and returns the list."""
    for job in jobs:
        job.relevance_score = score_job(job, query, required_skills, target_location, weights)
    jobs.sort(key=lambda j: j.relevance_score or 0.0, reverse=True)
    return jobs
