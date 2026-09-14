"""
Central configuration.

Everything configurable lives here or in environment variables, so we
never have to touch code to change a model, a limit, or a search
provider.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------- models
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# ---------------------------------------------------------------- MCP
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8000/mcp")

# ---------------------------------------------------------------- agent limits
# Hard caps on how many times each agent may run in a single request.
# These are the primary safety mechanism against infinite loops.
AGENT_LIMITS = {
    "research": int(os.getenv("LIMIT_RESEARCH", 3)),
    "extraction": int(os.getenv("LIMIT_EXTRACTION", 2)),
    "analysis": int(os.getenv("LIMIT_ANALYSIS", 2)),
    "reviewer": int(os.getenv("LIMIT_REVIEWER", 2)),
    "summary": int(os.getenv("LIMIT_SUMMARY", 1)),
}

MAX_TOTAL_STEPS = int(os.getenv("MAX_TOTAL_STEPS", 20))

# ---------------------------------------------------------------- general search
MAX_SEARCH_RESULTS = int(os.getenv("MAX_SEARCH_RESULTS", 5))
# Recency filter for general (non-job) search: d=day, w=week, m=month,
# y=year, ""=no filter. Without this, search engines rank by popularity,
# not freshness, and can surface year-old pages for "latest" queries.
SEARCH_TIME_LIMIT = os.getenv("SEARCH_TIME_LIMIT", "y")
MAX_DOCUMENTS = int(os.getenv("MAX_DOCUMENTS", 3))
MAX_FETCH_CHARS = int(os.getenv("MAX_FETCH_CHARS", 4000))

# ---------------------------------------------------------------- search provider
# Primary provider + comma-separated fallback chain. Any provider that is
# unconfigured (missing API key) or fails at request time is skipped in
# favor of the next one; DuckDuckGo is always available as a last resort
# since it needs no key.
SEARCH_PROVIDER = os.getenv("SEARCH_PROVIDER", "duckduckgo")
SEARCH_PROVIDER_FALLBACK = os.getenv("SEARCH_PROVIDER_FALLBACK", "duckduckgo")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY")

# ---------------------------------------------------------------- job search
JOB_SEARCH_ENABLED = os.getenv("JOB_SEARCH_ENABLED", "true").lower() == "true"
MAX_SEARCH_QUERIES = int(os.getenv("MAX_SEARCH_QUERIES", 4))
MAX_RESULTS_PER_SOURCE = int(os.getenv("MAX_RESULTS_PER_SOURCE", 5))
MAX_TOTAL_RESULTS = int(os.getenv("MAX_TOTAL_RESULTS", 30))
MAX_CONCURRENT_SEARCHES = int(os.getenv("MAX_CONCURRENT_SEARCHES", 5))
SEARCH_TIMEOUT = float(os.getenv("SEARCH_TIMEOUT", 15.0))
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", 10.0))
SEARCH_RETRIES = int(os.getenv("SEARCH_RETRIES", 1))

JOB_SEARCH_PLATFORMS = [
    p.strip() for p in os.getenv(
        "JOB_SEARCH_PLATFORMS", "linkedin,indeed,wuzzuf,glassdoor,bayt,wellfound"
    ).split(",") if p.strip()
]

# ---------------------------------------------------------------- LangSmith
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
