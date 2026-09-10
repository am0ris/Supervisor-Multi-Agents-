"""
اختبار الـ graph بالكامل بموديلات وهمية (بدون Ollama/MCP حقيقيين)
عشان نتأكد إن إعادة تنظيم الملفات (refactor) ملخبطتش أي منطق.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from config import AGENT_LIMITS
from state import make_initial_state, ResearchState
from supervisor.decision import SupervisorDecision, build_supervisor_prompt, enforce_limits
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
            return FakeMsg("تحليل تجريبي.")
        if "Summary Agent" in prompt:
            return FakeMsg("ملخص نهائي تجريبي.")
        return FakeMsg("رد عام")


class ChaoticSupervisorLLM:
    async def ainvoke(self, prompt):
        return SupervisorDecision(next_agent="summary", reason="عايز أخلص بسرعة!")


class FlakyReviewLLM:
    async def ainvoke(self, prompt):
        return ReviewResult(decision="NEEDS_MORE", reason="لسه ناقص", missing_information=["x"])


class FakeSearchTool:
    calls = 0

    async def ainvoke(self, args):
        FakeSearchTool.calls += 1
        return [{"title": f"Result {FakeSearchTool.calls}", "href": f"https://example.com/{FakeSearchTool.calls}", "body": "بيانات"}]


class FakeFetchTool:
    async def ainvoke(self, args):
        return {"url": args["url"], "title": "Fake page", "text": "محتوى صفحة تجريبي كافي.", "truncated": False, "error": None}


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
    state = make_initial_state("سؤال اختباري بعد إعادة الهيكلة")
    conf = {"configurable": {"thread_id": "refactor-test-1"}, "recursion_limit": 50}

    async for update in graph.astream(state, config=conf, stream_mode="updates"):
        for node in update:
            print("NODE:", node)

    full_state = graph.get_state(conf).values
    hist = full_state["execution_history"]
    print("\nexecution_history:", hist)
    print("agent_calls:", full_state["agent_calls"])

    first_summary_idx = hist.index("summary")
    assert "reviewer" in hist[:first_summary_idx], "summary حصل قبل أي reviewer!"
    assert "analysis" in hist[:first_summary_idx], "summary حصل قبل أي analysis!"

    for agent, limit in AGENT_LIMITS.items():
        calls = full_state["agent_calls"].get(agent, 0)
        assert calls <= limit, f"{agent} تخطى الحد! {calls} > {limit}"

    assert full_state["summary"]
    # تأكيد إن extraction فعلا استخدم fetch_tool (مش snippet fallback)
    assert all(d["source"] == "fetch_url" for d in full_state["documents"])

    print("\n✅ كل الاختبارات نجحت بعد إعادة الهيكلة (refactor) + إضافة fetch_url")


asyncio.run(main())
