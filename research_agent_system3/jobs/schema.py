"""
Structured schema for a job posting. All fields are optional except
`title` and `url`/`source` — missing information must stay None, never
be guessed or hallucinated by an LLM.
"""
from enum import Enum
from pydantic import BaseModel, Field


class DateConfidence(str, Enum):
    """
    How trustworthy a date field is. Never assume "unknown" means recent.
    """
    PUBLISHED = "published_date"    # explicit publish/posted date found in structured data or page
    UPDATED = "updated_date"        # explicit "last updated" date found
    INDEXED = "indexed_date"        # only the search engine's crawl/index date is known
    UNKNOWN = "date_unknown"        # no reliable date could be found at all


class JobPosting(BaseModel):
    title: str
    company: str | None = None
    location: str | None = None
    remote_type: str | None = None          # "remote" / "hybrid" / "on-site" / None
    employment_type: str | None = None      # "full-time" / "part-time" / "contract" / None
    experience_level: str | None = None     # "entry" / "mid" / "senior" / None
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    salary: str | None = None
    currency: str | None = None
    posted_date: str | None = None          # ISO date string, if known
    updated_date: str | None = None
    application_deadline: str | None = None
    url: str
    source: str                              # e.g. "linkedin", "remoteok", "company_career_page"
    description: str | None = None
    date_confidence: DateConfidence = DateConfidence.UNKNOWN
    date_verified: bool = False              # True only if posted_date came from structured data/page metadata

    # internal bookkeeping (not shown to the end user, used for dedup/ranking)
    canonical_url: str | None = None
    relevance_score: float | None = None
