"""
Deduplication for job postings gathered from multiple sources.

The same job frequently appears via several search engines, aggregators,
and the company's own career page. We use two complementary signals:

1. Canonical URL matching (strip tracking params/fragments, normalize
   host/scheme) - catches exact re-posts of the same URL.
2. Fuzzy matching on (title, company, location) - catches the same job
   posted independently on different platforms with different URLs.
"""
from difflib import SequenceMatcher
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

from jobs.schema import JobPosting

# Tracking/analytics query params that should never affect URL identity.
_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "referrer", "gclid", "fbclid", "trk", "trackingId", "src",
}

_SIMILARITY_THRESHOLD = 0.88

# Common legal-entity suffixes stripped before comparing company names, so
# "Acme Inc." and "Acme Inc" are treated as the same company. This is
# intentionally narrow - we do NOT fuzzy-match company names beyond this,
# because two similarly-spelled but distinct companies (e.g. "Company A"
# vs "Company B") must never be merged.
_COMPANY_SUFFIXES = {"inc", "inc.", "llc", "ltd", "ltd.", "corp", "corp.", "co", "co."}


def _normalize_company(name: str) -> str:
    if not name:
        return ""
    tokens = [t.strip(".,") for t in name.lower().split()]
    tokens = [t for t in tokens if t not in _COMPANY_SUFFIXES]
    return " ".join(tokens)


def canonicalize_url(url: str) -> str:
    """Normalizes a URL for identity comparison: lowercase host, strip
    tracking params and fragment, drop trailing slash."""
    if not url:
        return ""
    parsed = urlparse(url)
    clean_query = [
        (k, v) for k, v in parse_qsl(parsed.query) if k.lower() not in _TRACKING_PARAMS
    ]
    normalized_path = parsed.path.rstrip("/") or "/"
    canonical = urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        normalized_path,
        "",
        urlencode(sorted(clean_query)),
        "",
    ))
    return canonical


def _text_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _fuzzy_match(a: JobPosting, b: JobPosting) -> bool:
    title_sim = _text_similarity(a.title, b.title)
    location_sim = _text_similarity(a.location or "", b.location or "")

    # Company names must match exactly after normalization (case, spacing,
    # common suffixes) - NOT fuzzy-matched. Two distinct companies with
    # similarly-spelled names must never be treated as duplicates.
    company_a = _normalize_company(a.company or "")
    company_b = _normalize_company(b.company or "")
    if not company_a or not company_b or company_a != company_b:
        return False

    return title_sim >= _SIMILARITY_THRESHOLD and location_sim >= 0.5


def deduplicate_jobs(jobs: list[JobPosting]) -> list[JobPosting]:
    """
    Returns a new list with duplicates removed. When two entries are
    judged duplicates, the one with better date verification (and then
    more complete fields) is kept.
    """
    for job in jobs:
        job.canonical_url = canonicalize_url(job.url)

    def completeness_score(job: JobPosting) -> tuple:
        return (
            job.date_verified,
            bool(job.description),
            bool(job.salary),
            len(job.required_skills),
        )

    kept: list[JobPosting] = []

    for job in jobs:
        duplicate_index = None
        for i, existing in enumerate(kept):
            if job.canonical_url and job.canonical_url == existing.canonical_url:
                duplicate_index = i
                break
            if _fuzzy_match(job, existing):
                duplicate_index = i
                break

        if duplicate_index is None:
            kept.append(job)
        else:
            if completeness_score(job) > completeness_score(kept[duplicate_index]):
                kept[duplicate_index] = job

    return kept
