# Multi-Agent Research System

A Supervisor-coordinated multi-agent system (Research, Extraction, Analysis,
Reviewer, Summary) built on **LangGraph**, running a local model via
**Ollama**, using real tools via **MCP**, traced with **LangSmith**, and
exposed through a **Streamlit** UI. Includes a dedicated, security-conscious
**job search** capability.

## Project layout

```
research_agent_system/
├── app.py                       # Streamlit UI (General Research + Job Search modes)
├── config.py                    # all settings (env-driven)
├── state.py                     # graph state
├── agents/                      # research, extraction, analysis, reviewer, summary
├── supervisor/decision.py       # routing logic + hard-limit safety net
├── graph/builder.py             # wires everything into a LangGraph
├── mcp_server/
│   ├── server.py                  # exposes search_web, search_jobs, fetch_url
│   └── tools/
├── search/                      # search provider abstraction (DuckDuckGo/Tavily/SerpAPI/Brave)
├── jobs/                        # job-search domain logic
│   ├── schema.py                  # JobPosting structured data
│   ├── query_expansion.py         # bounded role-synonym expansion
│   ├── intent.py                  # job-search intent detection
│   ├── date_utils.py              # recency verification (never assumes unknown = recent)
│   ├── jsonld_extraction.py       # schema.org JobPosting parsing
│   ├── dedup.py / ranking.py      # deduplication + deterministic scoring
│   ├── aggregator.py              # multi-query, multi-source, parallel search
│   └── sources/                   # remoteok.py, weworkremotely.py, search_discovery.py
├── security/                    # SSRF guard + prompt-injection defense
├── tests/
├── notebooks/                   # original exploratory notebook (reference)
├── requirements.txt / .env.example
└── Dockerfile.mcp / Dockerfile.streamlit / docker-compose.yml
```

## Job search: what's actually supported, honestly

