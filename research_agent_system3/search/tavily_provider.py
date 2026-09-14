"""
Tavily search provider. Requires TAVILY_API_KEY (https://tavily.com).

Implemented against Tavily's documented REST API (POST /search). This
could not be live-verified in the development sandbox (no API key, no
network access to api.tavily.com) - the request/response handling is
covered by a mocked unit test instead. Verify against a real key before
relying on it in production.
"""
import httpx

from search.base import SearchProvider, SearchResult, SearchProviderError

TAVILY_ENDPOINT = "https://api.tavily.com/search"

_TIMELIMIT_TO_DAYS = {"d": 1, "w": 7, "m": 30, "y": 365}


class TavilyProvider(SearchProvider):
    name = "tavily"

    def __init__(self, api_key: str | None, timeout: float = 10.0):
        self.api_key = api_key
        self.timeout = timeout

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def search(
        self, query: str, max_results: int = 5, timelimit: str | None = None
    ) -> list[SearchResult]:
        if not self.is_configured():
            raise SearchProviderError("Tavily provider requires TAVILY_API_KEY")

        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
        }
        days = _TIMELIMIT_TO_DAYS.get(timelimit or "")
        if days:
            payload["days"] = days

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(TAVILY_ENDPOINT, json=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as e:
            raise SearchProviderError(f"Tavily search failed: {e}") from e

        results = data.get("results", [])
        return [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                snippet=r.get("content", ""),
                published_date=r.get("published_date"),
                source_provider=self.name,
                raw=r,
            )
            for r in results
        ]
