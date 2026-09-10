"""Research Agent - بيستخدم أداة search_web (عن طريق MCP)."""
from config import AGENT_LIMITS, MAX_SEARCH_RESULTS
from state import ResearchState
from agents.base import bump


def make_research_agent(search_tool):
    async def research_agent(state: ResearchState):
        attempt = state["agent_calls"].get("research", 0) + 1
        print(f"\n🔎 RESEARCH AGENT (محاولة {attempt}/{AGENT_LIMITS['research']})")

        results = await search_tool.ainvoke(
            {"query": state["query"], "max_results": MAX_SEARCH_RESULTS}
        )

        # بيجمع النتائج بدل ما يستبدلها - لو اتنادى تاني بيضيف مصادر جديدة
        combined = state["research_results"] + (
            results if isinstance(results, list) else [results]
        )

        return {
            "research_results": combined,
            **bump(state, "research"),
        }

    return research_agent
