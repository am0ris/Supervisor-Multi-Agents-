"""
Supervisor: the LLM proposes a next agent, but every proposal is checked
against `is_eligible` before it runs. If it isn't allowed (violates a
limit or the pipeline's logical order), it's automatically corrected via
deterministic fallback logic (`compute_fallback_agent`). This is the
core safety net that keeps a small local model from ever breaking the
control flow or causing an infinite loop.

Job search extension: when the reviewer sets `needs_more_search=True`
(job results were too thin or unverified), the supervisor is allowed to
route back to `research` for another round - but only while there is
still budget for a full research -> extraction round-trip. This is what
prevents the "search again" capability from ever deadlocking or looping
forever; see `is_eligible` for the exact guard.
"""
from typing import Literal, Optional
from pydantic import BaseModel, Field

from config import AGENT_LIMITS
from state import ResearchState


class SupervisorDecision(BaseModel):
    next_agent: Literal[
        "research", "extraction", "analysis", "reviewer", "summary", "finish"
    ]
    reason: str = Field(description="Short justification for this decision")


def _remaining(state: ResearchState) -> dict:
    return {
        agent: AGENT_LIMITS[agent] - state["agent_calls"].get(agent, 0)
        for agent in AGENT_LIMITS
    }


def is_eligible(agent: str, state: ResearchState) -> bool:
    calls = state["agent_calls"]
    query_type = state.get("query_type", "general_research")

    def has_budget(a: str) -> bool:
        return calls.get(a, 0) < AGENT_LIMITS[a]

    if calls.get("summary", 0) >= 1:
        return agent == "finish"

    if agent == "finish":
        return bool(state["summary"]) or all(not has_budget(a) for a in AGENT_LIMITS)

    if agent == "research":
        if not has_budget("research"):
            return False
        if calls.get("extraction", 0) == 0:
            return True
        # "Search again": only for job search, only when the reviewer
        # explicitly asked for it, and only if there's still budget left
        # to extract whatever the new search finds (otherwise searching
        # again would be pointless - nothing could process the results).
        if query_type == "job_search" and state["review"].get("needs_more_search") and has_budget("extraction"):
            return True
        return False

    if agent == "extraction":
        if not has_budget("extraction") or calls.get("research", 0) == 0:
            return False
        if calls.get("extraction", 0) == 0:
            return True  # first extraction pass, always eligible once we have search results
        # Re-run extraction only when there is genuinely new, not-yet-extracted
        # data (a "search again" round) - never just because budget remains.
        if query_type == "job_search" and len(state["research_results"]) > state.get("extracted_result_count", 0):
            return True
        return False

    if agent == "analysis":
        return has_budget("analysis") and calls.get("extraction", 0) >= 1

    if agent == "reviewer":
        return has_budget("reviewer") and calls.get("analysis", 0) >= 1

    if agent == "summary":
        review_decision = state["review"].get("decision")
        loop_still_open = has_budget("analysis") and has_budget("reviewer")
        search_again_open = (
            query_type == "job_search"
            and bool(state["review"].get("needs_more_search"))
            and is_eligible("research", state)
        )
        return (
            has_budget("summary")
            and calls.get("analysis", 0) >= 1
            and calls.get("reviewer", 0) >= 1
            and (review_decision == "APPROVED" or not (loop_still_open or search_again_open))
        )

    return False


def compute_fallback_agent(state: ResearchState) -> tuple[str, str]:
    calls = state["agent_calls"]
    query_type = state.get("query_type", "general_research")

    if calls.get("research", 0) == 0:
        return "research", "Need search results before anything else."

    # Always drain any pending extraction work before considering another
    # search round - this covers both the first extraction pass AND
    # re-extracting newly added results after a "search again" round.
    if is_eligible("extraction", state):
        return "extraction", "There are search results that still need extracting."

    if calls.get("analysis", 0) == 0:
        return "analysis", "We have documents; time for the first analysis pass."
    if calls.get("summary", 0) >= 1:
        return "finish", "The final summary has already been produced."

    if calls.get("reviewer", 0) < calls.get("analysis", 0) and is_eligible("reviewer", state):
        return "reviewer", "There's a new analysis pass that needs review."

    review = state["review"]
    if query_type == "job_search" and review.get("needs_more_search") and is_eligible("research", state):
        return "research", "The reviewer requested another search round for better job coverage."

    if (
        review.get("decision") == "NEEDS_MORE"
        and is_eligible("analysis", state)
        and AGENT_LIMITS["reviewer"] - calls.get("reviewer", 0) > 0
    ):
        return "analysis", "The reviewer requested an improved analysis and attempts remain."

    if is_eligible("summary", state):
        return "summary", "Analysis and review are ready; time for the final summary."

    return "finish", "All available budget has been used, or every stage is complete."


def build_supervisor_prompt(state: ResearchState) -> str:
    from datetime import date

    remaining = _remaining(state)
    eligible_now = [a for a in list(AGENT_LIMITS) + ["finish"] if is_eligible(a, state)]

    job_block = ""
    if state["query_type"] == "job_search":
        job_block = f"""
This is a JOB SEARCH request.
Jobs found so far: {len(state['jobs'])}
Verified-date jobs so far: {sum(1 for j in state['jobs'] if j.get('date_verified'))}
If the reviewer flagged needs_more_search=true and "research" is in the allowed options below,
prefer going back to research to broaden/refine the search rather than proceeding with thin data.
"""

    return f"""You are the Supervisor Agent, coordinating a team of agents to answer a research request as well as possible.

Actual current date: {date.today().isoformat()}
Request: {state['query']}
{job_block}
Executed so far: {state['execution_history'] or 'nothing yet'}
Number of search results: {len(state['research_results'])}
Number of documents: {len(state['documents'])}
Current analysis exists: {'yes' if state['analysis'] else 'no'}
Latest review outcome: {state['review'] or 'none yet'}
Final summary exists: {'yes' if state['summary'] else 'no'}

Remaining budget per agent: {remaining}
Actually allowed options right now: {eligible_now}

Choose exactly one of the "allowed options" and give a brief reason.
If the reviewer requested NEEDS_MORE and analysis/reviewer attempts remain, prefer going back to analysis.
If there's no need for further improvement, proceed normally to the next stage.
"""


def enforce_limits(raw_agent: str, state: ResearchState) -> tuple[str, Optional[str]]:
    if is_eligible(raw_agent, state):
        return raw_agent, None

    fallback_agent, fallback_reason = compute_fallback_agent(state)
    override_reason = (
        f"Overrode the supervisor's decision ('{raw_agent}' is not currently allowed) "
        f"in favor of '{fallback_agent}': {fallback_reason}"
    )
    return fallback_agent, override_reason
