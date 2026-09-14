"""Graph state shared across all agents."""
from typing import TypedDict, Optional

from config import AGENT_LIMITS


class ResearchState(TypedDict):
    query: str
    query_type: str  # "job_search" | "general_research"

    # optional structured filters for job search (from the UI or caller)
    job_filters: dict

    research_results: list
    documents: list
    analysis: str
    review: dict
    summary: str

    # job-search specific
    jobs: list            # list of JobPosting dicts (see jobs/schema.py)
    job_search_stats: dict
    extracted_result_count: int  # how many research_results have been through extraction so far

    best_analysis: str
    best_review: dict

    step_count: int
    agent_calls: dict
    execution_history: list

    next_agent: str
    supervisor_reason: str


def make_initial_state(query: str, query_type: str = "general_research", job_filters: Optional[dict] = None) -> ResearchState:
    return {
        "query": query,
        "query_type": query_type,
        "job_filters": job_filters or {},
        "research_results": [],
        "documents": [],
        "analysis": "",
        "review": {},
        "summary": "",
        "jobs": [],
        "job_search_stats": {},
        "extracted_result_count": 0,
        "best_analysis": "",
        "best_review": {},
        "step_count": 0,
        "agent_calls": {k: 0 for k in AGENT_LIMITS},
        "execution_history": [],
        "next_agent": "",
        "supervisor_reason": "",
    }
