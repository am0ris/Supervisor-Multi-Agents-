"""
Integration test: exercises the REAL build_graph() wiring in job_search
mode against a REAL MCP server (search_jobs, fetch_url tools). Only the
ChatOllama LLM is mocked (no Ollama in this environment). Network access
to actual job platforms is blocked in this sandbox, so we verify graceful
degradation (the pipeline must still complete and produce a summary) -
this does NOT verify live job results; see README for that caveat.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import graph.builder as builder_module
from supervisor.decision import SupervisorDecision
from agents.reviewer import ReviewResult


class FakeMsg:
    def __init__(self, content):
        self.content = content


class FakeChatOllama:
    def __init__(self, *a, **kw):
        pass

    async def ainvoke(self, prompt):
        if "Analysis Agent" in prompt:
            return FakeMsg("[TEST] Job market analysis based on retrieved data.")
        if "Summary Agent" in prompt:
            return FakeMsg("[TEST] Final job search summary.")
        return FakeMsg("[TEST] generic response")

    def with_structured_output(self, model_cls):
        class _Wrapped:
            async def ainvoke(self, prompt):
                if model_cls.__name__ == "ReviewResult":
                    return model_cls(decision="APPROVED", reason="[TEST] accepting whatever we found",
                                      missing_information=[], needs_more_search=False)
                if model_cls.__name__ == "SupervisorDecision":
                    return model_cls(next_agent="finish", reason="[TEST]")
                # JobPosting structured extraction fallback - just fail gracefully
                raise ValueError("not used in this test")
        return _Wrapped()


async def main():
    builder_module.ChatOllama = FakeChatOllama
    graph = await builder_module.build_graph()

    from state import make_initial_state
    state = make_initial_state(
        "Find recent Generative AI Engineer jobs in Egypt",
        query_type="job_search",
        job_filters={"max_results": 10, "timelimit": "m", "platforms": ["linkedin"]},
    )
    conf = {"configurable": {"thread_id": "job-integration-1"}, "recursion_limit": 50}

    async for update in graph.astream(state, config=conf, stream_mode="updates"):
        for node in update:
            print("NODE:", node)

    final = graph.get_state(conf).values
    print("\nexecution_history:", final["execution_history"])
    print("agent_calls:", final["agent_calls"])
    print("jobs found:", len(final["jobs"]))
    print("job_search_stats:", final["job_search_stats"])

    assert final["summary"], "must produce a final summary even with zero live results in this sandbox"
    assert "research" in final["execution_history"]
    assert "extraction" in final["execution_history"]
    print("\n✅ build_graph() job_search wiring works end-to-end against a real MCP server")
    print("   (zero/near-zero live job results expected here - sandbox has no route to job platforms)")


asyncio.run(main())
