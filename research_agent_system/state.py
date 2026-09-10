"""حالة المشروع (Graph State)."""
from typing import TypedDict

from config import AGENT_LIMITS


class ResearchState(TypedDict):
    query: str

    research_results: list
    documents: list
    analysis: str
    review: dict
    summary: str

    best_analysis: str
    best_review: dict

    step_count: int
    agent_calls: dict
    execution_history: list

    next_agent: str
    supervisor_reason: str


def make_initial_state(query: str) -> ResearchState:
    return {
        "query": query,
        "research_results": [],
        "documents": [],
        "analysis": "",
        "review": {},
        "summary": "",
        "best_analysis": "",
        "best_review": {},
        "step_count": 0,
        "agent_calls": {k: 0 for k in AGENT_LIMITS},
        "execution_history": [],
        "next_agent": "",
        "supervisor_reason": "",
    }
