"""Headless Streamlit tests: confirms the app renders without exceptions
in both General Research and Job Search modes."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from streamlit.testing.v1 import AppTest

APP_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")


def test_general_research_mode_renders():
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    assert not at.exception, f"Initial render raised: {at.exception}"

    titles = [t.value for t in at.title]
    assert any("Multi-Agent" in t for t in titles)

    sidebar_md = [m.value for m in at.sidebar.markdown]
    assert any("qwen2.5" in m for m in sidebar_md)

    assert len(at.text_area) == 1  # the general research question box
    assert len(at.button) == 1
    print("PASS: test_general_research_mode_renders")


def test_job_search_mode_renders_all_filters():
    at = AppTest.from_file(APP_PATH, default_timeout=30)
    at.run()
    at.radio[0].set_value("Job Search").run()
    assert not at.exception, f"Switching to Job Search raised: {at.exception}"

    text_input_labels = {ti.label for ti in at.text_input}
    assert {"Job title", "Location", "Skills (comma-separated)"} <= text_input_labels

    selectbox_labels = {sb.label for sb in at.selectbox}
    assert {"Remote / Hybrid / On-site", "Experience level", "Date range"} <= selectbox_labels

    assert len(at.multiselect) == 1
    assert len(at.number_input) == 1
    print("PASS: test_job_search_mode_renders_all_filters")


if __name__ == "__main__":
    test_general_research_mode_renders()
    test_job_search_mode_renders_all_filters()
    print("\n✅ All Streamlit render tests passed")