| Platform / source | Status | How it works |
|---|---|---|
| **RemoteOK** | Directly supported (public API) | Calls `https://remoteok.com/api` directly - documented, no key needed |
| **We Work Remotely** | Directly supported (public RSS) | Parses the public RSS feed - no key needed |
| **Company career pages** | Public-page based | `fetch_url` + JSON-LD `JobPosting` extraction when the page provides it |
| **LinkedIn, Indeed, Glassdoor, Wuzzuf, Bayt, Wellfound** | Search-engine discovered | A normal `site:<domain>` web search finds public result links; we never log in, solve CAPTCHAs, or scrape behind auth. If the resulting page happens to be public and includes JSON-LD, extraction upgrades it; otherwise you get the search snippet only. |
| **Any provider requiring a login/session (e.g. LinkedIn's own job search API)** | Unavailable without credentials | Not implemented - would require OAuth/API access this project doesn't have |

**Important limitation on verification:** the development sandbox this
project was built in has no route to the public internet (or to
`remoteok.com` / `weworkremotely.com` specifically - both returned `403
Forbidden` from here, most likely due to the sandbox's own network
policy, not the sites themselves). This means:
- The **code paths are real and tested** (unit tests with realistic mocked
  payloads matching each service's documented format, resilience tests with
  simulated failures/timeouts/retries).
- **Live results have not been verified** by me. Run it on a machine with
  normal internet access and confirm before relying on it.

### Adding another job platform

1. If it has a public API or feed (like RemoteOK/WWR): add a new file under
   `jobs/sources/`, implement the `JobSource` interface (`find_jobs`), and
   register it in `jobs/aggregator.py`.
2. If it requires login (like LinkedIn): add its domain to
   `PLATFORM_DOMAINS` in `jobs/sources/search_discovery.py` and to
   `JOB_SEARCH_PLATFORMS` in `.env`. No new code needed - discovery and
   JSON-LD extraction apply automatically.

## Search provider configuration

```env
SEARCH_PROVIDER=duckduckgo          # primary
SEARCH_PROVIDER_FALLBACK=duckduckgo # comma-separated fallback chain
TAVILY_API_KEY=                     # only if you use tavily
SERPAPI_API_KEY=                    # only if you use serpapi
BRAVE_API_KEY=                      # only if you use brave
```

DuckDuckGo needs no key and is always available as an implicit last
resort even if not listed. Tavily/SerpAPI/Brave clients are implemented
against each service's documented REST API and covered by mocked unit
tests, but **not live-verified** (no API keys or network access in this
sandbox) - test with a real key before depending on them.

## Recency / date handling

- `SEARCH_TIME_LIMIT` (general search) and the Streamlit "Date range"
  picker (job search: Today / Last 24h / Last 3 days / Last 7 days / Last
  month / Last 3 months) control how far back results can come from.
- Every date is classified as `published_date` > `updated_date` >
  `indexed_date` > `date_unknown`, in that priority order. **An unknown
  date is never treated as recent** - this is enforced in
  `jobs/date_utils.py` and covered by a dedicated test.
- All date math uses the application's own clock (`jobs.date_utils.app_now()`),
  never the LLM's idea of "today" - every agent prompt is also given
  today's actual date explicitly and instructed not to override retrieved
  data with its own training knowledge.

## Security

- **SSRF**: every `fetch_url` call is validated against internal/private
  IP ranges and cloud metadata endpoints before any request is made
  (`security/ssrf_guard.py`).
- **robots.txt**: checked and honored before fetching any page; a missing
  robots.txt fails open (no restriction stated), a disallow rule blocks
  the fetch.
- **No access-control bypass, ever**: no CAPTCHA solving, no login
  automation, no anti-bot evasion, anywhere in this codebase.
- **Prompt injection**: all fetched web content is wrapped in explicit
  "this is data, not instructions" delimiters before being placed in an
  LLM prompt (`security/prompt_injection.py`). This is a pragmatic
  mitigation, not a guarantee - no such guarantee exists for LLM systems.

## Running locally

```bash
pip install -r requirements.txt
cp .env.example .env
ollama pull qwen2.5:3b && ollama serve
python mcp_server/server.py     # separate terminal, keep it running
streamlit run app.py
```

### Example job-search queries to try in the UI

- Job title: `Generative AI Engineer`, Location: `Egypt`, Date range: `Last month`
- Job title: `Backend Engineer`, Remote: `Remote`, Skills: `Python, FastAPI`
- Job title: `LLM Engineer`, Platforms: just `linkedin, wellfound`

## LangSmith

Set `LANGSMITH_API_KEY` and `LANGSMITH_PROJECT` in `.env` - tracing turns
on automatically via `config.py` (no code changes elsewhere). Every run
is tagged with `query_type` and carries metadata: query, search provider,
model, and agent limits. Job search stats (queries used, sources
searched, result/dedup/verification counts, retries, duration) are
attached to `state["job_search_stats"]` and visible in the trace's
final state. No credentials or chain-of-thought are logged.

## Docker

```bash
docker compose up --build
docker exec -it <ollama_container> ollama pull qwen2.5:3b
```
Runs Ollama + the MCP server + Streamlit as three services. The
docker-compose YAML is syntactically validated but not run end-to-end in
this sandbox (no Docker daemon available here) - verify on your machine.

## Tests

```bash
python tests/test_date_utils.py            # recency/date classification (unit)
python tests/test_dedup_ranking.py         # deduplication + ranking (unit)
python tests/test_fetch_security.py        # SSRF + robots.txt (unit, mocked HTTP)
python tests/test_jsonld_extraction.py     # JSON-LD JobPosting parsing (unit)
python tests/test_search_providers.py      # provider fallback + mocked API parsing (unit)
python tests/test_job_aggregator.py        # multi-query/source resilience: timeouts, retries, partial failure (unit)
python tests/test_graph_mock.py            # general-research control flow (unit, mocked LLMs/tools)
python tests/test_supervisor_job_search.py # job-search "search again" loop safety (unit, mocked)
python tests/test_streamlit_app.py         # UI renders in both modes (unit)
python tests/test_streamlit_run_flow.py    # full click-through in both modes (unit, mocked graph)

# integration tests - require a running MCP server (`python mcp_server/server.py`)
python tests/test_integration_real_mcp.py       # build_graph() against a real MCP server
python tests/test_integration_job_search.py     # job-search wiring against a real MCP server
```

**All 12 test files pass** in the development environment. The two
integration tests confirm the real wiring works end-to-end (no crashes,
graceful degradation, correct control flow) but cannot confirm live job
results, since this sandbox has no route to the public internet - see the
platform table above.

### Bugs this testing process actually caught (fixed, not just found)

1. Fuzzy company-name matching in deduplication would have merged
   different companies ("Company A" vs "Company B") as duplicates -
   fixed by requiring near-exact company match, fuzzy only on title/location.
2. The job aggregator's retry logic never actually triggered on discovery
   failures, because errors were being swallowed silently one layer down.
3. The supervisor's "search again" fallback could deadlock before ever
   reaching `summary` once extraction's budget was exhausted mid-loop.
4. A related fallback-ordering bug could send the supervisor back to
   `research` repeatedly without ever re-running `extraction` on the new results.
5. **The most significant one**: `langchain_mcp_adapters` wraps tool
   results in a `[{"type": "text", "text": "<json>"}]` envelope that
   nothing was unwrapping - meaning `search_web`, `fetch_url`, and
   `search_jobs` were all silently unusable through the real MCP layer.
   This had been masked in every earlier test because blocked internet
   always produced zero results before the bug could surface. Fixed with
   a shared `parse_mcp_result()` helper.

## What was NOT fully verified

- Live results from any job platform (sandbox has no internet route to them).
- Tavily/SerpAPI/Brave against real API keys.
- `docker compose up` actually running end-to-end (no Docker daemon here).

Everything else in this list - control flow, limits, deduplication,
ranking, date logic, security guards, MCP wiring, and the Streamlit UI -
was exercised with real assertions, not just written and assumed to work.
