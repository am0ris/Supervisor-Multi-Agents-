import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import jobs.aggregator as agg_mod
from jobs.aggregator import search_jobs
from jobs.schema import JobPosting
from jobs.sources.base import JobSourceError
from search.base import SearchProvider, SearchResult, SearchProviderError


class FakeProvider(SearchProvider):
    name = "fake"

    def __init__(self, behavior="ok"):
        self.behavior = behavior
        self.call_count = 0

    async def search(self, query, max_results=5, timelimit=None):
        self.call_count += 1
        if self.behavior == "always_fail":
            raise SearchProviderError("simulated provider failure")
        if self.behavior == "slow":
            await asyncio.sleep(5)
            return []
        return [
            SearchResult(title=f"Generative AI Engineer at Acme ({query})", url=f"https://linkedin.com/jobs/{self.call_count}",
                         snippet="Great job", source_provider=self.name)
        ]


class FailingRemoteOk:
    async def find_jobs(self, query, max_results=10, **kwargs):
        raise JobSourceError("RemoteOK is down")


class WorkingRemoteOk:
    async def find_jobs(self, query, max_results=10, **kwargs):
        return [JobPosting(title="Remote AI Engineer", company="RemoteCo", url="https://remoteok.com/1", source="remoteok")]


async def test_basic_search_returns_ranked_unique_jobs():
    provider = FakeProvider("ok")
    jobs, stats = await search_jobs(
        "Generative AI Engineer jobs in Egypt",
        provider,
        max_search_queries=2,
        max_results_per_source=2,
        platforms=["linkedin"],
    )
    assert stats.total_results > 0
    assert stats.unique_results <= stats.total_results
    assert len(jobs) == stats.unique_results
    assert "remoteok" in stats.sources_searched
    assert "linkedin" in stats.sources_searched
    print("PASS: test_basic_search_returns_ranked_unique_jobs")


async def test_one_failing_source_does_not_break_whole_search():
    provider = FakeProvider("ok")
    # monkeypatch RemoteOK to fail - the rest of the pipeline must still work
    agg_mod.RemoteOkSource = lambda: FailingRemoteOk()
    jobs, stats = await search_jobs(
        "AI Engineer",
        provider,
        max_search_queries=1,
        platforms=["linkedin"],
        retries=0,
    )
    assert any("remoteok" in e for e in stats.errors), stats.errors
    assert stats.total_results > 0, "linkedin discovery results must still come through"
    print("PASS: test_one_failing_source_does_not_break_whole_search")
    agg_mod.RemoteOkSource = _ORIGINAL_REMOTEOK  # restore


async def test_all_providers_failing_yields_empty_but_no_crash():
    provider = FakeProvider("always_fail")
    agg_mod.RemoteOkSource = lambda: FailingRemoteOk()
    jobs, stats = await search_jobs("AI Engineer", provider, max_search_queries=1, platforms=["linkedin"], retries=0)
    assert jobs == []
    assert stats.total_results == 0
    assert len(stats.errors) > 0
    print("PASS: test_all_providers_failing_yields_empty_but_no_crash")
    agg_mod.RemoteOkSource = _ORIGINAL_REMOTEOK


async def test_retry_on_failure_then_succeed():
    class FlakyThenOk(SearchProvider):
        name = "flaky"
        def __init__(self):
            self.calls = 0
        async def search(self, query, max_results=5, timelimit=None):
            self.calls += 1
            if self.calls == 1:
                raise SearchProviderError("transient failure")
            return [SearchResult(title="AI Engineer", url="https://linkedin.com/jobs/1", snippet="x", source_provider=self.name)]

    provider = FlakyThenOk()
    agg_mod.RemoteOkSource = lambda: FailingRemoteOk()  # isolate to just discovery
    jobs, stats = await search_jobs("AI Engineer", provider, max_search_queries=1, platforms=["linkedin"], retries=1)
    assert stats.retry_count >= 1, "expected at least one retry to be recorded"
    assert stats.total_results > 0, "should succeed after retry"
    print("PASS: test_retry_on_failure_then_succeed")
    agg_mod.RemoteOkSource = _ORIGINAL_REMOTEOK


async def test_timeout_is_enforced_and_does_not_hang_whole_search():
    provider = FakeProvider("slow")  # sleeps 5s, way beyond our tiny timeout
    agg_mod.RemoteOkSource = lambda: WorkingRemoteOk()
    agg_mod.WeWorkRemotelySource = lambda: FailingRemoteOk()  # keep it simple/fast

    jobs, stats = await search_jobs(
        "AI Engineer", provider, max_search_queries=1, platforms=["linkedin"],
        search_timeout=0.2, retries=0,
    )
    assert any("timed out" in e for e in stats.errors), stats.errors
    # RemoteOK (fast, working) results must still be present despite the slow provider
    assert any(j.source == "remoteok" for j in jobs)
    print("PASS: test_timeout_is_enforced_and_does_not_hang_whole_search")
    agg_mod.RemoteOkSource = _ORIGINAL_REMOTEOK
    agg_mod.WeWorkRemotelySource = _ORIGINAL_WWR


async def test_query_expansion_bounds_number_of_discovery_calls():
    provider = FakeProvider("ok")
    agg_mod.RemoteOkSource = lambda: FailingRemoteOk()
    jobs, stats = await search_jobs(
        "Generative AI Engineer jobs", provider,
        max_search_queries=2, platforms=["linkedin"], retries=0,
    )
    assert len(stats.queries_used) <= 2
    print("PASS: test_query_expansion_bounds_number_of_discovery_calls (queries:", stats.queries_used, ")")
    agg_mod.RemoteOkSource = _ORIGINAL_REMOTEOK


_ORIGINAL_REMOTEOK = agg_mod.RemoteOkSource
_ORIGINAL_WWR = agg_mod.WeWorkRemotelySource


async def main():
    await test_basic_search_returns_ranked_unique_jobs()
    await test_one_failing_source_does_not_break_whole_search()
    await test_all_providers_failing_yields_empty_but_no_crash()
    await test_retry_on_failure_then_succeed()
    await test_timeout_is_enforced_and_does_not_hang_whole_search()
    await test_query_expansion_bounds_number_of_discovery_calls()
    print("\n✅ All job aggregator resilience tests passed")


asyncio.run(main())
