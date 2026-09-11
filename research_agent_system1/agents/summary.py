"""Summary Agent - بيكتب الإجابة النهائية من أفضل نسخة متاحة."""
from state import ResearchState
from agents.base import bump


def make_summary_agent(llm):
    async def summary_agent(state: ResearchState):
        print("\n📝 SUMMARY AGENT")

        analysis_used = state["best_analysis"] or state["analysis"]

        prompt = f"""أنت Summary Agent.

السؤال: {state['query']}
التحليل النهائي المتاح: {analysis_used}
نتيجة المراجعة: {state['best_review'] or state['review']}

اكتب إجابة نهائية واضحة ومختصرة.
لو فيه نواقص في المعلومات وضّح ده بشفافية.
لا تخترع معلومات غير موجودة في التحليل."""

        response = await llm.ainvoke(prompt)

        return {
            "summary": response.content,
            **bump(state, "summary"),
        }

    return summary_agent
