"""
Search provider abstraction.

Defines the common interface every search backend implements, so the
rest of the system (research agent, job search) never depends on a
specific provider (DuckDuckGo, Tavily, SerpAPI, Brave). Providers are
selected via config (SEARCH_PROVIDER / SEARCH_PROVIDER_FALLBACK) and can
be swapped or chained without touching agent code.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class SearchResult:
    """A single normalized search result, regardless of which provider produced it."""

    title: str
    url: str
    snippet: str
    published_date: str | None = None  # raw date string from the provider, if any
    source_provider: str = "unknown"
    raw: dict = field(default_factory=dict)  # original provider payload, for debugging


class SearchProviderError(Exception):
    """Raised when a provider fails (network error, bad API key, rate limit, etc.)."""


class SearchProvider(ABC):
    """Common interface for all search backends."""

    name: str = "base"

    @abstractmethod
    async def search(
        self, query: str, max_results: int = 5, timelimit: str | None = None
    ) -> list[SearchResult]:
        """
        Run a search and return normalized results.

        Args:
            query: search query text.
            max_results: max number of results to return.
            timelimit: recency filter - "d"/"w"/"m"/"y" or None. Providers
                that don't support this natively should approximate it or
                ignore it (never raise for an unsupported value).

        Raises:
            SearchProviderError: on any failure (network, auth, rate limit).
        """
        raise NotImplementedError

    def is_configured(self) -> bool:
        """Whether this provider has what it needs (API key, etc.) to run."""
        return True
