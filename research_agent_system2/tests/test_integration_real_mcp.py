import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import graph.builder as builder_module


class FakeMsg:
    def __init__(self, content):
        self.content = content


class FakeChatOllama:
    def __init__(self, *a, **kw):
        pass

    async def ainvoke(self, prompt):
        if "Analysis Agent" in prompt:
            return FakeMsg("[TEST] تحليل تجريبي.")
        if "Summary Agent" in prompt:
            return FakeMsg("[TEST] ملخص نهائي.")
        return FakeMsg("[TEST] رد عام")

    def with_structured_output(self, model_cls):
        class _Wrapped:
            async def ainvoke(self, prompt):
                if model_cls.__name__ == "ReviewResult":
                    return model_cls(decision="APPROVED", reason="[TEST]", missing_information=[])
                if model_cls.__name__ == "SupervisorDecision":
                    return model_cls(next_agent="finish", reason="[TEST]")
                raise ValueError("unexpected schema")
        return _Wrapped()


async def main():
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
    assert final["summary"]
    print("\n✅ build_graph() الحقيقية اشتغلت مع سيرفر MCP حقيقي من غير ما تعطل")


asyncio.run(main())
