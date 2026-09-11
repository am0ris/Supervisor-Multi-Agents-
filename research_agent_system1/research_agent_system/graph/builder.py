"""بناء الـ LangGraph كامل: supervisor + كل الإيجنتس + edges صحيحة."""
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_ollama import ChatOllama
from langchain_mcp_adapters.client import MultiServerMCPClient

import config
from state import ResearchState
from supervisor.decision import (
    SupervisorDecision,
    build_supervisor_prompt,
    enforce_limits,
    compute_fallback_agent,
)
from agents.research import make_research_agent
from agents.extraction import make_extraction_agent
from agents.analysis import make_analysis_agent
from agents.reviewer import make_reviewer_agent, ReviewResult
from agents.summary import make_summary_agent


async def get_mcp_tools():
    client = MultiServerMCPClient(
        {
            "research_tools": {
                "transport": "streamable_http",
                "url": config.MCP_SERVER_URL,
            }
        }
    )
    tools = await client.get_tools()
    return {t.name: t for t in tools}


def make_supervisor_node(supervisor_llm):
    async def supervisor_node(state: ResearchState):
        if state["step_count"] >= config.MAX_TOTAL_STEPS:
            return {
                "next_agent": "finish",
                "supervisor_reason": "تم الوصول للحد الأقصى الكلي للخطوات.",
                "execution_history": state["execution_history"] + ["supervisor"],
            }

        prompt = build_supervisor_prompt(state)

        try:
            decision: SupervisorDecision = await supervisor_llm.ainvoke(prompt)
            raw_agent, raw_reason = decision.next_agent, decision.reason
        except Exception as e:
            raw_agent, raw_reason = compute_fallback_agent(state)
            raw_reason = f"{raw_reason} (فشل الـ LLM: {e})"

        final_agent, override_reason = enforce_limits(raw_agent, state)
        reason = override_reason or raw_reason

        print(f"\n🧭 SUPERVISOR -> {final_agent} | {reason}")

        return {
            "next_agent": final_agent,
            "supervisor_reason": reason,
            "execution_history": state["execution_history"] + ["supervisor"],
        }

    return supervisor_node


def supervisor_router(state: ResearchState):
    return state["next_agent"]


async def build_graph():
    llm = ChatOllama(model=config.OLLAMA_MODEL, base_url=config.OLLAMA_BASE_URL, temperature=0)
    supervisor_llm = llm.with_structured_output(SupervisorDecision)
    review_llm = llm.with_structured_output(ReviewResult)

    tools = await get_mcp_tools()
    search_tool = tools["search_web"]
    fetch_tool = tools["fetch_url"]

    builder = StateGraph(ResearchState)

    builder.add_node("supervisor", make_supervisor_node(supervisor_llm))
    builder.add_node("research", make_research_agent(search_tool))
    builder.add_node("extraction", make_extraction_agent(fetch_tool))
    builder.add_node("analysis", make_analysis_agent(llm))
    builder.add_node("reviewer", make_reviewer_agent(review_llm))
    builder.add_node("summary", make_summary_agent(llm))

    builder.add_edge(START, "supervisor")

    builder.add_conditional_edges(
        "supervisor",
        supervisor_router,
        {
            "research": "research",
            "extraction": "extraction",
            "analysis": "analysis",
            "reviewer": "reviewer",
            "summary": "summary",
            "finish": END,
        },
    )

    for agent_name in ["research", "extraction", "analysis", "reviewer", "summary"]:
        builder.add_edge(agent_name, "supervisor")

    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)
