"""
We Work Remotely job source. Uses WWR's public RSS feeds, which require
no authentication - RSS is explicitly published for consumption.

Not live-verified in the development sandbox: the sandbox's network
allowlist does not include weworkremotely.com. The parsing logic follows
WWR's known RSS format (title = "Company: Job Title") and is covered by
a unit test using a realistic mocked feed - verify against the live feed
before relying on it in production.
"""
import xml.etree.ElementTree as ET

import httpx

from jobs.date_utils import classify_date
from jobs.schema import JobPosting
from jobs.sources.base import JobSource, JobSourceError

WWR_FEED_URL = "https://weworkremotely.com/categories/remote-programming-jobs.rss"


def parse_wwr_rss(xml_text: str, source_name: str = "weworkremotely") -> list[JobPosting]:
    """Parses a WWR RSS feed's XML text into JobPosting objects. Pure
    function so it can be unit-tested without any network access."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise JobSourceError(f"Could not parse WWR RSS feed: {e}") from e

    jobs = []
    for item in root.findall(".//item"):
        raw_title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        description = (item.findtext("description") or "").strip()

        # WWR titles are formatted as "Company: Job Title".
        if ":" in raw_title:
            company, _, title = raw_title.partition(":")
            company, title = company.strip(), title.strip()
        else:
            company, title = None, raw_title

        if not title or not link:
            continue

        posted_date, confidence, verified = classify_date(published_raw=pub_date)

        jobs.append(
            JobPosting(
                title=title,
                company=company,
                location="Remote",
                remote_type="remote",
                posted_date=posted_date,
                url=link,
                source=source_name,
                description=description or None,
                date_confidence=confidence,
                date_verified=verified,
            )
        )
    return jobs


class WeWorkRemotelySource(JobSource):
    name = "weworkremotely"

    def __init__(self, timeout: float = 10.0, feed_url: str = WWR_FEED_URL):
        self.timeout = timeout
        self.feed_url = feed_url

    async def find_jobs(self, query: str, max_results: int = 10, **kwargs) -> list[JobPosting]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(self.feed_url)
                resp.raise_for_status()
        except httpx.HTTPError as e:
            raise JobSourceError(f"WeWorkRemotely feed request failed: {e}") from e

        all_jobs = parse_wwr_rss(resp.text, source_name=self.name)

        query_lower = query.lower()
        matched = [
            j for j in all_jobs
            if not query_lower
            or query_lower in j.title.lower()
            or any(word in j.title.lower() for word in query_lower.split() if len(word) > 2)
        ]
        return matched[:max_results]
