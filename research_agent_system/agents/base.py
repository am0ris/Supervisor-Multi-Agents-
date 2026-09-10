"""حاجات مشتركة بين كل الإيجنتس."""
from state import ResearchState


def bump(state: ResearchState, agent_name: str) -> dict:
    """تحديثات مشتركة كل إيجنت لازم يرجعها: العداد + التاريخ."""
    calls = dict(state["agent_calls"])
    calls[agent_name] = calls.get(agent_name, 0) + 1
    return {
        "step_count": state["step_count"] + 1,
        "agent_calls": calls,
        "execution_history": state["execution_history"] + [agent_name],
    }
