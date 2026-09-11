# Multi-Agent Research System

نظام بحث متعدد الإيجنتس: **Supervisor** بيدير 5 إيجنتس (Research, Extraction,
Analysis, Reviewer, Summary)، مبني بـ **LangGraph**، شغال بموديل محلي عبر
**Ollama**، بيستخدم أدوات حقيقية عبر **MCP** (Model Context Protocol)، متتبّع
بـ **LangSmith**، ومتاح كواجهة **Streamlit**.

## هيكل المشروع

```
research_agent_system/
├── app.py                     # واجهة Streamlit
├── config.py                  # كل الإعدادات (limits, models, LangSmith)
├── state.py                   # حالة الـ graph
├── agents/
│   ├── base.py                 # helper مشترك
│   ├── research.py             # بيستخدم tool: search_web
│   ├── extraction.py           # بيستخدم tool: fetch_url
│   ├── analysis.py
│   ├── reviewer.py              # structured output: ReviewResult
│   └── summary.py
├── supervisor/
│   └── decision.py             # قرار السوبرفايزر + شبكة أمان الحدود
├── graph/
│   └── builder.py               # بناء الـ LangGraph كامل
├── mcp_server/
│   ├── server.py                 # سيرفر MCP (FastMCP)
│   └── tools/
│       ├── search.py             # tool: search_web (ddgs، بدون API key)
│       └── fetch.py              # tool: fetch_url (يجيب نص الصفحة فعليًا)
├── tests/                      # اختبارات (mock + integration + streamlit)
├── notebooks/                  # نسخة النوتبوك الاستكشافية الأصلية (مرجع)
├── requirements.txt
├── .env.example
├── Dockerfile.mcp
├── Dockerfile.streamlit
└── docker-compose.yml
```

## الأدوات (Tools) اللي فعليًا بتضيف قدرة حقيقية للإيجنتس

| الإيجنت | الأداة | إيه اللي بتعمله فعليًا |
|---|---|---|
| `research` | `search_web` (MCP) | بحث حقيقي على الإنترنت بدون API key (مكتبة `ddgs`) |
| `extraction` | `fetch_url` (MCP) | بتجيب **النص الفعلي الكامل** لأفضل الصفحات (مش الـ snippet القصير بس)، مع fallback للـ snippet لو الصفحة اترفضت أو الرابط ميت |

كل الإيجنتس التانية (`analysis`, `reviewer`, `summary`) بتشتغل بالاستدلال (reasoning)
بس على البيانات اللي وصلتلها — مفيش داعي لأداة خارجية ليها، ودي حاجة طبيعية
(مش كل إيجنت لازم يكون له tool، المهم إنه بياخد قرارات مستقلة عن الخطوة الجاية).

## تشغيل محلي (بدون Docker)

### 1. جهّز البيئة
```bash
python -m venv venv && source venv/bin/activate   # أو أي بيئة تفضلها
pip install -r requirements.txt
cp .env.example .env
```

### 2. شغّل Ollama
```bash
ollama pull qwen2.5:3b
ollama serve   # لو مش شغال تلقائي
```

### 3. شغّل سيرفر الـ MCP (سيبه شغال في terminal منفصل)
```bash
python mcp_server/server.py
```
استنى تشوف: `Uvicorn running on http://0.0.0.0:8000`

### 4. شغّل الواجهة
```bash
streamlit run app.py
```
هتفتح على `http://localhost:8501`

## تفعيل LangSmith (اختياري)

1. اعمل حساب على https://smith.langchain.com/ وهات API key.
2. في ملف `.env`:
   ```
   LANGSMITH_API_KEY=ls__...
   LANGSMITH_PROJECT=multi-agent-research
   ```
3. كده خلاص — `config.py` بيفعّل التتبع تلقائيًا (`LANGCHAIN_TRACING_V2=true`)
   من غير ما تلمس أي كود تاني. لو الـ key فاضي، المشروع بيشتغل عادي من غير تتبع.
4. الواجهة (sidebar) بتوريك حالة LangSmith (مفعّل ولا لأ) في أي وقت.

كل run من الواجهة بيتوسم تلقائيًا بـ `tags=["streamlit","multi-agent","mcp"]`
و `metadata` فيها الموديل والحدود المستخدمة — يعني في LangSmith هتقدر تفلتر
وتقارن بين runs مختلفة بسهولة.

## التشغيل بـ Docker (production-style)

```bash
docker compose up --build
```

ده هيشغل 3 حاويات: `ollama` (بورت 11434) + `mcp-server` (بورت 8000) +
`app` (Streamlit، بورت 8501). بعد ما يشتغلوا، حمّل الموديل جوه حاوية أوليama:

```bash
docker exec -it <container_name_ollama> ollama pull qwen2.5:3b
```

بعدين افتح `http://localhost:8501`.

> ملحوظة: جربت الـ YAML بتاع docker-compose وهو صحيح، لكن معنديش Docker
> daemon في بيئة التنفيذ بتاعتي عشان أعمل `docker compose up` فعليًا وأتأكد
> إنه بيشتغل end-to-end. جرّبه عندك وقولّي لو واجهت أي مشكلة في الـ networking
> بين الحاويات.

## الاختبارات

```bash
python tests/test_graph_mock.py            # منطق السوبرفايزر والحدود (بموديل وهمي)
python tests/test_integration_real_mcp.py  # graph.builder.build_graph() الحقيقية + سيرفر MCP حقيقي
python tests/test_streamlit_app.py         # الواجهة بتتحمل صح
python tests/test_streamlit_run_flow.py    # تدفق الضغط على الزرار كامل
```

كل الأربعة نجحوا في بيئة التطوير بتاعتي. `test_integration_real_mcp.py` هيوريك
تحذير إن `search_web` رجعت فاضية — ده بس لأن بيئة الاختبار بتاعتي محجوب عندها
الإنترنت العام؛ على جهازك هيرجع نتائج حقيقية.

## إيه اللي اتغيّر عن النسخة اللي كانت في النوتبوك

1. **تنظيم حقيقي**: من نوتبوك واحد لباكدج Python منظم (agents/, supervisor/,
   graph/, mcp_server/) — كل حاجة في مكانها وقابلة لإعادة الاستخدام والاختبار.
2. **أداة تانية حقيقية (`fetch_url`)**: الـ extraction agent بقى بيجيب محتوى
   الصفحات فعليًا مش بس بيلف على الـ snippets.
3. **LangSmith مربوط بشكل نضيف**: عن طريق environment variables بس، من غير
   أي كود إضافي في الـ graph نفسه — سهل تفعّله/تطفيه.
4. **واجهة Streamlit** كاملة: sidebar بالإعدادات، شريط تقدم حي لكل خطوة،
   عرض للمصادر المستخدمة (صفحة كاملة ولا snippet).
5. **تجهيز للـ production**: Dockerfiles + docker-compose لتشغيل الـ 3 خدمات
   مع بعض، `.env.example` لإدارة الإعدادات، واختبارات منفصلة لكل طبقة.

## الخطوات الجاية المقترحة (من الحوار اللي فات)

- Eval set حقيقي (20-50 سؤال) لقياس جودة الإجابات بمرور الوقت.
- Checkpointer دائم (Postgres بدل MemorySaver) لو هتشغل المشروع كـ خدمة طويلة المدى.
- حماية من prompt injection في محتوى الصفحات اللي بيجيبها `fetch_url` قبل ما تدخل الـ analysis prompt.
- Human-in-the-loop (`interrupt()` في LangGraph) لو ضفت أي tool له تأثير حقيقي (زي إرسال إيميل).
