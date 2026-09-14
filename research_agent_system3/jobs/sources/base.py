"""Common interface for job sources (a platform-specific way of finding jobs)."""
from abc import ABC, abstractmethod

from jobs.schema import JobPosting


class JobSourceError(Exception):
    """Raised when a job source fails. One source failing must never fail the whole search."""


class JobSource(ABC):
    name: str = "base"

    @abstractmethod
    async def find_jobs(self, query: str, max_results: int = 10, **kwargs) -> list[JobPosting]:
        raise NotImplementedError
