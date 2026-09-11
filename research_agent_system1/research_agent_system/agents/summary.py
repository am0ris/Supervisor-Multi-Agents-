"""Summary Agent - بيكتب الإجابة النهائية من أفضل نسخة متاحة."""
from datetime import date

from state import ResearchState
from agents.base import bump


def make_summary_agent(llm):
    async def summary_agent(state: ResearchState):
        print("\n📝 SUMMARY AGENT")

        analysis_used = state["best_analysis"] or state["analysis"]

        prompt = f"""أنت Summary Agent.

تاريخ اليوم الفعلي: {date.today().isoformat()}

السؤال: {state['query']}
التحليل النهائي المتاح: {analysis_used}
نتيجة المراجعة: {state['best_review'] or state['review']}

اكتب إجابة نهائية واضحة ومختصرة.
اعتمد فقط على التحليل المتاح فوق (مبني على بيانات بحث حقيقية) - ممنوع
تضيف أو تصحح أي حقيقة بناءً على معلوماتك المخزّنة من التدريب، حتى لو
حسّيت إنها "أحدث" من وجهة نظرك.
لو فيه نواقص في المعلومات وضّح ده بشفافية.
لا تخترع معلومات غير موجودة في التحليل."""

        response = await llm.ainvoke(prompt)

        return {
            "summary": response.content,
            **bump(state, "summary"),
        }

    return summary_agent
