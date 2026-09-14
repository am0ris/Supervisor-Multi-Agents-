"""Tool: search_jobs — multi-source, multi-query job search.

Wraps jobs/aggregator.py behind the MCP interface, consistent with
search_web and fetch_url, so the research agent never talks to job
platforms directly - it only calls this tool.
"""
import os

from jobs.aggregator import search_jobs as _search_jobs_impl
from search.factory import build_provider_chain

_PROVIDER_CHAIN_WRAPPER = None


def _get_provider():
    """Lazily builds a single provider from the configured chain (the
    first entry) for job-platform discovery searches. Built lazily so
    importing this module doesn't require env vars to already be set."""
    global _PROVIDER_CHAIN_WRAPPER
    if _PROVIDER_CHAIN_WRAPPER is None:
        chain = build_provider_chain(
            primary=os.getenv("SEARCH_PROVIDER", "duckduckgo"),
            fallback_csv=os.getenv("SEARCH_PROVIDER_FALLBACK", "duckduckgo"),
            env=os.environ,
        )
        _PROVIDER_CHAIN_WRAPPER = chain
    return _PROVIDER_CHAIN_WRAPPER


class _ChainAsProvider:
    """Adapts a ProviderChain (which returns tuples) to the single-provider
    `search(...) -> list[SearchResult]` interface the aggregator expects."""

    name = "provider_chain"

    def __init__(self, chain):
        self.chain = chain

    async def search(self, query, max_results=5, timelimit=None):
        results, _used, _failed = await self.chain.search(query, max_results, timelimit)
        return results


async def search_jobs(
    query: str,
    max_results: int = int(os.getenv("MAX_TOTAL_RESULTS", 30)),
    timelimit: str = "m",
    platforms: list[str] | None = None,
    target_location: str | None = None,
    required_skills: list[str] | None = None,
    max_search_queries: int = int(os.getenv("MAX_SEARCH_QUERIES", 4)),
    max_results_per_source: int = int(os.getenv("MAX_RESULTS_PER_SOURCE", 5)),
    max_concurrent_searches: int = int(os.getenv("MAX_CONCURRENT_SEARCHES", 5)),
    search_timeout: float = float(os.getenv("SEARCH_TIMEOUT", 15.0)),
) -> dict:
    """
    Searches for jobs across multiple sources: direct public APIs/feeds
    (RemoteOK, We Work Remotely) and search-engine discovery for platforms
    that require login (LinkedIn, Indeed, Wuzzuf, Glassdoor, Bayt,
    Wellfound). Never logs in, solves CAPTCHAs, or bypasses access
    controls - discovery only surfaces public search-result links.

    Args:
        query: e.g. "Generative AI Engineer jobs in Egypt".
        max_results: max number of ranked, deduplicated jobs to return.
        timelimit: recency filter - "d"/"w"/"m"/"y".
        platforms: subset of platform names to search (default: all configured).
        target_location: optional location filter used for ranking.
        required_skills: optional skill list used for ranking.

    Returns:
        dict with "jobs" (list of job dicts) and "stats" (search metadata:
        queries used, sources searched, result counts, errors, duration).
    """
    provider = _ChainAsProvider(_get_provider())
    retries = int(os.getenv("SEARCH_RETRIES", 1))

    jobs, stats = await _search_jobs_impl(
        query,
        provider,
        max_search_queries=max_search_queries,
        max_results_per_source=max_results_per_source,
        max_total_results=max_results,
        max_concurrent_searches=max_concurrent_searches,
        search_timeout=search_timeout,
        retries=retries,
        timelimit=timelimit or None,
        platforms=platforms,
        target_location=target_location,
        required_skills=required_skills,
    )

    return {
        "jobs": [j.model_dump() for j in jobs],
        "stats": {
            "queries_used": stats.queries_used,
            "sources_searched": stats.sources_searched,
            "total_results": stats.total_results,
            "unique_results": stats.unique_results,
            "verified_recent_results": stats.verified_recent_results,
            "retry_count": stats.retry_count,
            "errors": stats.errors,
            "search_duration_seconds": stats.search_duration_seconds,
        },
    }
