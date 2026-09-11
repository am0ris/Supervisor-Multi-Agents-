import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import graph.builder as builder_module


class _FakeCompiledGraph:
    async def astream(self, initial_state, config, stream_mode):
        steps = [
            ("supervisor", {"next_agent": "research", "supervisor_reason": "بداية"}),
            ("research", {"agent_calls": {"research": 1}}),
            ("supervisor", {"next_agent": "summary", "supervisor_reason": "كفاية"}),
            ("summary", {"agent_calls": {"summary": 1}}),
        ]
        for node, out in steps:
            yield {node: out}

    def get_state(self, config):
        class _S:
            values = {
                "summary": "[TEST] هذا ملخص تجريبي نهائي.",
                "agent_calls": {"research": 1, "extraction": 1, "analysis": 1, "reviewer": 1, "summary": 1},
                "execution_history": ["research", "extraction", "analysis", "reviewer", "summary"],
                "documents": [{"title": "Test Doc", "url": "https://example.com", "source": "fetch_url"}],
            }
        return _S()


async def _fake_build_graph():
    return _FakeCompiledGraph()


builder_module.build_graph = _fake_build_graph

from streamlit.testing.v1 import AppTest

app_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")
at = AppTest.from_file(app_path, default_timeout=30)
at.run()
assert not at.exception

at.text_area[0].set_value("What is LangGraph?")
at.button[0].click().run()

assert not at.exception, f"حصل استثناء بعد الضغط على الزرار: {at.exception}"

markdowns = [m.value for m in at.markdown]
full_text = "\n".join(markdowns)
assert "ملخص تجريبي نهائي" in full_text

print("✅ تدفق الضغط على الزرار كامل شغال")
