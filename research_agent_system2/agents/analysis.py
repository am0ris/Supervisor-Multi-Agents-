"""Analysis Agent - بيحلل المستندات، وبيحسّن نفسه لو المراجع طلب تفاصيل أكتر."""
from datetime import date

from config import AGENT_LIMITS, MAX_DOCUMENTS
from state import ResearchState
from agents.base import bump


def make_analysis_agent(llm):
    async def analysis_agent(state: ResearchState):
        attempt = state["agent_calls"].get("analysis", 0) + 1
        print(f"\n🧠 ANALYSIS AGENT (Try {attempt}/{AGENT_LIMITS['analysis']})")

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

تاريخ اليوم الفعلي: {date.today().isoformat()}

⚠️ تعليمات مهمة عن مصدر المعلومات:
- اعتمد فقط على "بيانات البحث والمستندات" الموجودة تحت - دي معلومات
  حقيقية اتجابت دلوقتي من الإنترنت.
- عندك معلومات مخزّنة من التدريب (training data) ممكن تكون قديمة. ممنوع
  تستخدمها كمصدر أساسي، وممنوع تقول حاجة تتعارض مع البيانات المتاحة تحت
  بناءً على "معرفتك" الداخلية.
- لو بيانات البحث نفسها قديمة (مفيهاش تواريخ حديثة قريبة من تاريخ اليوم
  فوق)، وضّح ده صراحة في التحليل بدل ما تتجاهله أو تعوّضه بمعلومات من عندك.

سؤال المستخدم:
{state['query']}

بيانات البحث والمستندات:
{context}
{feedback_block}

حلل البيانات وحدد:
1. أهم النتائج
2. حقائق مهمة (مع تاريخها لو معروف)
3. اتجاهات
4. محدوديات البيانات المتاحة (هل هي حديثة كفاية بالنسبة لتاريخ اليوم؟)

لا تقم بأي بحث إضافي. رجّع التحليل فقط."""

        response = await llm.ainvoke(prompt)
        analysis_text = response.content

        return {
            "analysis": analysis_text,
            "best_analysis": analysis_text,
            **bump(state, "analysis"),
        }

    return analysis_agent
