"""
Full-graph test for the GENERAL RESEARCH path (query_type=general_research),
using mock LLMs/tools (no Ollama/MCP needed). Confirms the original limit
and ordering guarantees still hold after the job-search extension.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from config import AGENT_LIMITS
from state import make_initial_state, ResearchState
from supervisor.decision import SupervisorDecision
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
        if "Analysis Agent" in prompt:
            return FakeMsg("Fake analysis output.")
        if "Summary Agent" in prompt:
            return FakeMsg("Fake final summary.")
        return FakeMsg("Generic response")


class ChaoticSupervisorLLM:
    """Always tries to jump straight to summary - the deterministic
    safety net must correct this every time."""
    async def ainvoke(self, prompt):
        return SupervisorDecision(next_agent="summary", reason="Trying to finish quickly!")


class FlakyReviewLLM:
    async def ainvoke(self, prompt):
        return ReviewResult(decision="NEEDS_MORE", reason="Still missing something", missing_information=["x"])


class FakeSearchTool:
    calls = 0

    async def ainvoke(self, args):
        FakeSearchTool.calls += 1
        assert "timelimit" in args, "research_agent must pass timelimit to the tool"
        return [{"title": f"Result {FakeSearchTool.calls}", "href": f"https://example.com/{FakeSearchTool.calls}", "body": "data"}]


class FakeFetchTool:
    async def ainvoke(self, args):
        return {"url": args["url"], "title": "Fake page", "text": "Sufficient fake page content.",
                "html": "<html></html>", "truncated": False, "error": None}


def build_test_graph():
    builder = StateGraph(ResearchState)

    builder.add_node("supervisor", make_supervisor_node(ChaoticSupervisorLLM()))
    builder.add_node("research", make_research_agent(FakeSearchTool()))
    builder.add_node("extraction", make_extraction_agent(FakeFetchTool()))
    builder.add_node("analysis", make_analysis_agent(FakeLLM()))
    builder.add_node("reviewer", make_reviewer_agent(FlakyReviewLLM()))
    builder.add_node("summary", make_summary_agent(FakeLLM()))

    builder.add_edge(START, "supervisor")
    builder.add_conditional_edges(
        "supervisor",
        supervisor_router,
        {
            "research": "research", "extraction": "extraction", "analysis": "analysis",
            "reviewer": "reviewer", "summary": "summary", "finish": END,
        },
    )
    for agent_name in ["research", "extraction", "analysis", "reviewer", "summary"]:
        builder.add_edge(agent_name, "supervisor")

    return builder.compile(checkpointer=MemorySaver())


async def main():
    graph = build_test_graph()
    state = make_initial_state("Test query after refactor", query_type="general_research")
    conf = {"configurable": {"thread_id": "refactor-test-1"}, "recursion_limit": 50}

    async for update in graph.astream(state, config=conf, stream_mode="updates"):
        for node in update:
            print("NODE:", node)

    full_state = graph.get_state(conf).values
    hist = full_state["execution_history"]
    print("\nexecution_history:", hist)
    print("agent_calls:", full_state["agent_calls"])

    first_summary_idx = hist.index("summary")
    assert "reviewer" in hist[:first_summary_idx]
    assert "analysis" in hist[:first_summary_idx]

    for agent, limit in AGENT_LIMITS.items():
        calls = full_state["agent_calls"].get(agent, 0)
        assert calls <= limit, f"{agent} exceeded its limit! {calls} > {limit}"

    # General research must still extract exactly once - the job-search
    # re-extraction extension must not affect this path.
    assert full_state["agent_calls"]["extraction"] == 1, "general research must extract exactly once"

    assert full_state["summary"]
    assert all(d["source"] == "fetch_url" for d in full_state["documents"])

    print("\n✅ All tests passed (limit logic + timelimit passthrough + general-research isolation)")


asyncio.run(main())
