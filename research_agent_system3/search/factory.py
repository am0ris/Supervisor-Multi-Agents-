"""
Factory for building a search provider chain from config.

SEARCH_PROVIDER picks the primary provider; SEARCH_PROVIDER_FALLBACK
(comma-separated) lists providers to try, in order, if the primary
fails or is not configured (missing API key). This means a misconfigured
paid provider degrades to DuckDuckGo instead of breaking the whole
research pipeline.
"""
import logging

from search.base import SearchProvider, SearchResult, SearchProviderError
from search.duckduckgo_provider import DuckDuckGoProvider
from search.tavily_provider import TavilyProvider
from search.serpapi_provider import SerpApiProvider
from search.brave_provider import BraveProvider

logger = logging.getLogger(__name__)


def _build_provider(name: str, env: dict) -> SearchProvider | None:
    name = (name or "").strip().lower()
    if name == "duckduckgo":
        return DuckDuckGoProvider()
    if name == "tavily":
        return TavilyProvider(api_key=env.get("TAVILY_API_KEY"))
    if name == "serpapi":
        return SerpApiProvider(api_key=env.get("SERPAPI_API_KEY"))
    if name == "brave":
        return BraveProvider(api_key=env.get("BRAVE_API_KEY"))
    return None


class ProviderChain:
    """
    Wraps an ordered list of providers. `search()` tries each provider in
    order and returns the first successful result set. A single provider
    failure never fails the whole search - it just moves to the next one.
    """

    def __init__(self, providers: list[SearchProvider]):
        configured = [p for p in providers if p.is_configured()]
        if not configured:
            # Always guarantee at least DuckDuckGo works, since it needs no key.
            configured = [DuckDuckGoProvider()]
        self.providers = configured

    async def search(
        self, query: str, max_results: int = 5, timelimit: str | None = None
    ) -> tuple[list[SearchResult], str, list[str]]:
        """
        Returns (results, provider_that_succeeded, list_of_providers_that_failed).
        Raises SearchProviderError only if EVERY provider in the chain fails.
        """
        failures = []
        for provider in self.providers:
            try:
                results = await provider.search(query, max_results, timelimit)
                return results, provider.name, failures
            except SearchProviderError as e:
                logger.warning("Search provider '%s' failed: %s", provider.name, e)
                failures.append(provider.name)
                continue
        raise SearchProviderError(
            f"All search providers failed for query: {query!r} (tried: {failures})"
        )


def build_provider_chain(
    primary: str, fallback_csv: str, env: dict
) -> ProviderChain:
    """
    Args:
        primary: value of SEARCH_PROVIDER, e.g. "duckduckgo".
        fallback_csv: value of SEARCH_PROVIDER_FALLBACK, e.g. "tavily,duckduckgo".
        env: dict-like source of API keys (os.environ or a subset).
    """
    names = [primary] + [n for n in (fallback_csv or "").split(",") if n.strip()]
    providers = []
    seen = set()
    for name in names:
        key = name.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        provider = _build_provider(key, env)
        if provider:
            providers.append(provider)
    return ProviderChain(providers)
