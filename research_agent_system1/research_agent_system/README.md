# Multi-Agent Research System

نظام بحث متعدد الإيجنتس: **Supervisor** بيدير 5 إيجنتس (Research, Extraction,
Analysis, Reviewer, Summary)، مبني بـ **LangGraph**، شغال بموديل محلي عبر
**Ollama**، بيستخدم أدوات حقيقية عبر **MCP**، متتبّع بـ **LangSmith**،
ومتاح كواجهة **Streamlit**.

## هيكل المشروع

```
research_agent_system/
├── app.py                     # واجهة Streamlit
├── config.py                  # كل الإعدادات (limits, models, LangSmith, search recency)
├── state.py                   # حالة الـ graph
├── agents/
│   ├── research.py             # tool: search_web
│   ├── extraction.py           # tool: fetch_url
│   ├── analysis.py
│   ├── reviewer.py
│   └── summary.py
├── supervisor/decision.py      # قرار السوبرفايزر + شبكة أمان الحدود
├── graph/builder.py            # بناء الـ LangGraph كامل
├── mcp_server/
│   ├── server.py
│   └── tools/{search.py, fetch.py}
├── tests/
├── notebooks/                  # النسخة الاستكشافية الأصلية (مرجع)
├── requirements.txt
├── .env.example
├── Dockerfile.mcp / Dockerfile.streamlit / docker-compose.yml
```

## ⚠️ تحديث مهم: مشكلة "النتائج بترجع من 2023/2024"

لو لاحظت إن نتائج البحث أو التحليل بتبان قديمة، السبب اتنين حاجات
مختلفة، واتصلحوا الاتنين:

**1. البحث نفسه ماكانش بيفلتر بالحداثة.**
`search_web` كان بينادي `ddgs.text()` من غير أي فلتر زمني. من غير كده،
DuckDuckGo بيرجّح النتائج بالـ **شهرة/backlinks**، مش بتاريخ النشر — يعني
مقال قديم عليه لينكات كتير ممكن يطلع قبل مقال نُشر امبارح. الحل: ضفنا
باراميتر `timelimit` (`d`/`w`/`m`/`y`) لأداة `search_web`، وخليناه
افتراضيًا `y` (آخر سنة) — قابل للتغيير من `.env` بمتغير `SEARCH_TIME_LIMIT`.
لو عايز نتائج أضيق، غيّره لـ `m` (شهر) أو `w` (أسبوع).

**2. الموديل الصغير كان بيميل يرجع لمعرفته الداخلية (training data) بدل
ما يعتمد على البيانات المجلوبة فعليًا.** ده مشهور جدًا مع الموديلات
الصغيرة زي `qwen2.5:3b` — بتحاول "تكمل" من ذاكرتها المدربة بدل ما تلتزم
100% بالسياق. الحل: كل الـ prompts (analysis, reviewer, summary,
supervisor) بقت فيها:
- تاريخ اليوم الفعلي محسوب في وقت التشغيل.
- تعليمات صريحة: "اعتمد فقط على البيانات المجلوبة، ممنوع تستخدم معرفتك
  الداخلية، ولو البيانات نفسها قديمة وضّح ده صراحة بدل ما تعوّضها من عندك".

لو لسه شايف نتائج قديمة بعد الإصلاح ده، جرب موديل أكبر (`qwen2.5:7b` أو
أعلى) — الموديلات الأصغر بتلتزم بالتعليمات دي بشكل أضعف عمومًا.

## تشغيل محلي

```bash
pip install -r requirements.txt
cp .env.example .env
ollama pull qwen2.5:3b && ollama serve
python mcp_server/server.py     # في terminal منفصل، سيبه شغال
streamlit run app.py
```

## LangSmith (اختياري)

حط `LANGSMITH_API_KEY` و `LANGSMITH_PROJECT` في `.env` — التتبع بيتفعّل
تلقائيًا (`config.py` بيظبط `LANGCHAIN_TRACING_V2` لوحده). كل run من
الواجهة متوسوم بـ `tags=["streamlit","multi-agent","mcp"]`.

## Docker

```bash
docker compose up --build
docker exec -it <ollama_container> ollama pull qwen2.5:3b
```
افتح `http://localhost:8501`. (جربت الـ YAML صحيح تركيبيًا، بس معنديش
Docker daemon في بيئتي عشان أشغّله فعليًا end-to-end — جرّبه عندك.)

## الاختبارات

```bash
python tests/test_graph_mock.py            # منطق الحدود + تأكيد تمرير timelimit
python tests/test_integration_real_mcp.py  # build_graph() الحقيقية + سيرفر MCP حقيقي
python tests/test_streamlit_app.py         # الواجهة بتتحمل صح
python tests/test_streamlit_run_flow.py    # تدفق الزرار كامل
```

كل الأربعة بينجحوا في بيئتي. `search_web` بترجع فاضية في بيئة الاختبار
بتاعتي بس لأنها محجوب عندها الإنترنت العام — على جهازك هترجع نتائج حقيقية
حديثة (بفضل `timelimit`).
