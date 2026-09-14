"""
Query expansion for job search.

Deterministic and rule-based by design (not LLM-driven) so results are
reproducible and bounded. A curated synonym map covers common tech-role
families; expansion is capped by `max_queries` so a single request can't
explode into dozens of near-duplicate searches (which would hurt
relevance more than it helps recall).
"""
import re

# Curated synonym groups for common tech roles. Add more groups here as
# needed - this is the single place to extend role coverage.
_ROLE_SYNONYM_GROUPS: list[list[str]] = [
    ["generative ai engineer", "genai engineer", "llm engineer", "rag engineer",
     "ai engineer", "nlp engineer", "ai agent engineer"],
    ["machine learning engineer", "ml engineer", "mlops engineer"],
    ["data scientist", "applied scientist", "research scientist"],
    ["backend engineer", "backend developer", "server-side engineer"],
    ["frontend engineer", "frontend developer", "ui engineer"],
    ["full stack engineer", "full-stack developer", "fullstack engineer"],
    ["devops engineer", "site reliability engineer", "sre", "platform engineer"],
    ["data engineer", "etl engineer", "analytics engineer"],
]

_ROLE_LOOKUP: dict[str, list[str]] = {}
for group in _ROLE_SYNONYM_GROUPS:
    for role in group:
        _ROLE_LOOKUP[role] = group


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def find_role_synonyms(query: str) -> list[str]:
    """
    Returns the synonym group for any known role phrase found in the
    query, or an empty list if none matched. Matching is substring-based
    on normalized text, so "Generative AI Engineer jobs in Egypt" matches
    "generative ai engineer".
    """
    normalized = _normalize(query)
    for role, group in _ROLE_LOOKUP.items():
        if role in normalized:
            return group
    return []


def expand_query(query: str, max_queries: int = 4) -> list[str]:
    """
    Expands a single job-search query into a bounded list of related
    queries by substituting known role synonyms, while keeping any
    surrounding context (location, seniority, etc.) intact.

    Always includes the original query first. Never exceeds max_queries.
    """
    max_queries = max(1, max_queries)
    synonyms = find_role_synonyms(query)

    if not synonyms:
        return [query]

    normalized_query = _normalize(query)
    matched_role = next(r for r in synonyms if r in normalized_query)

    expanded = [query]
    for synonym in synonyms:
        if synonym == matched_role:
            continue
        if len(expanded) >= max_queries:
            break
        # Case-insensitive substitution that preserves the rest of the query.
        pattern = re.compile(re.escape(matched_role), re.IGNORECASE)
        new_query = pattern.sub(synonym, query, count=1)
        if new_query.lower() != query.lower():
            expanded.append(new_query)

    return expanded[:max_queries]
