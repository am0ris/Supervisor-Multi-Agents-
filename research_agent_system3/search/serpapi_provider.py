"""
SerpAPI search provider (Google results via serpapi.com). Requires
SERPAPI_API_KEY.

Implemented against SerpAPI's documented REST API (GET /search). Not
live-verified in the development sandbox (no API key, no network access
to serpapi.com) - covered by a mocked unit test instead.
"""
import httpx

from search.base import SearchProvider, SearchResult, SearchProviderError

SERPAPI_ENDPOINT = "https://serpapi.com/search"

# SerpAPI's Google engine uses "tbs=qdr:<code>" for recency filtering.
_TIMELIMIT_TO_QDR = {"d": "d", "w": "w", "m": "m", "y": "y"}


class SerpApiProvider(SearchProvider):
    name = "serpapi"

    def __init__(self, api_key: str | None, timeout: float = 10.0):
        self.api_key = api_key
        self.timeout = timeout

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def search(
        self, query: str, max_results: int = 5, timelimit: str | None = None
    ) -> list[SearchResult]:
        if not self.is_configured():
            raise SearchProviderError("SerpAPI provider requires SERPAPI_API_KEY")

        params = {
            "engine": "google",
            "q": query,
            "num": max_results,
            "api_key": self.api_key,
        }
        qdr = _TIMELIMIT_TO_QDR.get(timelimit or "")
        if qdr:
            params["tbs"] = f"qdr:{qdr}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(SERPAPI_ENDPOINT, params=params)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as e:
            raise SearchProviderError(f"SerpAPI search failed: {e}") from e

        organic = data.get("organic_results", [])
        return [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("link", ""),
                snippet=r.get("snippet", ""),
                published_date=r.get("date"),
                source_provider=self.name,
                raw=r,
            )
            for r in organic[:max_results]
        ]
