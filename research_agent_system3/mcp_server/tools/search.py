"""Tool: search_web — general-purpose web search, provider-agnostic.

Backed by the search provider abstraction (search/), so the actual
backend (DuckDuckGo, Tavily, SerpAPI, Brave) is configurable via
environment variables and never hard-coded here.
"""
import os

from search.factory import build_provider_chain
from search.base import SearchProviderError

_PROVIDER_CHAIN = build_provider_chain(
    primary=os.getenv("SEARCH_PROVIDER", "duckduckgo"),
    fallback_csv=os.getenv("SEARCH_PROVIDER_FALLBACK", "duckduckgo"),
    env=os.environ,
)


async def search_web(query: str, max_results: int = 5, timelimit: str = "y") -> list[dict]:
    """
    Searches the web for a query and returns the top results.

    Args:
        query: search text.
        max_results: max number of results (default 5).
        timelimit: recency filter - "d" (day) / "w" (week) / "m" (month) /
            "y" (year) / "" (no filter). Default "y" so "latest
            developments"-style queries don't surface old, heavily-linked
            pages instead of recent ones.

    Returns:
        list[dict]: each item has title, href, body, published_date,
        provider (which backend actually served this result).
    """
    try:
        results, provider_used, failed_providers = await _PROVIDER_CHAIN.search(
            query, max_results=max_results, timelimit=timelimit or None
        )
    except SearchProviderError as e:
        return [{"title": "Search error", "href": "", "body": f"Search failed: {e}"}]

    return [
        {
            "title": r.title,
            "href": r.url,
            "body": r.snippet,
            "published_date": r.published_date,
            "provider": provider_used,
        }
        for r in results
    ] or [{"title": "No results", "href": "", "body": "No results found."}]
