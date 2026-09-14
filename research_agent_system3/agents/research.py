"""
Research Agent.

For general research: uses the `search_web` MCP tool (recency-filtered).
For job search: uses the `search_jobs` MCP tool, which internally does
query expansion, multi-source parallel search, deduplication, and
ranking (see jobs/aggregator.py). Job search results are stored in
state["jobs"] AND mirrored into state["research_results"] (title/href/
body) so the existing extraction agent can still fetch full pages for
those jobs without any special-casing.
"""
from config import AGENT_LIMITS, MAX_SEARCH_RESULTS, SEARCH_TIME_LIMIT
from state import ResearchState
from agents.base import bump
from agents.mcp_utils import parse_mcp_result


def make_research_agent(search_tool, search_jobs_tool=None):
    async def research_agent(state: ResearchState):
        attempt = state["agent_calls"].get("research", 0) + 1
        print(f"\nRESEARCH AGENT (attempt {attempt}/{AGENT_LIMITS['research']})")

        if state["query_type"] == "job_search" and search_jobs_tool is not None:
            return await _run_job_search(state, search_jobs_tool)
        return await _run_general_search(state, search_tool)

    return research_agent


async def _run_general_search(state: ResearchState, search_tool):
    raw_results = await search_tool.ainvoke(
        {
            "query": state["query"],
            "max_results": MAX_SEARCH_RESULTS,
            "timelimit": SEARCH_TIME_LIMIT or None,
        }
    )
    results = parse_mcp_result(raw_results)

    # Accumulate rather than replace - a later research call (e.g. after
    # a reviewer request for more depth) adds to what we already have.
    combined = state["research_results"] + (
        results if isinstance(results, list) else [results]
    )

    return {
        "research_results": combined,
        **bump(state, "research"),
    }


async def _run_job_search(state: ResearchState, search_jobs_tool):
    filters = state.get("job_filters") or {}

    raw_result = await search_jobs_tool.ainvoke(
        {
            "query": state["query"],
            "max_results": filters.get("max_results", 20),
            "timelimit": filters.get("timelimit", "m"),
            "platforms": filters.get("platforms"),
            "target_location": filters.get("location"),
            "required_skills": filters.get("skills"),
        }
    )
    result = parse_mcp_result(raw_result)

    new_jobs = result.get("jobs", [])
    stats = result.get("stats", {})

    print(
        f"   -> job search: {stats.get('total_results', 0)} raw, "
        f"{stats.get('unique_results', 0)} unique, "
        f"{stats.get('verified_recent_results', 0)} with a verified date"
    )

    # Mirror job URLs into research_results so the extraction agent's
    # existing fetch-and-enrich logic works unchanged for job pages too.
    mirrored_results = [
        {"title": j.get("title", ""), "href": j.get("url", ""), "body": j.get("description") or ""}
        for j in new_jobs
        if j.get("url")
    ]

    return {
        "jobs": state["jobs"] + new_jobs,
        "research_results": state["research_results"] + mirrored_results,
        "job_search_stats": stats,
        **bump(state, "research"),
    }
