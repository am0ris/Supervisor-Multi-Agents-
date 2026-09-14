"""
Date parsing and classification for job postings.

The application's own clock (`app_now()`) is always the source of truth
for "today" — never the LLM's idea of the current date, which reflects
its training cutoff and can be badly wrong. Every date-related decision
in the system should go through this module.
"""
from datetime import datetime, timezone
from dateutil import parser as dateutil_parser
from dateutil.relativedelta import relativedelta

from jobs.schema import DateConfidence


def app_now() -> datetime:
    """The application's actual current time (UTC). Always use this, never LLM output."""
    return datetime.now(timezone.utc)


def parse_date_safe(raw: str | None) -> datetime | None:
    """
    Parses a date string into a timezone-aware UTC datetime. Returns None
    if it can't be parsed - callers must treat that as unknown, not as
    "today".
    """
    if not raw or not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = dateutil_parser.parse(raw, fuzzy=True)
    except (ValueError, OverflowError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def classify_date(
    published_raw: str | None = None,
    updated_raw: str | None = None,
    indexed_raw: str | None = None,
) -> tuple[str | None, DateConfidence, bool]:
    """
    Given whatever date signals were found for a job posting, decides
    which one to trust and how confident we are in it.

    Returns (iso_date_or_none, DateConfidence, date_verified).

    Priority: an explicit published date beats an "updated" date, which
    beats a search engine's index date, which beats nothing at all. A
    date is only marked `date_verified=True` when it came from an
    explicit published/updated signal (i.e. NOT merely the index date).
    """
    published = parse_date_safe(published_raw)
    if published:
        return published.isoformat(), DateConfidence.PUBLISHED, True

    updated = parse_date_safe(updated_raw)
    if updated:
        return updated.isoformat(), DateConfidence.UPDATED, True

    indexed = parse_date_safe(indexed_raw)
    if indexed:
        return indexed.isoformat(), DateConfidence.INDEXED, False

    return None, DateConfidence.UNKNOWN, False


def is_within_recency_window(iso_date: str | None, timelimit: str | None, now: datetime | None = None) -> bool | None:
    """
    Checks whether a date falls within a recency window ("d"/"w"/"m"/"y").

    Returns:
        True  - date is known and within the window
        False - date is known and OUTSIDE the window
        None  - date is unknown, so recency can't be determined (caller
                must NOT treat this as "recent" - see module docstring)
    """
    if not timelimit:
        return True if iso_date else None

    if not iso_date:
        return None

    date = parse_date_safe(iso_date)
    if date is None:
        return None

    now = now or app_now()
    deltas = {
        "d": relativedelta(days=1),
        "w": relativedelta(weeks=1),
        "m": relativedelta(months=1),
        "y": relativedelta(years=1),
    }
    delta = deltas.get(timelimit)
    if delta is None:
        return None

    cutoff = now - delta
    return date >= cutoff


# Human-friendly recency window labels, used by the UI / query layer to
# map a user-facing choice ("Last 3 days") to a timelimit-like window.
# ddgs/most providers only support single-letter codes (d/w/m/y) natively,
# so finer windows are approximated with the nearest code and then
# double-checked precisely via `is_within_recency_window` using the
# extracted date (not just the provider's coarse filter).
RECENCY_LABEL_TO_TIMELIMIT = {
    "today": "d",
    "last_24_hours": "d",
    "last_3_days": "w",   # approximate at the provider level; refined via extracted dates
    "last_7_days": "w",
    "last_month": "m",
    "last_3_months": "m",  # approximate; providers don't support quarter windows natively
}

RECENCY_LABEL_TO_DAYS = {
    "today": 1,
    "last_24_hours": 1,
    "last_3_days": 3,
    "last_7_days": 7,
    "last_month": 30,
    "last_3_months": 90,
}


def is_within_days(iso_date: str | None, max_days: int | None, now: datetime | None = None) -> bool | None:
    """Precise day-based recency check, used to refine the coarse provider-level timelimit."""
    if max_days is None:
        return True if iso_date else None
    if not iso_date:
        return None
    date = parse_date_safe(iso_date)
    if date is None:
        return None
    now = now or app_now()
    return (now - date).days <= max_days
