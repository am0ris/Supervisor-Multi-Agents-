"""
Central configuration.

كل حاجة قابلة للتغيير بتتظبط هنا أو من environment variables - عشان
مانلمسش الكود لما نغير موديل أو حد أو نفعّل/نطفي LangSmith.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------- models
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# ---------------------------------------------------------------- MCP
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8000/mcp")

# ---------------------------------------------------------------- limits
AGENT_LIMITS = {
    "research": int(os.getenv("LIMIT_RESEARCH", 3)),
    "extraction": int(os.getenv("LIMIT_EXTRACTION", 1)),
    "analysis": int(os.getenv("LIMIT_ANALYSIS", 2)),
    "reviewer": int(os.getenv("LIMIT_REVIEWER", 2)),
    "summary": int(os.getenv("LIMIT_SUMMARY", 1)),
}

MAX_TOTAL_STEPS = int(os.getenv("MAX_TOTAL_STEPS", 20))
MAX_SEARCH_RESULTS = int(os.getenv("MAX_SEARCH_RESULTS", 5))
MAX_DOCUMENTS = int(os.getenv("MAX_DOCUMENTS", 3))
MAX_FETCH_CHARS = int(os.getenv("MAX_FETCH_CHARS", 4000))  # حد لحجم أي صفحة نجيبها بالكامل

# ---------------------------------------------------------------- LangSmith
# LangChain/LangGraph بيقرأ الـ env vars دي تلقائيًا - مفيش أي كود إضافي
# مطلوب في الـ graph نفسه. لو LANGSMITH_API_KEY مش موجود، التتبع
# بيتقفل تلقائيًا من غير ما المشروع يعطل.
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "multi-agent-research")

if LANGSMITH_API_KEY:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = LANGSMITH_API_KEY
    os.environ["LANGCHAIN_PROJECT"] = LANGSMITH_PROJECT
    LANGSMITH_ENABLED = True
else:
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    LANGSMITH_ENABLED = False
