"""Analysis Agent - بيحلل المستندات، وبيحسّن نفسه لو المراجع طلب تفاصيل أكتر."""
from config import AGENT_LIMITS, MAX_DOCUMENTS
from state import ResearchState
from agents.base import bump


def make_analysis_agent(llm):
    async def analysis_agent(state: ResearchState):
        attempt = state["agent_calls"].get("analysis", 0) + 1
        print(f"\n🧠 ANALYSIS AGENT (محاولة {attempt}/{AGENT_LIMITS['analysis']})")

        context = "\n\n".join(
            f"[{d.get('title')}] ({d.get('url')})\n{d.get('content')}"
            for d in state["documents"][:MAX_DOCUMENTS]
        )

        feedback_block = ""
        if state["review"].get("decision") == "NEEDS_MORE":
            feedback_block = f"""
ملاحظات المراجع على المحاولة السابقة (لازم تعالجها):
- سبب: {state['review'].get('reason', '')}
- نواقص محددة: {state['review'].get('missing_information', [])}

حسّن التحليل عشان يغطي النواقص دي.
"""

        prompt = f"""أنت Analysis Agent.

سؤال المستخدم:
{state['query']}

بيانات البحث والمستندات:
{context}
{feedback_block}

حلل البيانات وحدد:
1. أهم النتائج
2. حقائق مهمة
3. اتجاهات
4. محدوديات البيانات المتاحة

لا تقم بأي بحث إضافي. رجّع التحليل فقط."""

        response = await llm.ainvoke(prompt)
        analysis_text = response.content

        return {
            "analysis": analysis_text,
            "best_analysis": analysis_text,
            **bump(state, "analysis"),
        }

    return analysis_agent
