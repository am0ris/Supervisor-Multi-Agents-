"""
RemoteOK job source. Uses RemoteOK's public JSON API
(https://remoteok.com/api), which requires no authentication and is
documented/intended for this kind of programmatic access.

Not live-verified in the development sandbox: the sandbox's network
allowlist does not include remoteok.com. The parsing logic follows
RemoteOK's known response schema and is covered by a unit test using a
realistic mocked payload - verify against the live API before relying on
it in production.
"""
import httpx

from jobs.date_utils import classify_date
from jobs.schema import JobPosting
from jobs.sources.base import JobSource, JobSourceError

REMOTEOK_API_URL = "https://remoteok.com/api"

# RemoteOK asks API consumers to identify themselves with a real User-Agent.
_HEADERS = {"User-Agent": "MultiAgentResearchSystem/1.0 (job-search feature)"}


class RemoteOkSource(JobSource):
    name = "remoteok"

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    async def find_jobs(self, query: str, max_results: int = 10, **kwargs) -> list[JobPosting]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=_HEADERS) as client:
                resp = await client.get(REMOTEOK_API_URL)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as e:
            raise JobSourceError(f"RemoteOK request failed: {e}") from e
        except ValueError as e:
            raise JobSourceError(f"RemoteOK returned invalid JSON: {e}") from e

        query_lower = query.lower()
        jobs = []
        for entry in data:
            # The first element of RemoteOK's response is a legal/metadata
            # notice, not a job - skip anything without a position/company.
            if not isinstance(entry, dict) or "position" not in entry or "company" not in entry:
                continue

            searchable_text = " ".join(
                [entry.get("position", ""), " ".join(entry.get("tags", []) or [])]
            ).lower()
            if query_lower and query_lower not in searchable_text and not any(
                word in searchable_text for word in query_lower.split() if len(word) > 2
            ):
                continue

            posted_date, confidence, verified = classify_date(published_raw=entry.get("date"))

            jobs.append(
                JobPosting(
                    title=entry.get("position", ""),
                    company=entry.get("company"),
                    location=entry.get("location") or "Remote",
                    remote_type="remote",
                    employment_type=None,
                    required_skills=list(entry.get("tags") or []),
                    salary=(
                        f"{entry.get('salary_min')}-{entry.get('salary_max')}"
                        if entry.get("salary_min") and entry.get("salary_max")
                        else None
                    ),
                    posted_date=posted_date,
                    url=entry.get("url") or entry.get("apply_url", ""),
                    source=self.name,
                    description=entry.get("description"),
                    date_confidence=confidence,
                    date_verified=verified,
                )
            )
            if len(jobs) >= max_results:
                break

        return jobs
