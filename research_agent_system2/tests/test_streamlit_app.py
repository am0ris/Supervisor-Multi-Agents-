import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from streamlit.testing.v1 import AppTest

app_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")
at = AppTest.from_file(app_path, default_timeout=30)
at.run()

assert not at.exception, f"الواجهة رمت استثناء عند أول تحميل: {at.exception}"

titles = [t.value for t in at.title]
assert any("Multi-Agent" in t for t in titles)

sidebar_md = [m.value for m in at.sidebar.markdown]
assert any("qwen2.5" in m for m in sidebar_md)
assert any("SEARCH_TIME_LIMIT" in m or "y" in m for m in sidebar_md)  # فلتر الحداثة ظاهر

assert len(at.text_area) == 1
assert len(at.button) == 1

print("✅ الواجهة اتحملت صح من غير أي استثناء")
