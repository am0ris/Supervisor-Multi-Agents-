import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jobs.jsonld_extraction import extract_jsonld_jobpostings, jobposting_from_jsonld
from jobs.schema import DateConfidence

SAMPLE_HTML_SINGLE = """
<html><head>
<script type="application/ld+json">
{
  "@context": "https://schema.org/",
  "@type": "JobPosting",
  "title": "Generative AI Engineer",
  "description": "Build LLM-powered products.",
  "datePosted": "2026-09-05",
  "validThrough": "2026-10-05",
  "employmentType": "FULL_TIME",
  "hiringOrganization": {
    "@type": "Organization",
    "name": "Acme AI"
  },
  "jobLocation": {
    "@type": "Place",
    "address": {
      "@type": "PostalAddress",
      "addressLocality": "Cairo",
      "addressCountry": "EG"
    }
  },
  "baseSalary": {
    "@type": "MonetaryAmount",
    "currency": "USD",
    "value": {
      "@type": "QuantitativeValue",
      "minValue": 60000,
      "maxValue": 90000
    }
  }
}
</script>
</head><body></body></html>
"""

SAMPLE_HTML_GRAPH = """
<html><head>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@graph": [
    {"@type": "WebPage", "name": "Careers"},
    {
      "@type": "JobPosting",
      "title": "Remote NLP Engineer",
      "hiringOrganization": {"name": "RemoteCo"},
      "jobLocationType": "TELECOMMUTE",
      "datePosted": "2026-08-01"
    }
  ]
}
</script>
</head><body></body></html>
"""

SAMPLE_HTML_NO_JOBPOSTING = """
<html><head>
<script type="application/ld+json">
{"@type": "Organization", "name": "Just a company page"}
</script>
</head><body></body></html>
"""

SAMPLE_HTML_MALFORMED = """
<html><head>
<script type="application/ld+json">
{ not valid json !!! }
</script>
</head><body></body></html>
"""


def test_extract_single_jobposting():
    nodes = extract_jsonld_jobpostings(SAMPLE_HTML_SINGLE)
    assert len(nodes) == 1
    job = jobposting_from_jsonld(nodes[0], url="https://acme.com/jobs/1", source="company_career_page")
    assert job is not None
    assert job.title == "Generative AI Engineer"
    assert job.company == "Acme AI"
    assert job.location == "Cairo, EG"
    assert job.salary == "60000-90000"
    assert job.currency == "USD"
    assert job.date_confidence == DateConfidence.PUBLISHED
    assert job.date_verified is True
    assert job.posted_date.startswith("2026-09-05")
    assert job.application_deadline == "2026-10-05"
    print("PASS: test_extract_single_jobposting")


def test_extract_jobposting_from_graph_and_remote_type():
    nodes = extract_jsonld_jobpostings(SAMPLE_HTML_GRAPH)
    assert len(nodes) == 1
    job = jobposting_from_jsonld(nodes[0], url="https://remoteco.com/jobs/2", source="company_career_page")
    assert job.title == "Remote NLP Engineer"
    assert job.remote_type == "remote"
    assert job.company == "RemoteCo"
    print("PASS: test_extract_jobposting_from_graph_and_remote_type")


def test_no_jobposting_present_returns_empty():
    nodes = extract_jsonld_jobpostings(SAMPLE_HTML_NO_JOBPOSTING)
    assert nodes == []
    print("PASS: test_no_jobposting_present_returns_empty")


def test_malformed_jsonld_does_not_crash():
    nodes = extract_jsonld_jobpostings(SAMPLE_HTML_MALFORMED)
    assert nodes == [], "malformed JSON-LD must be skipped, not raise"
    print("PASS: test_malformed_jsonld_does_not_crash")


def test_missing_title_returns_none():
    job = jobposting_from_jsonld({"@type": "JobPosting", "company": "X"}, url="https://x.com", source="x")
    assert job is None
    print("PASS: test_missing_title_returns_none")


def test_no_date_at_all_is_unknown_not_assumed_recent():
    raw = {"@type": "JobPosting", "title": "AI Engineer", "hiringOrganization": {"name": "X"}}
    job = jobposting_from_jsonld(raw, url="https://x.com", source="x")
    assert job.date_confidence == DateConfidence.UNKNOWN
    assert job.date_verified is False
    assert job.posted_date is None
    print("PASS: test_no_date_at_all_is_unknown_not_assumed_recent")


if __name__ == "__main__":
    test_extract_single_jobposting()
    test_extract_jobposting_from_graph_and_remote_type()
    test_no_jobposting_present_returns_empty()
    test_malformed_jsonld_does_not_crash()
    test_missing_title_returns_none()
    test_no_date_at_all_is_unknown_not_assumed_recent()
    print("\n✅ All JSON-LD extraction tests passed")
