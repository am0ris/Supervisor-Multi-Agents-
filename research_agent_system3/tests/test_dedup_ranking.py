import sys
import os
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jobs.schema import JobPosting, DateConfidence
from jobs.dedup import deduplicate_jobs, canonicalize_url
from jobs.ranking import rank_jobs, score_job
from jobs.date_utils import app_now


def test_canonicalize_url_strips_tracking_params():
    a = canonicalize_url("https://Example.com/jobs/123?utm_source=linkedin&ref=abc")
    b = canonicalize_url("https://example.com/jobs/123/")
    assert a == b, f"{a} != {b}"
    print("PASS: test_canonicalize_url_strips_tracking_params")


def test_dedup_exact_url_match():
    jobs = [
        JobPosting(title="AI Engineer", company="Acme", url="https://acme.com/jobs/1?utm_source=x", source="linkedin"),
        JobPosting(title="AI Engineer", company="Acme", url="https://acme.com/jobs/1", source="company_career_page"),
    ]
    result = deduplicate_jobs(jobs)
    assert len(result) == 1, f"expected 1 after dedup, got {len(result)}"
    # should keep the company_career_page version if it's more complete/reliable - here neither
    # is more "complete" by our completeness_score fields, so either is acceptable; just check count.
    print("PASS: test_dedup_exact_url_match")


def test_dedup_fuzzy_title_company_location_match():
    jobs = [
        JobPosting(title="Senior Generative AI Engineer", company="OpenAI Corp", location="Cairo, Egypt",
                   url="https://linkedin.com/jobs/1", source="linkedin"),
        JobPosting(title="Sr. Generative AI Engineer", company="OpenAI Corp", location="Cairo, Egypt",
                   url="https://indeed.com/jobs/999", source="indeed"),
    ]
    result = deduplicate_jobs(jobs)
    assert len(result) == 1, f"expected fuzzy dedup to merge these, got {len(result)}"
    print("PASS: test_dedup_fuzzy_title_company_location_match")


def test_dedup_different_companies_not_merged():
    jobs = [
        JobPosting(title="AI Engineer", company="Company A", location="Cairo", url="https://a.com/1", source="linkedin"),
        JobPosting(title="AI Engineer", company="Company B", location="Cairo", url="https://b.com/1", source="linkedin"),
    ]
    result = deduplicate_jobs(jobs)
    assert len(result) == 2, "different companies must never be merged as duplicates"
    print("PASS: test_dedup_different_companies_not_merged")


def test_dedup_keeps_more_complete_verified_entry():
    weak = JobPosting(title="AI Engineer", company="Acme", url="https://acme.com/jobs/1", source="linkedin",
                       date_verified=False)
    strong = JobPosting(title="AI Engineer", company="Acme", url="https://acme.com/jobs/1?ref=x", source="company_career_page",
                         date_verified=True, description="Full JD here", salary="$100k")
    result = deduplicate_jobs([weak, strong])
    assert len(result) == 1
    assert result[0].date_verified is True, "dedup must keep the more complete/verified entry"
    print("PASS: test_dedup_keeps_more_complete_verified_entry")


def test_ranking_prefers_verified_recent_reliable_source():
    now = app_now()
    recent_verified = JobPosting(
        title="Generative AI Engineer", company="Acme", location="Cairo, Egypt",
        url="https://acme.com/1", source="company_career_page",
        posted_date=(now - timedelta(days=1)).isoformat(),
        date_confidence=DateConfidence.PUBLISHED, date_verified=True,
    )
    old_unverified = JobPosting(
        title="Generative AI Engineer", company="Acme", location="Cairo, Egypt",
        url="https://acme.com/2", source="search_discovery",
        posted_date=None, date_confidence=DateConfidence.UNKNOWN, date_verified=False,
    )
    jobs = [old_unverified, recent_verified]
    ranked = rank_jobs(jobs, query="Generative AI Engineer", target_location="Cairo")

    assert ranked[0] is recent_verified, "verified recent job from a reliable source should rank first"
    assert ranked[0].relevance_score > ranked[1].relevance_score
    print("PASS: test_ranking_prefers_verified_recent_reliable_source")


def test_ranking_skill_match_affects_score():
    now = app_now()
    matches_skills = JobPosting(
        title="AI Engineer", company="Acme", url="https://acme.com/1", source="linkedin",
        required_skills=["Python", "LangChain", "RAG"],
    )
    no_skills_listed = JobPosting(
        title="AI Engineer", company="Acme", url="https://acme.com/2", source="linkedin",
        required_skills=[],
    )
    score_with = score_job(matches_skills, query="AI Engineer", required_skills=["python", "rag"])
    score_without = score_job(no_skills_listed, query="AI Engineer", required_skills=["python", "rag"])
    assert score_with > score_without
    print("PASS: test_ranking_skill_match_affects_score")


def test_ranking_is_deterministic():
    jobs = [
        JobPosting(title="AI Engineer", company="Acme", url="https://acme.com/1", source="linkedin"),
        JobPosting(title="ML Engineer", company="Acme", url="https://acme.com/2", source="linkedin"),
    ]
    r1 = rank_jobs(list(jobs), query="AI Engineer")
    r2 = rank_jobs(list(jobs), query="AI Engineer")
    assert [j.url for j in r1] == [j.url for j in r2], "ranking must be deterministic across runs"
    print("PASS: test_ranking_is_deterministic")


if __name__ == "__main__":
    test_canonicalize_url_strips_tracking_params()
    test_dedup_exact_url_match()
    test_dedup_fuzzy_title_company_location_match()
    test_dedup_different_companies_not_merged()
    test_dedup_keeps_more_complete_verified_entry()
    test_ranking_prefers_verified_recent_reliable_source()
    test_ranking_skill_match_affects_score()
    test_ranking_is_deterministic()
    print("\n✅ All dedup/ranking tests passed")
