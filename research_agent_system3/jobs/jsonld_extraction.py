"""
Deterministic extraction of schema.org JobPosting structured data
(JSON-LD) from a page's HTML. This is preferred over LLM-based extraction
whenever it's available, since it's exact - no risk of hallucinating
fields the LLM "infers" incorrectly.

Reference: https://schema.org/JobPosting
"""
import json
from bs4 import BeautifulSoup

from jobs.date_utils import classify_date
from jobs.schema import JobPosting


def _iter_jobposting_nodes(data):
    """JSON-LD can nest a JobPosting directly, in a list, or under @graph."""
    if isinstance(data, list):
        for item in data:
            yield from _iter_jobposting_nodes(item)
        return

    if not isinstance(data, dict):
        return

    node_type = data.get("@type")
    types = node_type if isinstance(node_type, list) else [node_type]
    if "JobPosting" in types:
        yield data

    if "@graph" in data:
        yield from _iter_jobposting_nodes(data["@graph"])


def extract_jsonld_jobpostings(html: str) -> list[dict]:
    """Returns a list of raw JobPosting JSON-LD dicts found in the page (possibly empty)."""
    soup = BeautifulSoup(html, "lxml")
    postings = []

    for script in soup.find_all("script", type="application/ld+json"):
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
        except (json.JSONDecodeError, TypeError):
            continue
        postings.extend(_iter_jobposting_nodes(data))

    return postings


def _extract_location(raw: dict) -> str | None:
    loc = raw.get("jobLocation")
    if isinstance(loc, list):
        loc = loc[0] if loc else None
    if not isinstance(loc, dict):
        return None
    address = loc.get("address")
    if isinstance(address, dict):
        parts = [
            address.get("addressLocality"),
            address.get("addressRegion"),
            address.get("addressCountry"),
        ]
        parts = [p for p in parts if p]
        return ", ".join(parts) if parts else None
    return None


def _extract_remote_type(raw: dict) -> str | None:
    if raw.get("jobLocationType") == "TELECOMMUTE":
        return "remote"
    return None


def _extract_salary(raw: dict) -> tuple[str | None, str | None]:
    salary = raw.get("baseSalary")
    if not isinstance(salary, dict):
        return None, None
    currency = salary.get("currency")
    value = salary.get("value")
    if isinstance(value, dict):
        min_v, max_v = value.get("minValue"), value.get("maxValue")
        if min_v and max_v:
            return f"{min_v}-{max_v}", currency
        single = value.get("value")
        if single:
            return str(single), currency
    elif value:
        return str(value), currency
    return None, currency


def jobposting_from_jsonld(raw: dict, url: str, source: str) -> JobPosting | None:
    """
    Converts a raw JSON-LD JobPosting dict into our normalized JobPosting
    schema. Returns None if the raw data doesn't even have a usable title
    (i.e. it's not really usable as a job posting).
    """
    title = raw.get("title")
    if not title:
        return None

    org = raw.get("hiringOrganization")
    company = org.get("name") if isinstance(org, dict) else (org if isinstance(org, str) else None)

    salary, currency = _extract_salary(raw)

    posted_date, confidence, verified = classify_date(
        published_raw=raw.get("datePosted"),
        updated_raw=raw.get("dateModified"),
        indexed_raw=None,
    )

    employment_type = raw.get("employmentType")
    if isinstance(employment_type, list):
        employment_type = employment_type[0] if employment_type else None

    return JobPosting(
        title=title,
        company=company,
        location=_extract_location(raw),
        remote_type=_extract_remote_type(raw),
        employment_type=employment_type,
        experience_level=raw.get("experienceRequirements") if isinstance(raw.get("experienceRequirements"), str) else None,
        salary=salary,
        currency=currency,
        posted_date=posted_date,
        updated_date=raw.get("dateModified"),
        application_deadline=raw.get("validThrough"),
        url=url,
        source=source,
        description=raw.get("description"),
        date_confidence=confidence,
        date_verified=verified,
    )
