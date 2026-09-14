"""
Job search orchestration: query expansion -> parallel multi-source search
(direct APIs/feeds + search-engine discovery for auth-walled platforms)
-> deduplication -> ranking.

Resilience: every source call is wrapped with a timeout, limited retries
with exponential backoff, and a concurrency limit. One failing source
(a timeout, a rate limit, a malformed response) never fails the whole
search - it's recorded in `SearchStats.errors` and the rest continue.
"""
import asyncio
import time
from dataclasses import dataclass, field

from jobs.dedup import deduplicate_jobs
from jobs.query_expansion import expand_query
from jobs.ranking import rank_jobs
from jobs.schema import JobPosting
from jobs.sources.remoteok import RemoteOkSource
from jobs.sources.weworkremotely import WeWorkRemotelySource
from jobs.sources.search_discovery import discover_platform_jobs, PLATFORM_DOMAINS
from jobs.sources.base import JobSourceError
from search.base import SearchProvider, SearchProviderError


@dataclass
class JobSearchStats:
    queries_used: list[str] = field(default_factory=list)
    sources_searched: list[str] = field(default_factory=list)
    total_results: int = 0
    unique_results: int = 0
    verified_recent_results: int = 0
    retry_count: int = 0
    errors: list[str] = field(default_factory=list)
    search_duration_seconds: float = 0.0


async def _with_retry(coro_factory, retries: int, base_delay: float, stats: JobSearchStats, label: str):
    """Runs an async operation with limited retries and exponential backoff."""
    last_error = None
    for attempt in range(retries + 1):
        try:
            return await coro_factory()
        except (JobSourceError, SearchProviderError, asyncio.TimeoutError) as e:
            last_error = e
            if attempt < retries:
                stats.retry_count += 1
                await asyncio.sleep(base_delay * (2 ** attempt))
    stats.errors.append(f"{label}: {last_error}")
    return []


async def search_jobs(
    query: str,
    provider: SearchProvider,
    *,
    max_search_queries: int = 4,
    max_results_per_source: int = 5,
    max_total_results: int = 30,
    max_concurrent_searches: int = 5,
    search_timeout: float = 15.0,
    retries: int = 1,
    timelimit: str | None = "m",
    platforms: list[str] | None = None,
    target_location: str | None = None,
    required_skills: list[str] | None = None,
) -> tuple[list[JobPosting], JobSearchStats]:
    """
    Runs the full job search pipeline and returns (ranked_unique_jobs, stats).
    """
    start = time.monotonic()
    stats = JobSearchStats()

    expanded_queries = expand_query(query, max_queries=max_search_queries)
    stats.queries_used = expanded_queries

    platforms = platforms if platforms is not None else list(PLATFORM_DOMAINS.keys())
    semaphore = asyncio.Semaphore(max_concurrent_searches)

    all_jobs: list[JobPosting] = []

    async def _bounded(coro_factory, label: str):
        async with semaphore:
            try:
                return await asyncio.wait_for(
                    _with_retry(coro_factory, retries, 0.5, stats, label), timeout=search_timeout
                )
            except asyncio.TimeoutError:
                stats.errors.append(f"{label}: timed out after {search_timeout}s")
                return []

    tasks = []

    # Direct, no-auth sources (queried once with the original query - they
    # return broad feeds/APIs, not query-scoped search results).
    remoteok = RemoteOkSource()
    wwr = WeWorkRemotelySource()
    tasks.append(_bounded(lambda: remoteok.find_jobs(query, max_results_per_source), "remoteok"))
    tasks.append(_bounded(lambda: wwr.find_jobs(query, max_results_per_source), "weworkremotely"))
    stats.sources_searched.extend(["remoteok", "weworkremotely"])

    # Search-engine discovery for auth-walled platforms, once per expanded query.
    for platform in platforms:
        if platform not in PLATFORM_DOMAINS:
            continue
        stats.sources_searched.append(platform)
        for q in expanded_queries:
            async def _discover(p=platform, qq=q):
                jobs, discovery_stats = await discover_platform_jobs(
                    provider, p, qq, max_results_per_source, timelimit
                )
                if discovery_stats.error:
                    # Propagate as an exception so _with_retry can retry it
                    # and record it in stats.errors - discover_platform_jobs
                    # itself never raises (it's meant to be resilient at the
                    # caller's discretion), so we surface the failure here.
                    raise SearchProviderError(discovery_stats.error)
                return jobs
            tasks.append(_bounded(_discover, f"{platform}:{q}"))

    results_lists = await asyncio.gather(*tasks)
    for result_list in results_lists:
        all_jobs.extend(result_list)

    stats.total_results = len(all_jobs)

    unique_jobs = deduplicate_jobs(all_jobs)
    stats.unique_results = len(unique_jobs)
    stats.verified_recent_results = sum(1 for j in unique_jobs if j.date_verified)

    ranked = rank_jobs(unique_jobs, query=query, required_skills=required_skills, target_location=target_location)
    ranked = ranked[:max_total_results]

    stats.search_duration_seconds = round(time.monotonic() - start, 3)
    return ranked, stats
