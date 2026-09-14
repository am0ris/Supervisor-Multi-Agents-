"""
Search-engine discovery for job platforms that do not offer a public,
unauthenticated API or feed (LinkedIn, Indeed, Glassdoor, Wuzzuf, Bayt,
Wellfound). This module NEVER logs in, solves CAPTCHAs, or bypasses
anti-bot mechanisms. It only issues a normal web search scoped to the
platform's domain (e.g. `site:linkedin.com/jobs ...`) via the configured
search provider, then returns the public result links. Whether those
links are viewable without login is entirely up to the platform - we
never attempt to get around a login wall if one appears.

Full page content (for JSON-LD extraction) is fetched later by the
extraction agent, via `fetch_url`, which itself respects robots.txt and
SSRF protections. If a platform blocks the fetch or requires login, the
job is kept with only the search snippet - never faked.
"""
from dataclasses import dataclass

from jobs.date_utils import classify_date
from jobs.schema import JobPosting
from search.base import SearchProvider, SearchProviderError

# Domain filters used for `site:` scoped search-engine discovery. This is
# the single place to add a new platform - see README for the "adding a
# platform" walkthrough.
PLATFORM_DOMAINS: dict[str, str] = {
    "linkedin": "linkedin.com/jobs",
    "indeed": "indeed.com",
    "glassdoor": "glassdoor.com",
    "wuzzuf": "wuzzuf.net",
    "bayt": "bayt.com",
    "wellfound": "wellfound.com",
}


@dataclass
class DiscoveryStats:
    platform: str
    query: str
    result_count: int
    provider_used: str | None
    error: str | None = None


async def discover_platform_jobs(
    provider: SearchProvider,
    platform: str,
    query: str,
    max_results: int,
    timelimit: str | None,
) -> tuple[list[JobPosting], DiscoveryStats]:
    """
    Runs one `site:<platform-domain> <query>` search and converts results
    into JobPosting stubs. These stubs typically have UNKNOWN or INDEXED
    date confidence (a search engine's result date is not the same as the
    page's actual publish date) - the extraction agent may upgrade this
    later via JSON-LD if the page is fetchable.
    """
    domain = PLATFORM_DOMAINS.get(platform)
    if not domain:
        raise ValueError(f"Unknown job platform: {platform}")

    scoped_query = f"site:{domain} {query}"

    try:
        results = await provider.search(scoped_query, max_results=max_results, timelimit=timelimit)
    except SearchProviderError as e:
        return [], DiscoveryStats(platform=platform, query=scoped_query, result_count=0, provider_used=None, error=str(e))

    jobs = []
    for r in results:
        # A search engine's own date signal is its crawl/index estimate,
        # not a verified publish date - classify it as `indexed`, not
        # `published`, so ranking/review never mistake it for verified.
        posted_date, confidence, verified = classify_date(indexed_raw=r.published_date)

        jobs.append(
            JobPosting(
                title=r.title,
                url=r.url,
                source=platform,
                description=r.snippet or None,
                posted_date=posted_date,
                date_confidence=confidence,
                date_verified=verified,
            )
        )

    return jobs, DiscoveryStats(
        platform=platform, query=scoped_query, result_count=len(jobs), provider_used=r.source_provider if results else None
    )
