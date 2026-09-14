"""Shared helpers used by every agent."""
from state import ResearchState


def bump(state: ResearchState, agent_name: str) -> dict:
    """Common bookkeeping every agent must return: attempt counter and history."""
    calls = dict(state["agent_calls"])
    calls[agent_name] = calls.get(agent_name, 0) + 1
    return {
        "step_count": state["step_count"] + 1,
        "agent_calls": calls,
        "execution_history": state["execution_history"] + [agent_name],
    }
