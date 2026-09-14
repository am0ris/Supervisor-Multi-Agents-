"""Analysis Agent - synthesizes findings from documents (and jobs, if any)."""
from datetime import date

from config import AGENT_LIMITS, MAX_DOCUMENTS
from state import ResearchState
from agents.base import bump
from security.prompt_injection import wrap_untrusted


def make_analysis_agent(llm):
    async def analysis_agent(state: ResearchState):
        attempt = state["agent_calls"].get("analysis", 0) + 1
        print(f"\nANALYSIS AGENT (attempt {attempt}/{AGENT_LIMITS['analysis']})")

        context = "\n\n".join(
            f"[{d.get('title')}] ({d.get('url')})\n{d.get('content')}"
            for d in state["documents"][:MAX_DOCUMENTS]
        )
        safe_context = wrap_untrusted(context, source_label="retrieved web content")

        feedback_block = ""
        if state["review"].get("decision") == "NEEDS_MORE":
            feedback_block = f"""
Reviewer feedback on the previous attempt (must be addressed):
- Reason: {state['review'].get('reason', '')}
- Specific gaps: {state['review'].get('missing_information', [])}

Improve the analysis to cover these gaps.
"""

        job_context = ""
        if state["query_type"] == "job_search" and state["jobs"]:
            job_lines = "\n".join(
                f"- {j.get('title')} at {j.get('company') or 'unknown company'} "
                f"({j.get('location') or 'location unknown'}) - "
                f"posted: {j.get('posted_date') or 'unknown'} "
                f"(verified: {j.get('date_verified')}) - source: {j.get('source')} - {j.get('url')}"
                for j in state["jobs"][:15]
            )
            job_context = f"\n\nStructured job listings found so far:\n{job_lines}\n"

        prompt = f"""You are the Analysis Agent.

Actual current date: {date.today().isoformat()}

IMPORTANT - source of information:
- Rely only on the "retrieved content" below - this is real information gathered just now.
- You may have information memorized from training that could be outdated. Do not use it as a
  primary source, and never state something that contradicts the data below based on your
  internal "knowledge".
- If the retrieved data itself looks outdated (no dates close to today's date above), say so
  explicitly instead of ignoring it or silently substituting your own knowledge.

User question:
{state['query']}

Retrieved content:
{safe_context}
{job_context}
{feedback_block}

Analyze the data and identify:
1. Key findings
2. Important facts (with dates where known)
3. Trends
4. Limitations of the available data (is it recent enough relative to today's date?)

Do not perform any additional search. Return only the analysis."""

        response = await llm.ainvoke(prompt)
        analysis_text = response.content

        return {
            "analysis": analysis_text,
            "best_analysis": analysis_text,
            **bump(state, "analysis"),
        }

    return analysis_agent
