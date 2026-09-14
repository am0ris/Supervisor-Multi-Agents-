"""
Headless Streamlit tests for the full run flow (button click -> progress
-> results), for both General Research and Job Search modes, using a
mocked graph (no Ollama/MCP required).
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import graph.builder as builder_module

APP_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")


class _FakeGeneralGraph:
    async def astream(self, initial_state, config, stream_mode):
        steps = [
            ("supervisor", {"next_agent": "research", "supervisor_reason": "start"}),
            ("research", {"agent_calls": {"research": 1}}),
            ("supervisor", {"next_agent": "summary", "supervisor_reason": "enough"}),
            ("summary", {"agent_calls": {"summary": 1}}),
        ]
        for node, out in steps:
            yield {node: out}

    def get_state(self, config):
        class _S:
            values = {
                "summary": "[TEST] This is the final general research summary.",
                "agent_calls": {"research": 1, "extraction": 1, "analysis": 1, "reviewer": 1, "summary": 1},
                "execution_history": ["research", "extraction", "analysis", "reviewer", "summary"],
                "documents": [{"title": "Test Doc", "url": "https://example.com", "source": "fetch_url"}],
                "jobs": [],
                "job_search_stats": {},
            }
        return _S()


class _FakeJobSearchGraph:
    async def astream(self, initial_state, config, stream_mode):
        steps = [
            ("supervisor", {"next_agent": "research", "supervisor_reason": "start job search"}),
            ("research", {"agent_calls": {"research": 1}}),
            ("supervisor", {"next_agent": "summary", "supervisor_reason": "enough jobs found"}),
            ("summary", {"agent_calls": {"summary": 1}}),
        ]
        for node, out in steps:
            yield {node: out}

    def get_state(self, config):
        class _S:
            values = {
                "summary": "[TEST] Found 2 relevant Generative AI Engineer jobs.",
                "agent_calls": {"research": 1, "extraction": 1, "analysis": 1, "reviewer": 1, "summary": 1},
                "execution_history": ["research", "extraction", "analysis", "reviewer", "summary"],
                "documents": [],
                "jobs": [
                    {
                        "title": "Generative AI Engineer", "company": "Acme AI", "location": "Cairo, Egypt",
                        "remote_type": "remote", "url": "https://linkedin.com/jobs/1", "source": "linkedin",
                        "posted_date": "2026-09-01T00:00:00+00:00", "date_verified": True,
                        "date_confidence": "published_date", "relevance_score": 0.91,
                        "required_skills": ["Python", "LangChain"], "salary": None, "currency": None,
                    },
                    {
                        "title": "LLM Engineer", "company": "RemoteCo", "location": None,
                        "remote_type": "remote", "url": "https://remoteok.com/jobs/2", "source": "remoteok",
                        "posted_date": None, "date_verified": False,
                        "date_confidence": "date_unknown", "relevance_score": 0.75,
                        "required_skills": [], "salary": None, "currency": None,
                    },
                ],
                "job_search_stats": {
                    "sources_searched": ["remoteok", "weworkremotely", "linkedin"],
                    "total_results": 3, "unique_results": 2, "verified_recent_results": 1,
                    "errors": ["weworkremotely: simulated timeout"],
                },
            }
        return _S()


def test_general_research_run_flow():
    from streamlit.testing.v1 import AppTest

    async def _fake_build_graph():
        return _FakeGeneralGraph()

    builder_module.build_graph = _fake_build_graph

    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    at.text_area[0].set_value("What is LangGraph?")
    at.button[0].click().run()

    assert not at.exception, f"Run raised: {at.exception}"
    full_text = "\n".join(m.value for m in at.markdown)
    assert "final general research summary" in full_text
    print("PASS: test_general_research_run_flow")


def test_job_search_run_flow_shows_ranked_jobs_and_stats():
    from streamlit.testing.v1 import AppTest
    import streamlit as st

    st.cache_resource.clear()  # avoid picking up the previous test's cached fake graph

    async def _fake_build_graph():
        return _FakeJobSearchGraph()

    builder_module.build_graph = _fake_build_graph

    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    at.radio[0].set_value("Job Search").run()

    job_title_input = next(ti for ti in at.text_input if ti.label == "Job title")
    job_title_input.set_value("Generative AI Engineer")
    at.button[0].click().run()

    assert not at.exception, f"Job search run raised: {at.exception}"

    expander_labels = "\n".join(e.label for e in at.expander)
    assert "Generative AI Engineer" in expander_labels
    assert "Acme AI" in expander_labels
    assert "LLM Engineer" in expander_labels

    metric_values = [m.value for m in at.metric]
    assert "3" in metric_values  # sources_searched count (remoteok, wwr, linkedin)
    print("PASS: test_job_search_run_flow_shows_ranked_jobs_and_stats")


if __name__ == "__main__":
    test_general_research_run_flow()
    test_job_search_run_flow_shows_ranked_jobs_and_stats()
    print("\n✅ All Streamlit run-flow tests passed")
