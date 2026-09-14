"""Summary Agent - writes the final answer from the best available analysis (and jobs, if any)."""
from datetime import date

from state import ResearchState
from agents.base import bump
from security.prompt_injection import wrap_untrusted


def make_summary_agent(llm):
    async def summary_agent(state: ResearchState):
        print("\nSUMMARY AGENT")

        analysis_used = state["best_analysis"] or state["analysis"]
        safe_analysis = wrap_untrusted(analysis_used, source_label="analysis output")

        job_block = ""
        if state["query_type"] == "job_search" and state["jobs"]:
            ranked = sorted(state["jobs"], key=lambda j: j.get("relevance_score") or 0, reverse=True)
            lines = []
            for j in ranked[:10]:
                date_note = j.get("posted_date") or "date unknown/unverified"
                lines.append(
                    f"- {j.get('title')} at {j.get('company') or 'Unknown company'} "
                    f"({j.get('location') or 'Location unknown'}, {j.get('remote_type') or 'n/a'}) "
                    f"- posted: {date_note} - source: {j.get('source')} - {j.get('url')}"
                )
            job_block = "\n\nRanked job listings:\n" + "\n".join(lines)

        prompt = f"""You are the Summary Agent.

Actual current date: {date.today().isoformat()}

Question: {state['query']}
Final available analysis: {safe_analysis}
Review outcome: {state['best_review'] or state['review']}
{job_block}

Write a clear, concise final answer.
Rely only on the analysis above (grounded in real retrieved data) - never add or "correct" a
fact using your own training knowledge, even if you believe it is more current.
If there are gaps in the information, state that transparently.
Do not invent information not present in the analysis or job listings above."""

        response = await llm.ainvoke(prompt)

        return {
            "summary": response.content,
            **bump(state, "summary"),
        }

    return summary_agent
