"""
Reviewer Agent.

For job searches, the review combines deterministic, code-computed
checks (date known? verified? URL well-formed? any results at all?) with
an LLM judgment on the more subjective checks (actual relevance, role
match, whether listed skills are supported by the source text). The
deterministic checks act as a safety net: if job results are objectively
too sparse or unverified, we force NEEDS_MORE with `needs_more_search`
regardless of what the LLM says, matching the existing pattern in this
codebase where the LLM proposes and code disposes.
"""
from datetime import date
from typing import Literal
from pydantic import BaseModel

from config import AGENT_LIMITS
from state import ResearchState
from agents.base import bump
from security.prompt_injection import wrap_untrusted


class ReviewResult(BaseModel):
    decision: Literal["APPROVED", "NEEDS_MORE"]
    reason: str
    missing_information: list[str] = []
    # True when the reviewer believes another SEARCH round (not just a
    # deeper analysis pass) is needed - e.g. too few relevant/verified
    # job results, not merely "the writeup could be more detailed".
    needs_more_search: bool = False


def _compute_job_quality_metrics(state: ResearchState) -> dict:
    jobs = state["jobs"]
    verified = sum(1 for j in jobs if j.get("date_verified"))
    with_valid_url = sum(1 for j in jobs if isinstance(j.get("url"), str) and j["url"].startswith("http"))
    unknown_dates = sum(1 for j in jobs if j.get("date_confidence") == "date_unknown")

    return {
        "total_jobs": len(jobs),
        "verified_date_jobs": verified,
        "jobs_with_valid_url": with_valid_url,
        "jobs_with_unknown_date": unknown_dates,
    }


def make_reviewer_agent(review_llm):
    async def reviewer_agent(state: ResearchState):
        attempt = state["agent_calls"].get("reviewer", 0) + 1
        print(f"\nREVIEWER AGENT (attempt {attempt}/{AGENT_LIMITS['reviewer']})")

        if state["query_type"] == "job_search":
            review_dict = await _review_job_search(state, review_llm)
        else:
            review_dict = await _review_general(state, review_llm)

        return {
            "review": review_dict,
            "best_review": review_dict,
            **bump(state, "reviewer"),
        }

    return reviewer_agent


async def _review_general(state: ResearchState, review_llm) -> dict:
    safe_analysis = wrap_untrusted(state["analysis"], source_label="analysis output")

    prompt = f"""You are a strict research reviewer.

Actual current date: {date.today().isoformat()}

Question: {state['query']}
Analysis: {safe_analysis}

Judge whether the analysis is sufficient to usefully answer the question. One criterion:
is the analysis grounded in recent information (close to today's date above), or does it
read like generic/outdated knowledge with no real dates or sources? If the analysis doesn't
mention recent dates or sources despite the question asking about "latest developments",
treat that as a gap and request NEEDS_MORE.

Do not perform any additional search. If something is missing, say exactly what."""

    try:
        result = await review_llm.ainvoke(prompt)
        return result.model_dump()
    except Exception as e:
        return {
            "decision": "APPROVED",
            "reason": f"Could not run a precise review ({e}); approved as a fallback.",
            "missing_information": [],
            "needs_more_search": False,
        }


async def _review_job_search(state: ResearchState, review_llm) -> dict:
    metrics = _compute_job_quality_metrics(state)
    safe_analysis = wrap_untrusted(state["analysis"], source_label="analysis output")

    job_summary = "\n".join(
        f"- {j.get('title')} @ {j.get('company')} | location={j.get('location')} | "
        f"date_confidence={j.get('date_confidence')} | verified={j.get('date_verified')} | url={j.get('url')}"
        for j in state["jobs"][:15]
    )

    prompt = f"""You are a strict job-search reviewer. Verify the following, for each job:
- Is this actually a job posting (not a generic page)?
- Is it relevant to the user's request?
- Does the location match (if the user specified one)?
- Does the role match the requested title/family?
- Are the listed skills plausibly supported by the source content?

Do not perform any additional search.

User request: {state['query']}
Deterministic metrics (already computed in code, trust these numbers): {metrics}

Jobs found:
{job_summary}

Analysis written from these jobs:
{safe_analysis}

If there are too few relevant, verified jobs to give the user a useful answer, set
needs_more_search=true and decision=NEEDS_MORE so another search round can run."""

    try:
        result = await review_llm.ainvoke(prompt)
        review_dict = result.model_dump()
    except Exception as e:
        review_dict = {
            "decision": "APPROVED",
            "reason": f"Could not run a precise review ({e}); approved as a fallback.",
            "missing_information": [],
            "needs_more_search": False,
        }

    # Deterministic safety net: force NEEDS_MORE + needs_more_search when
    # the objective numbers are simply too thin, regardless of the LLM's
    # own judgment (small local models can be overly generous here).
    if metrics["total_jobs"] == 0 or metrics["verified_date_jobs"] == 0:
        review_dict["decision"] = "NEEDS_MORE"
        review_dict["needs_more_search"] = True
        review_dict.setdefault("missing_information", [])
        review_dict["missing_information"].append(
            f"Only {metrics['total_jobs']} job(s) found, {metrics['verified_date_jobs']} with a verified date."
        )
        review_dict["reason"] = (review_dict.get("reason", "") + " Overridden: insufficient verified job data.").strip()

    return review_dict
