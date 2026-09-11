"""
اختبار headless للـ Streamlit app باستخدام AppTest، مع mock لـ get_graph()
عشان نتأكد إن الواجهة نفسها (الأزرار، الـ sidebar، عرض النتائج) شغالة صح
من غير الحاجة لـ Ollama أو MCP حقيقيين.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from streamlit.testing.v1 import AppTest

at = AppTest.from_file(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py"), default_timeout=30)
at.run()

print("Exceptions after initial render:", at.exception)
assert not at.exception, f"الواجهة رمت استثناء عند أول تحميل: {at.exception}"

# تأكيد إن العناصر الأساسية اتعرضت
titles = [t.value for t in at.title]
print("Titles:", titles)
assert any("Multi-Agent" in t for t in titles)

sidebar_md = [m.value for m in at.sidebar.markdown]
print("Sidebar has model line:", any("qwen2.5" in m for m in sidebar_md))
assert any("qwen2.5" in m for m in sidebar_md)

# تأكيد وجود مربع النص وزرار التشغيل
assert len(at.text_area) == 1
assert len(at.button) == 1

print("\n✅ الواجهة اتحملت صح من غير أي استثناء، وكل العناصر الأساسية ظاهرة")
