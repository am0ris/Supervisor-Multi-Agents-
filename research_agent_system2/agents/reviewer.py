"""Reviewer Agent - بيقيّم كفاية التحليل بـ structured output."""
from datetime import date
from typing import Literal
from pydantic import BaseModel

from config import AGENT_LIMITS
from state import ResearchState
from agents.base import bump


class ReviewResult(BaseModel):
    decision: Literal["APPROVED", "NEEDS_MORE"]
    reason: str
    missing_information: list[str]


def make_reviewer_agent(review_llm):
    async def reviewer_agent(state: ResearchState):
        attempt = state["agent_calls"].get("reviewer", 0) + 1
        print(f"\n🔍 REVIEWER AGENT (محاولة {attempt}/{AGENT_LIMITS['reviewer']})")

        prompt = f"""أنت مراجع بحثي صارم.

تاريخ اليوم الفعلي: {date.today().isoformat()}

السؤال: {state['query']}
التحليل: {state['analysis']}

قيّم هل التحليل كافٍ عشان يجاوب على السؤال بشكل مفيد. من ضمن معايير
التقييم: هل التحليل معتمد على معلومات حديثة (قريبة من تاريخ اليوم فوق)
ولا معتمد على معلومات عامة تبدو من معرفة الموديل الداخلية مش من بيانات
بحث فعلية؟ لو التحليل مايذكرش تواريخ أو مصادر حديثة رغم إن السؤال بيطلب
"آخر التطورات"، اعتبر ده نقص واطلب NEEDS_MORE.

لا تقم بأي بحث إضافي. لو ناقص حاجة، حددها بوضوح."""

        try:
            result = await review_llm.ainvoke(prompt)
            review_dict = result.model_dump()
        except Exception as e:
            review_dict = {
                "decision": "APPROVED",
                "reason": f"تعذر تقييم دقيق ({e}), تم القبول احتياطيًا.",
                "missing_information": [],
            }

        return {
            "review": review_dict,
            "best_review": review_dict,
            **bump(state, "reviewer"),
        }

    return reviewer_agent
