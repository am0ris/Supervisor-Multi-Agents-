"""
Detects whether a query is a job-search request. Deterministic and
keyword-based (not LLM-driven) so classification is instant, free, and
reproducible - an LLM call here would add latency and non-determinism
for something a simple rule handles reliably.
"""
import re

_JOB_KEYWORDS = [
    r"\bjob\b", r"\bjobs\b", r"\bhiring\b", r"\bvacanc(y|ies)\b",
    r"\bposition(s)?\b", r"\bcareer(s)?\b", r"\bhire\b", r"\bemployment\b",
    r"\bopenings?\b", r"\brecruit(ing|ment)?\b", r"\bapply\b",
]
_COMPILED = [re.compile(p, re.IGNORECASE) for p in _JOB_KEYWORDS]


def is_job_search_query(query: str) -> bool:
    """Returns True if the query looks like a job-search request."""
    if not query:
        return False
    return any(pattern.search(query) for pattern in _COMPILED)


def detect_query_type(query: str) -> str:
    return "job_search" if is_job_search_query(query) else "general_research"
