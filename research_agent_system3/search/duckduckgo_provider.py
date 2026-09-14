"""
DuckDuckGo search provider. No API key required. This is the default
provider since it works out of the box, though it is the least reliable
under load (no SLA, unofficial library) — use a paid provider for
production-grade reliability.
"""
import asyncio

from ddgs import DDGS

from search.base import SearchProvider, SearchResult, SearchProviderError


class DuckDuckGoProvider(SearchProvider):
    name = "duckduckgo"

    def is_configured(self) -> bool:
        return True  # no credentials needed

    async def search(
        self, query: str, max_results: int = 5, timelimit: str | None = None
    ) -> list[SearchResult]:
        def _run():
            with DDGS() as ddgs:
                results = list(
                    ddgs.text(query, max_results=max_results, timelimit=timelimit)
                )
            if not results and timelimit:
                # Recency filter returned nothing - retry without it rather
                # than reporting a hard failure.
                with DDGS() as ddgs:
                    results = list(ddgs.text(query, max_results=max_results))
            return results

        try:
            raw_results = await asyncio.to_thread(_run)
        except Exception as e:
            raise SearchProviderError(f"DuckDuckGo search failed: {e}") from e

        return [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("href", ""),
                snippet=r.get("body", ""),
                published_date=None,  # DDG text search does not return dates
                source_provider=self.name,
                raw=r,
            )
            for r in raw_results
        ]
