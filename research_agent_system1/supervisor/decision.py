"""
السوبرفايزر: الـ LLM بيقترح، لكن أي قرار بيتفحص بـ is_eligible قبل
التنفيذ. لو غير مسموح، بيتصحح تلقائيًا بمنطق حتمي (compute_fallback_agent).
"""
from typing import Literal, Optional
from pydantic import BaseModel, Field

from config import AGENT_LIMITS
from state import ResearchState


class SupervisorDecision(BaseModel):
    next_agent: Literal[
        "research", "extraction", "analysis", "reviewer", "summary", "finish"
    ]
    reason: str = Field(description="سبب قصير للقرار")


def _remaining(state: ResearchState) -> dict:
    return {
        agent: AGENT_LIMITS[agent] - state["agent_calls"].get(agent, 0)
        for agent in AGENT_LIMITS
    }


def is_eligible(agent: str, state: ResearchState) -> bool:
    calls = state["agent_calls"]

    def has_budget(a: str) -> bool:
        return calls.get(a, 0) < AGENT_LIMITS[a]

    if calls.get("summary", 0) >= 1:
        return agent == "finish"

    if agent == "finish":
        return bool(state["summary"]) or all(not has_budget(a) for a in AGENT_LIMITS)

    if agent == "research":
        return has_budget("research") and calls.get("extraction", 0) == 0

    if agent == "extraction":
        return (
            has_budget("extraction")
            and calls.get("research", 0) >= 4
            and calls.get("analysis", 0) == 0
        )

    if agent == "analysis":
        return has_budget("analysis") and calls.get("extraction", 0) >= 1

    if agent == "reviewer":
        return has_budget("reviewer") and calls.get("analysis", 0) >= 1

    if agent == "summary":
        review_decision = state["review"].get("decision")
        loop_still_open = has_budget("analysis") and has_budget("reviewer")
        return (
            has_budget("summary")
            and calls.get("analysis", 0) >= 1
            and calls.get("reviewer", 0) >= 1
            and (review_decision == "APPROVED" or not loop_still_open)
        )

    return False


def compute_fallback_agent(state: ResearchState) -> tuple[str, str]:
    calls = state["agent_calls"]

    if calls.get("research", 0) == 0:
        return "research", "لازم بيانات بحث قبل أي حاجة تانية."
    if calls.get("extraction", 0) == 0:
        return "extraction", "عندنا نتائج بحث؛ وقت الاستخراج."
    if calls.get("analysis", 0) == 0:
        return "analysis", "عندنا مستندات؛ وقت التحليل الأول."
    if calls.get("summary", 0) >= 1:
        return "finish", "تم إصدار الملخص النهائي بالفعل."

    if calls.get("reviewer", 0) < calls.get("analysis", 0) and is_eligible("reviewer", state):
        return "reviewer", "فيه تحليل جديد محتاج مراجعة."

    review_decision = state["review"].get("decision")
    if (
        review_decision == "NEEDS_MORE"
        and is_eligible("analysis", state)
        and AGENT_LIMITS["reviewer"] - calls.get("reviewer", 0) > 0
    ):
        return "analysis", "المراجع طلب تحسين التحليل وفيه محاولات متبقية."

    if is_eligible("summary", state):
        return "summary", "التحليل والمراجعة جاهزين؛ وقت التلخيص النهائي."

    return "finish", "كل الحدود المتاحة اتستنفذت أو خلصنا كل المراحل."


def build_supervisor_prompt(state: ResearchState) -> str:
    remaining = _remaining(state)
    eligible_now = [a for a in list(AGENT_LIMITS) + ["finish"] if is_eligible(a, state)]

    return f"""أنت Supervisor Agent بيدير فريق إيجنتس عشان يجاوب على سؤال بحثي بأفضل نتيجة ممكنة.

السؤال: {state['query']}

تم تنفيذ حتى الآن: {state['execution_history'] or 'لسه معملش حاجة'}
عدد نتائج البحث: {len(state['research_results'])}
عدد المستندات: {len(state['documents'])}
يوجد تحليل حالي: {'نعم' if state['analysis'] else 'لا'}
نتيجة آخر مراجعة: {state['review'] or 'لا يوجد بعد'}
يوجد ملخص نهائي: {'نعم' if state['summary'] else 'لا'}

الحد الأقصى المتبقي لكل إيجنت: {remaining}
الخيارات المسموحة فعليًا دلوقتي فقط: {eligible_now}

اختر واحد فقط من "الخيارات المسموحة" واشرح سببك باختصار.
لو المراجع طلب NEEDS_MORE وفيه محاولات analysis/reviewer متبقية، الأفضل عادة الرجوع لـ analysis.
لو مفيش داعي لمزيد من التحسين، كمل عادي للمرحلة التالية.
"""


def enforce_limits(raw_agent: str, state: ResearchState) -> tuple[str, Optional[str]]:
    if is_eligible(raw_agent, state):
        return raw_agent, None

    fallback_agent, fallback_reason = compute_fallback_agent(state)
    override_reason = (
        f"تم تجاوز قرار السوبرفايزر ('{raw_agent}' غير مسموح به الآن) "
        f"والانتقال لـ '{fallback_agent}': {fallback_reason}"
    )
    return fallback_agent, override_reason
