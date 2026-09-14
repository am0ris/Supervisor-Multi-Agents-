"""
Unit tests for the search provider abstraction: fallback chain behavior,
provider selection from config, and (mocked) request/response handling
for the API-key-based providers.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from search.base import SearchProvider, SearchResult, SearchProviderError
from search.factory import build_provider_chain, ProviderChain
from search.tavily_provider import TavilyProvider
from search.serpapi_provider import SerpApiProvider
from search.brave_provider import BraveProvider


class AlwaysFailsProvider(SearchProvider):
    name = "always_fails"

    async def search(self, query, max_results=5, timelimit=None):
        raise SearchProviderError("simulated failure")


class AlwaysSucceedsProvider(SearchProvider):
    name = "always_succeeds"

    async def search(self, query, max_results=5, timelimit=None):
        return [SearchResult(title="ok", url="https://example.com", snippet="fine", source_provider=self.name)]


async def test_fallback_on_failure():
    chain = ProviderChain([AlwaysFailsProvider(), AlwaysSucceedsProvider()])
    results, used, failures = await chain.search("test query")
    assert used == "always_succeeds"
    assert failures == ["always_fails"]
    assert len(results) == 1
    print("PASS: test_fallback_on_failure")


async def test_all_providers_fail_raises():
    chain = ProviderChain([AlwaysFailsProvider(), AlwaysFailsProvider()])
    try:
        await chain.search("test query")
        assert False, "expected SearchProviderError"
    except SearchProviderError:
        pass
    print("PASS: test_all_providers_fail_raises")


def test_unconfigured_provider_falls_back_to_duckduckgo():
    # No API keys provided -> Tavily/SerpAPI/Brave are all unconfigured,
    # so the chain must still guarantee DuckDuckGo is available.
    chain = build_provider_chain(
        primary="tavily", fallback_csv="serpapi,brave", env={}
    )
    names = [p.name for p in chain.providers]
    assert "duckduckgo" in names, f"expected duckduckgo fallback, got {names}"
    print("PASS: test_unconfigured_provider_falls_back_to_duckduckgo (providers:", names, ")")


def test_configured_provider_chain_order():
    chain = build_provider_chain(
        primary="tavily",
        fallback_csv="duckduckgo",
        env={"TAVILY_API_KEY": "fake-key-123"},
    )
    names = [p.name for p in chain.providers]
    assert names == ["tavily", "duckduckgo"], names
    print("PASS: test_configured_provider_chain_order (order:", names, ")")


class _FakeAsyncClient:
    """Mocks httpx.AsyncClient for provider request/response tests."""

    def __init__(self, response_json, expected_method=None):
        self._response_json = response_json
        self.captured_calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, json=None):
        self.captured_calls.append(("POST", url, json))
        return _FakeResponse(self._response_json)

    async def get(self, url, params=None, headers=None):
        self.captured_calls.append(("GET", url, params, headers))
        return _FakeResponse(self._response_json)


class _FakeResponse:
    def __init__(self, json_data):
        self._json = json_data

    def raise_for_status(self):
        pass

    def json(self):
        return self._json


async def test_tavily_response_parsing():
    import search.tavily_provider as mod

    fake_response = {
        "results": [
            {"title": "AI Engineer Job", "url": "https://x.com/1", "content": "snippet", "published_date": "2026-09-01"}
        ]
    }
    fake_client = _FakeAsyncClient(fake_response)
    mod.httpx.AsyncClient = lambda timeout=None: fake_client

    provider = mod.TavilyProvider(api_key="fake-key")
    results = await provider.search("AI Engineer jobs", max_results=5, timelimit="w")

    assert len(results) == 1
    assert results[0].title == "AI Engineer Job"
    assert results[0].published_date == "2026-09-01"
    # verify "days" recency param was translated correctly for timelimit="w"
    method, url, payload = fake_client.captured_calls[0]
    assert payload["days"] == 7
    print("PASS: test_tavily_response_parsing")


async def test_serpapi_response_parsing():
    import search.serpapi_provider as mod

    fake_response = {
        "organic_results": [
            {"title": "LLM Engineer", "link": "https://x.com/2", "snippet": "snippet", "date": "2 days ago"}
        ]
    }
    fake_client = _FakeAsyncClient(fake_response)
    mod.httpx.AsyncClient = lambda timeout=None: fake_client

    provider = mod.SerpApiProvider(api_key="fake-key")
    results = await provider.search("LLM Engineer jobs", max_results=5, timelimit="w")

    assert len(results) == 1
    assert results[0].title == "LLM Engineer"
    method, url, params, headers = fake_client.captured_calls[0]
    assert params["tbs"] == "qdr:w"
    print("PASS: test_serpapi_response_parsing")


async def test_brave_response_parsing():
    import search.brave_provider as mod

    fake_response = {
        "web": {"results": [{"title": "NLP Engineer", "url": "https://x.com/3", "description": "snippet", "age": "3 days ago"}]}
    }
    fake_client = _FakeAsyncClient(fake_response)
    mod.httpx.AsyncClient = lambda timeout=None: fake_client

    provider = mod.BraveProvider(api_key="fake-key")
    results = await provider.search("NLP Engineer jobs", max_results=5, timelimit="w")

    assert len(results) == 1
    assert results[0].title == "NLP Engineer"
    method, url, params, headers = fake_client.captured_calls[0]
    assert params["freshness"] == "pw"
    assert headers["X-Subscription-Token"] == "fake-key"
    print("PASS: test_brave_response_parsing")


def test_unconfigured_provider_raises_clear_error():
    provider = TavilyProvider(api_key=None)
    assert not provider.is_configured()
    print("PASS: test_unconfigured_provider_raises_clear_error")


async def main():
    test_unconfigured_provider_falls_back_to_duckduckgo()
    test_configured_provider_chain_order()
    test_unconfigured_provider_raises_clear_error()
    await test_fallback_on_failure()
    await test_all_providers_fail_raises()
    await test_tavily_response_parsing()
    await test_serpapi_response_parsing()
    await test_brave_response_parsing()
    print("\n✅ All search provider tests passed")


asyncio.run(main())
