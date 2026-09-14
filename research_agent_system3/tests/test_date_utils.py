import sys
import os
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jobs.date_utils import (
    parse_date_safe, classify_date, is_within_recency_window, is_within_days, app_now
)
from jobs.schema import DateConfidence


def test_parse_date_safe_valid():
    d = parse_date_safe("2026-09-01")
    assert d is not None
    assert d.year == 2026 and d.month == 9 and d.day == 1
    print("PASS: test_parse_date_safe_valid")


def test_parse_date_safe_invalid_returns_none():
    assert parse_date_safe(None) is None
    assert parse_date_safe("") is None
    assert parse_date_safe("not a date at all !!!") is None
    print("PASS: test_parse_date_safe_invalid_returns_none")


def test_classify_date_prefers_published_over_updated():
    iso, confidence, verified = classify_date(
        published_raw="2026-09-01", updated_raw="2026-09-05", indexed_raw="2026-09-10"
    )
    assert confidence == DateConfidence.PUBLISHED
    assert verified is True
    assert "2026-09-01" in iso
    print("PASS: test_classify_date_prefers_published_over_updated")


def test_classify_date_falls_back_to_updated():
    iso, confidence, verified = classify_date(published_raw=None, updated_raw="2026-09-05", indexed_raw="2026-09-10")
    assert confidence == DateConfidence.UPDATED
    assert verified is True
    print("PASS: test_classify_date_falls_back_to_updated")


def test_classify_date_falls_back_to_indexed_and_is_not_verified():
    iso, confidence, verified = classify_date(published_raw=None, updated_raw=None, indexed_raw="2026-09-10")
    assert confidence == DateConfidence.INDEXED
    assert verified is False, "indexed-only dates must NOT be marked as verified"
    print("PASS: test_classify_date_falls_back_to_indexed_and_is_not_verified")


def test_classify_date_all_missing_is_unknown():
    iso, confidence, verified = classify_date(None, None, None)
    assert iso is None
    assert confidence == DateConfidence.UNKNOWN
    assert verified is False
    print("PASS: test_classify_date_all_missing_is_unknown")


def test_unknown_date_never_treated_as_recent():
    # This is the critical safety property from the spec: an unverified/
    # unknown date must NEVER be assumed to be within a recency window.
    result = is_within_recency_window(iso_date=None, timelimit="w")
    assert result is None, "unknown date must return None, not True"
    print("PASS: test_unknown_date_never_treated_as_recent")


def test_recent_date_within_window():
    now = app_now()
    recent = (now - timedelta(days=2)).isoformat()
    assert is_within_recency_window(recent, timelimit="w", now=now) is True
    print("PASS: test_recent_date_within_window")


def test_old_date_outside_window():
    now = app_now()
    old = (now - timedelta(days=400)).isoformat()
    assert is_within_recency_window(old, timelimit="w", now=now) is False
    assert is_within_recency_window(old, timelimit="y", now=now) is False
    print("PASS: test_old_date_outside_window")


def test_is_within_days_precise_windows():
    now = app_now()
    three_days_ago = (now - timedelta(days=3)).isoformat()
    ten_days_ago = (now - timedelta(days=10)).isoformat()

    assert is_within_days(three_days_ago, max_days=7, now=now) is True
    assert is_within_days(ten_days_ago, max_days=7, now=now) is False
    assert is_within_days(None, max_days=7, now=now) is None
    print("PASS: test_is_within_days_precise_windows")


def test_app_now_is_not_llm_dependent():
    # app_now() must reflect the real system clock, not any hardcoded or
    # LLM-suggested date. We just check it's within a sane range of the
    # actual OS clock at test time.
    now = app_now()
    real_now = datetime.now(timezone.utc)
    assert abs((now - real_now).total_seconds()) < 5
    print("PASS: test_app_now_is_not_llm_dependent")


if __name__ == "__main__":
    test_parse_date_safe_valid()
    test_parse_date_safe_invalid_returns_none()
    test_classify_date_prefers_published_over_updated()
    test_classify_date_falls_back_to_updated()
    test_classify_date_falls_back_to_indexed_and_is_not_verified()
    test_classify_date_all_missing_is_unknown()
    test_unknown_date_never_treated_as_recent()
    test_recent_date_within_window()
    test_old_date_outside_window()
    test_is_within_days_precise_windows()
    test_app_now_is_not_llm_dependent()
    print("\n✅ All date utility tests passed")
