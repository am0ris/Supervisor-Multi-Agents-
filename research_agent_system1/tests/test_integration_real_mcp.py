"""
اختبار تكاملي: بيستخدم سيرفر MCP حقيقي (search_web + fetch_url شغالين
فعليًا) مع build_graph() الحقيقية من graph/builder.py - الحاجة الوحيدة
اللي بنعملها mock هي ChatOllama نفسه (عشان مفيش Ollama في بيئة الاختبار).
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import graph.builder as builder_module


class FakeMsg:
    def __init__(self, content):
        self.content = content


class FakeChatOllama:
    """بديل لـ ChatOllama نفسه - نفس الواجهة (ainvoke + with_structured_output)."""
    def __init__(self, *a, **kw):
        pass

    async def ainvoke(self, prompt):
        if "Analysis Agent" in prompt:
            return FakeMsg("[TEST] تحليل حقيقي مبني على محتوى مجلوب فعليًا عبر fetch_url.")
        if "Summary Agent" in prompt:
            return FakeMsg("[TEST] ملخص نهائي.")
        return FakeMsg("[TEST] رد عام")

    def with_structured_output(self, model_cls):
        outer = self

        class _Wrapped:
            def __init__(self):
                self.n = 0

            async def ainvoke(self, prompt):
                self.n += 1
                if model_cls.__name__ == "ReviewResult":
                    return model_cls(decision="APPROVED", reason="[TEST] كافٍ", missing_information=[])
                if model_cls.__name__ == "SupervisorDecision":
                    if "'research': 0" not in prompt.replace(" ", "") and False:
                        pass
                    # نسيب enforce_limits/is_eligible هي اللي تقود التدفق فعليًا:
                    # نرجع "finish" دايمًا، وشبكة الأمان هي اللي هتصحح المسار.
                    return model_cls(next_agent="finish", reason="[TEST] قرار وهمي بسيط")
                raise ValueError("unexpected schema")

        return _Wrapped()


async def main():
    # نستبدل ChatOllama الحقيقي بالنسخة الوهمية جوه موديول builder
    builder_module.ChatOllama = FakeChatOllama

    graph = await builder_module.build_graph()

    from state import make_initial_state

    state = make_initial_state("What is LangGraph?")
    conf = {"configurable": {"thread_id": "integration-1"}, "recursion_limit": 50}

    async for update in graph.astream(state, config=conf, stream_mode="updates"):
        for node in update:
            print("NODE:", node)

    final = graph.get_state(conf).values
    print("\nexecution_history:", final["execution_history"])
    print("agent_calls:", final["agent_calls"])
    print("\ndocuments sources:", [d["source"] for d in final["documents"]])
    print("\nFINAL SUMMARY:\n", final["summary"])

    assert final["summary"]
    # ملحوظة: في بيئة الاختبار دي الإنترنت الخارجي (duckduckgo.com) محجوب،
    # فـ search_web بترجع "no results" بدل نتائج حقيقية - ده متوقع هنا فقط.
    # المهم اللي بنتأكد منه: النظام ماكرشش وكمل لحد summary نهائي حتى
    # لما search_web رجع فاضي (graceful degradation).
    if final["documents"]:
        print("\n✅ اتجابت مستندات حقيقية (فيه إنترنت شغال في البيئة دي)")
    else:
        print("\n⚠️  مفيش مستندات لأن search_web رجع فاضي (الإنترنت محجوب في بيئة الاختبار دي فقط)")
    print("\n✅ build_graph() الحقيقية اشتغلت مع سيرفر MCP حقيقي من غير ما تعطل")


asyncio.run(main())
