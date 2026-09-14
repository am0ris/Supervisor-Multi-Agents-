"""
Brave Search API provider. Requires BRAVE_API_KEY (https://brave.com/search/api/).

Implemented against Brave's documented REST API (GET /res/v1/web/search).
Not live-verified in the development sandbox (no API key, no network
access to api.search.brave.com) - covered by a mocked unit test instead.
"""
import httpx

from search.base import SearchProvider, SearchResult, SearchProviderError

BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"

# Brave's "freshness" param: pd (past day), pw (past week), pm (past month), py (past year)
_TIMELIMIT_TO_FRESHNESS = {"d": "pd", "w": "pw", "m": "pm", "y": "py"}


class BraveProvider(SearchProvider):
    name = "brave"

    def __init__(self, api_key: str | None, timeout: float = 10.0):
        self.api_key = api_key
        self.timeout = timeout

    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def search(
        self, query: str, max_results: int = 5, timelimit: str | None = None
    ) -> list[SearchResult]:
        if not self.is_configured():
            raise SearchProviderError("Brave provider requires BRAVE_API_KEY")

        params = {"q": query, "count": max_results}
        freshness = _TIMELIMIT_TO_FRESHNESS.get(timelimit or "")
        if freshness:
            params["freshness"] = freshness

        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(BRAVE_ENDPOINT, params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as e:
            raise SearchProviderError(f"Brave search failed: {e}") from e

        web_results = data.get("web", {}).get("results", [])
        return [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                snippet=r.get("description", ""),
                published_date=r.get("age") or r.get("page_age"),
                source_provider=self.name,
                raw=r,
            )
            for r in web_results[:max_results]
        ]
