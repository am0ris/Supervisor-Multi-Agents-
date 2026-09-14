"""
Tests the supervisor's job-search "search again" loop: it must eventually
terminate with a summary no matter how persistently the reviewer asks
for more searching, and it must never exceed any agent's hard limit.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from config import AGENT_LIMITS
from state import make_initial_state, ResearchState
from supervisor.decision import SupervisorDecision, is_eligible
from graph.builder import make_supervisor_node, supervisor_router
from agents.research import make_research_agent
from agents.extraction import make_extraction_agent
from agents.analysis import make_analysis_agent
from agents.reviewer import make_reviewer_agent, ReviewResult
from agents.summary import make_summary_agent


class FakeMsg:
    def __init__(self, content):
        self.content = content


class FakeLLM:
    async def ainvoke(self, prompt):
        return FakeMsg("Fake analysis or summary text.")

    def with_structured_output(self, model_cls):
        raise NotImplementedError  # not used directly by these fakes


class AlwaysDeferSupervisorLLM:
    """Always defers to whatever the supervisor's own fallback would pick -
    simulated by intentionally returning an invalid/ineligible choice so
    enforce_limits' deterministic fallback drives the whole run."""
    async def ainvoke(self, prompt):
        return SupervisorDecision(next_agent="finish", reason="trying to finish early")


class NeverSatisfiedReviewLLM:
    """Always asks for another search round - the worst case for the loop."""
    async def ainvoke(self, prompt):
        return ReviewResult(
            decision="NEEDS_MORE", reason="not enough jobs", missing_information=["more jobs"],
            needs_more_search=True,
        )


class FakeSearchJobsTool:
    call_count = 0

    async def ainvoke(self, args):
        FakeSearchJobsTool.call_count += 1
        n = FakeSearchJobsTool.call_count
        return {
            "jobs": [
                {
                    "title": "Generative AI Engineer", "company": "Acme", "url": f"https://linkedin.com/jobs/{n}",
                    "source": "linkedin", "date_confidence": "date_unknown", "date_verified": False,
                }
            ],
            "stats": {"total_results": 1, "unique_results": 1, "verified_recent_results": 0},
        }


class FakeFetchTool:
    async def ainvoke(self, args):
        return {"url": args["url"], "title": "Job", "text": "Some job text.", "html": "<html></html>", "error": None}


def build_test_graph():
    builder = StateGraph(ResearchState)

    builder.add_node("supervisor", make_supervisor_node(AlwaysDeferSupervisorLLM()))
    builder.add_node("research", make_research_agent(search_tool=None, search_jobs_tool=FakeSearchJobsTool()))
    builder.add_node("extraction", make_extraction_agent(FakeFetchTool(), llm=None))
    builder.add_node("analysis", make_analysis_agent(FakeLLM()))
    builder.add_node("reviewer", make_reviewer_agent(NeverSatisfiedReviewLLM()))
    builder.add_node("summary", make_summary_agent(FakeLLM()))

    builder.add_edge(START, "supervisor")
    builder.add_conditional_edges(
        "supervisor", supervisor_router,
        {"research": "research", "extraction": "extraction", "analysis": "analysis",
         "reviewer": "reviewer", "summary": "summary", "finish": END},
    )
    for agent_name in ["research", "extraction", "analysis", "reviewer", "summary"]:
        builder.add_edge(agent_name, "supervisor")

    return builder.compile(checkpointer=MemorySaver())


async def test_search_again_loop_always_terminates():
    graph = build_test_graph()
    state = make_initial_state("Find Generative AI Engineer jobs in Egypt", query_type="job_search")
    conf = {"configurable": {"thread_id": "job-loop-test"}, "recursion_limit": 100}

    step_count_seen = 0
    async for update in graph.astream(state, config=conf, stream_mode="updates"):
        step_count_seen += 1
        assert step_count_seen < 200, "graph did not terminate - possible infinite loop"

    full_state = graph.get_state(conf).values

    for agent, limit in AGENT_LIMITS.items():
        calls = full_state["agent_calls"].get(agent, 0)
        assert calls <= limit, f"{agent} exceeded its limit! {calls} > {limit}"

    assert full_state["summary"], "must always end with a summary, even when reviewer never approves"
    assert full_state["agent_calls"]["research"] > 1, "expected the search-again loop to trigger at least once"
    print(
        "PASS: test_search_again_loop_always_terminates "
        f"(research calls: {full_state['agent_calls']['research']}, "
        f"extraction calls: {full_state['agent_calls']['extraction']}, "
        f"total steps: {step_count_seen})"
    )


async def test_general_research_unaffected_by_job_search_changes():
    """Sanity check: a plain general_research state must still follow the
    original single-pass extraction rule (no re-extraction eligibility)."""
    state = make_initial_state("What is LangGraph?", query_type="general_research")
    state["agent_calls"] = {"research": 1, "extraction": 1, "analysis": 0, "reviewer": 0, "summary": 0}
    state["research_results"] = [{"title": "x", "href": "https://x.com", "body": "y"}]
    state["extracted_result_count"] = 0  # never updated by general extraction, as before

    # extraction must NOT be eligible again just because research_results > extracted_result_count,
    # since query_type is general_research, not job_search.
    assert not is_eligible("extraction", state), "general research must not re-trigger extraction"
    print("PASS: test_general_research_unaffected_by_job_search_changes")


async def main():
    await test_search_again_loop_always_terminates()
    await test_general_research_unaffected_by_job_search_changes()
    print("\n✅ All supervisor job-search routing tests passed")


asyncio.run(main())
