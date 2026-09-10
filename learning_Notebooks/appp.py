"""
واجهة Streamlit لمشروع الـ Multi-Agent Research System.

قبل التشغيل لازم يكون شغالين:
  1. Ollama (ollama serve) + الموديل محمّل (ollama pull qwen2.5:3b)
  2. سيرفر MCP: python mcp_server/server.py

تشغيل الواجهة:
    streamlit run app.py
"""
import asyncio
import uuid
import traceback

import nest_asyncio
import streamlit as st

nest_asyncio.apply()

import config
from state import make_initial_state
from graph.builder import build_graph

st.set_page_config(page_title="Multi-Agent Research System", page_icon="🤖", layout="wide")

AGENT_ICONS = {
    "supervisor": "🧭",
    "research": "🔎",
    "extraction": "📄",
    "analysis": "🧠",
    "reviewer": "🔍",
    "summary": "📝",
}


@st.cache_resource(show_spinner=False)
def get_graph():
    """بيبني الـ graph مرة واحدة بس (اتصال MCP + تجهيز الموديلات) ويكاشه."""
    return asyncio.run(build_graph())


def run_graph_sync(graph, initial_state, thread_config, on_update):
    """بيلف على astream ويستدعي on_update لكل خطوة - غلاف sync حوالين async generator."""
    async def _runner():
        async for update in graph.astream(initial_state, config=thread_config, stream_mode="updates"):
            for node, output in update.items():
                on_update(node, output)

    asyncio.run(_runner())


# ---------------------------------------------------------------- Sidebar
with st.sidebar:
    st.header("⚙️ الإعدادات الحالية")
    st.markdown(f"**الموديل:** `{config.OLLAMA_MODEL}`")
    st.markdown(f"**MCP Server:** `{config.MCP_SERVER_URL}`")

    st.markdown("**الحدود لكل إيجنت:**")
    for agent, limit in config.AGENT_LIMITS.items():
        st.markdown(f"- {AGENT_ICONS.get(agent, '•')} `{agent}`: **{limit}** محاولة")

    st.divider()
    if config.LANGSMITH_ENABLED:
        st.success(f"LangSmith مفعّل ✅\nProject: `{config.LANGSMITH_PROJECT}`")
    else:
        st.warning("LangSmith مش مفعّل (اختياري) — ضيف LANGSMITH_API_KEY في .env عشان تفعّله.")

    st.divider()
    st.caption("تأكد إن Ollama وسيرفر الـ MCP شغالين قبل ما تبدأ.")


# ---------------------------------------------------------------- Main
st.title("🤖 Multi-Agent Research System")
st.caption("Supervisor + Research + Extraction + Analysis + Reviewer + Summary — كله شغال بـ LangGraph و MCP.")

query = st.text_area("اكتب سؤالك البحثي:", placeholder="What are the latest developments in RAG?", height=80)
run_clicked = st.button("🚀 ابدأ البحث", type="primary", use_container_width=False)

if run_clicked:
    if not query.strip():
        st.error("اكتب سؤال الأول.")
        st.stop()

    try:
        with st.spinner("بيتصل بسيرفر الـ MCP وبيجهز الموديلات..."):
            graph = get_graph()
    except Exception as e:
        st.error(
            "تعذر تجهيز المشروع. تأكد إن:\n"
            "- Ollama شغال (`ollama serve`) والموديل محمّل\n"
            "- سيرفر الـ MCP شغال (`python mcp_server/server.py`)\n\n"
            f"تفاصيل الخطأ: {e}"
        )
        st.code(traceback.format_exc())
        st.stop()

    thread_id = str(uuid.uuid4())
    thread_config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 30,
        "run_name": "Streamlit Research Run",
        "tags": ["streamlit", "multi-agent", "mcp"],
        "metadata": {"model": config.OLLAMA_MODEL, "agent_limits": config.AGENT_LIMITS},
    }

    initial_state = make_initial_state(query.strip())

    progress_container = st.status("🏃 المشروع شغال...", expanded=True)
    step_log = []

    def on_update(node, output):
        icon = AGENT_ICONS.get(node, "•")
        if node == "supervisor":
            reason = output.get("supervisor_reason", "")
            nxt = output.get("next_agent", "")
            line = f"{icon} **Supervisor** → `{nxt}`  \n> {reason}"
        else:
            calls = output.get("agent_calls", {}).get(node)
            line = f"{icon} **{node}** اشتغل (محاولة رقم {calls})"
        step_log.append(line)
        progress_container.write(line)

    try:
        run_graph_sync(graph, initial_state, thread_config, on_update)
        progress_container.update(label="✅ خلص!", state="complete", expanded=False)
    except Exception as e:
        progress_container.update(label="❌ حصل خطأ", state="error")
        st.error(f"حصل خطأ أثناء التنفيذ: {e}")
        st.code(traceback.format_exc())
        st.stop()

    final_state = graph.get_state(thread_config).values

    st.divider()
    st.subheader("📝 الإجابة النهائية")
    st.markdown(final_state["summary"])

    with st.expander("📊 تفاصيل التنفيذ (عدد مرات كل إيجنت + المصادر)"):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**عدد مرات كل إيجنت:**")
            st.json(final_state["agent_calls"])
        with col2:
            st.markdown("**الترتيب الكامل:**")
            st.write(" → ".join(final_state["execution_history"]))

        if final_state["documents"]:
            st.markdown("**المستندات المستخدمة:**")
            for d in final_state["documents"]:
                src_badge = "🌐 صفحة كاملة" if d["source"] == "fetch_url" else "✂️ snippet فقط"
                st.markdown(f"- [{d['title']}]({d['url']}) — {src_badge}")
