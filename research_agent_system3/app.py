"""
Streamlit front end for the Multi-Agent Research System.

Before running:
  1. Ollama running (`ollama serve`) with the model pulled (`ollama pull qwen2.5:3b`)
  2. MCP server running: `python mcp_server/server.py`

Run:
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
from jobs.intent import detect_query_type
from jobs.sources.search_discovery import PLATFORM_DOMAINS
from jobs.date_utils import RECENCY_LABEL_TO_TIMELIMIT

st.set_page_config(page_title="Multi-Agent Research System", page_icon="🤖", layout="wide")

AGENT_ICONS = {
    "supervisor": "🧭",
    "research": "🔎",
    "extraction": "📄",
    "analysis": "🧠",
    "reviewer": "🔍",
    "summary": "📝",
}

RECENCY_LABELS = {
    "today": "Today",
    "last_24_hours": "Last 24 hours",
    "last_3_days": "Last 3 days",
    "last_7_days": "Last 7 days",
    "last_month": "Last month",
    "last_3_months": "Last 3 months",
}


@st.cache_resource(show_spinner=False)
def get_graph():
    """Builds the graph once (MCP connection + model setup) and caches it."""
    return asyncio.run(build_graph())


def run_graph_sync(graph, initial_state, thread_config, on_update):
    async def _runner():
        async for update in graph.astream(initial_state, config=thread_config, stream_mode="updates"):
            for node, output in update.items():
                on_update(node, output)

    asyncio.run(_runner())


# ---------------------------------------------------------------- Sidebar
with st.sidebar:
    st.header("Settings")
    st.markdown(f"**Model:** `{config.OLLAMA_MODEL}`")
    st.markdown(f"**MCP Server:** `{config.MCP_SERVER_URL}`")
    st.markdown(f"**Search provider:** `{config.SEARCH_PROVIDER}` (fallback: `{config.SEARCH_PROVIDER_FALLBACK}`)")
    st.markdown(f"**Recency filter (general search):** `{config.SEARCH_TIME_LIMIT or 'none'}`")

    st.markdown("**Per-agent limits:**")
    for agent, limit in config.AGENT_LIMITS.items():
        st.markdown(f"- {AGENT_ICONS.get(agent, '•')} `{agent}`: **{limit}** attempt(s)")

    st.divider()
    if config.LANGSMITH_ENABLED:
        st.success(f"LangSmith enabled ✅\nProject: `{config.LANGSMITH_PROJECT}`")
    else:
        st.warning("LangSmith is not enabled (optional) — add LANGSMITH_API_KEY to .env to enable it.")

    st.divider()
    st.caption("Make sure Ollama and the MCP server are both running before you start.")


# ---------------------------------------------------------------- Main
st.title("🤖 Multi-Agent Research System")
st.caption("Supervisor + Research + Extraction + Analysis + Reviewer + Summary — powered by LangGraph and MCP.")

mode = st.radio("Mode", ["General Research", "Job Search"], horizontal=True)

job_filters = {}

if mode == "Job Search":
    st.subheader("Job search filters")
    col1, col2, col3 = st.columns(3)
    with col1:
        job_title = st.text_input("Job title", placeholder="Generative AI Engineer")
        location = st.text_input("Location", placeholder="Egypt, Cairo, Remote...")
    with col2:
        remote_pref = st.selectbox("Remote / Hybrid / On-site", ["Any", "Remote", "Hybrid", "On-site"])
        experience_level = st.selectbox("Experience level", ["Any", "Entry", "Mid", "Senior"])
    with col3:
        recency_label = st.selectbox("Date range", list(RECENCY_LABELS.keys()), format_func=lambda k: RECENCY_LABELS[k], index=4)
        max_results = st.number_input("Max results", min_value=5, max_value=100, value=20, step=5)

    skills_input = st.text_input("Skills (comma-separated)", placeholder="Python, LangChain, RAG")
    selected_platforms = st.multiselect(
        "Platforms to search", options=list(PLATFORM_DOMAINS.keys()), default=list(PLATFORM_DOMAINS.keys())
    )

    query_parts = [job_title or "jobs"]
    if remote_pref != "Any":
        query_parts.append(remote_pref)
    if experience_level != "Any":
        query_parts.append(experience_level)
    if location:
        query_parts.append(f"in {location}")
    query = " ".join(query_parts)

    job_filters = {
        "max_results": int(max_results),
        "timelimit": RECENCY_LABEL_TO_TIMELIMIT.get(recency_label, "m"),
        "platforms": selected_platforms or None,
        "location": location or None,
        "skills": [s.strip() for s in skills_input.split(",") if s.strip()] or None,
    }
    st.caption(f"Query that will be sent: *{query}*")
else:
    query = st.text_area("Research question:", placeholder="What are the latest developments in RAG?", height=80)

run_clicked = st.button("🚀 Start", type="primary")

if run_clicked:
    if mode == "Job Search" and not job_filters.get("location") and not query.strip():
        st.error("Enter at least a job title.")
        st.stop()
    if mode == "General Research" and not query.strip():
        st.error("Enter a question first.")
        st.stop()

    try:
        with st.spinner("Connecting to the MCP server and preparing the models..."):
            graph = get_graph()
    except Exception as e:
        st.error(
            "Could not set up the pipeline. Make sure:\n"
            "- Ollama is running (`ollama serve`) with the model pulled\n"
            "- The MCP server is running (`python mcp_server/server.py`)\n\n"
            f"Error details: {e}"
        )
        st.code(traceback.format_exc())
        st.stop()

    query_type = "job_search" if mode == "Job Search" else detect_query_type(query)

    thread_id = str(uuid.uuid4())
    thread_config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 40,
        "run_name": "Streamlit Research Run",
        "tags": ["streamlit", "multi-agent", "mcp", query_type],
        "metadata": {
            "query": query,
            "query_type": query_type,
            "search_provider": config.SEARCH_PROVIDER,
            "model": config.OLLAMA_MODEL,
            "agent_limits": config.AGENT_LIMITS,
        },
    }

    initial_state = make_initial_state(query.strip(), query_type=query_type, job_filters=job_filters)

    progress_container = st.status("Running...", expanded=True)
    sources_searched_placeholder = st.empty()

    def on_update(node, output):
        icon = AGENT_ICONS.get(node, "•")
        if node == "supervisor":
            reason = output.get("supervisor_reason", "")
            nxt = output.get("next_agent", "")
            line = f"{icon} **Supervisor** → `{nxt}`  \n> {reason}"
        else:
            calls = output.get("agent_calls", {}).get(node)
            line = f"{icon} **{node}** ran (attempt {calls})"
        progress_container.write(line)

    try:
        run_graph_sync(graph, initial_state, thread_config, on_update)
        progress_container.update(label="Done!", state="complete", expanded=False)
    except Exception as e:
        progress_container.update(label="An error occurred", state="error")
        st.error(f"Error during execution: {e}")
        st.code(traceback.format_exc())
        st.stop()

    final_state = graph.get_state(thread_config).values

    st.divider()
    st.subheader("📝 Final Answer")
    st.markdown(final_state["summary"])

    if query_type == "job_search":
        stats = final_state.get("job_search_stats", {})
        st.divider()
        st.subheader("📊 Search statistics")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Sources searched", len(stats.get("sources_searched", [])))
        c2.metric("Total results", stats.get("total_results", 0))
        c3.metric("Unique results", stats.get("unique_results", 0))
        c4.metric("Verified-date results", stats.get("verified_recent_results", 0))

        if stats.get("errors"):
            with st.expander(f"⚠️ {len(stats['errors'])} source(s) had errors (search continued regardless)"):
                for err in stats["errors"]:
                    st.text(err)

        jobs = sorted(final_state["jobs"], key=lambda j: j.get("relevance_score") or 0, reverse=True)
        st.subheader(f"💼 Ranked jobs ({len(jobs)})")
        for job in jobs:
            date_label = job.get("posted_date") or "Unknown / unverified"
            verified_badge = "✅ verified" if job.get("date_verified") else "❓ unverified"
            with st.expander(f"{job.get('title')} — {job.get('company') or 'Unknown company'} ({job.get('source')})"):
                st.markdown(f"**Location:** {job.get('location') or 'Unknown'} &nbsp;|&nbsp; **Remote type:** {job.get('remote_type') or 'Unknown'}")
                st.markdown(f"**Posted:** {date_label} ({verified_badge}, confidence: `{job.get('date_confidence')}`)")
                if job.get("salary"):
                    st.markdown(f"**Salary:** {job['salary']} {job.get('currency') or ''}")
                if job.get("required_skills"):
                    st.markdown(f"**Skills:** {', '.join(job['required_skills'])}")
                st.markdown(f"**Relevance score:** {job.get('relevance_score')}")
                st.markdown(f"[Open original posting]({job.get('url')})")
    else:
        with st.expander("📊 Execution details"):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Attempts per agent:**")
                st.json(final_state["agent_calls"])
            with col2:
                st.markdown("**Full sequence:**")
                st.write(" → ".join(final_state["execution_history"]))

            if final_state["documents"]:
                st.markdown("**Documents used:**")
                for d in final_state["documents"]:
                    badge = "🌐 full page" if d["source"] == "fetch_url" else "✂️ snippet only"
                    st.markdown(f"- [{d['title']}]({d['url']}) — {badge}")
