from __future__ import annotations

from .base import Fetcher, JobPosting

API_URL = "https://remotive.com/api/remote-jobs"


class RemotiveFetcher(Fetcher):
    """Remotive's public JSON API. No key required, generous rate limits.
    Docs: https://remotive.com/api/remote-jobs
    """

    name = "remotive"

    def __init__(self, category: str | None = None, search: str | None = None):
        self.category = category
        self.search = search

    def fetch(self) -> list[JobPosting]:
        params = {}
        if self.category:
            params["category"] = self.category
        if self.search:
            params["search"] = self.search

        data = self._get(API_URL, params=params).json()
        postings = []
        for job in data.get("jobs", []):
            postings.append(
                JobPosting(
                    source=self.name,
                    title=job.get("title", ""),
                    company=job.get("company_name", ""),
                    location=job.get("candidate_required_location", ""),
                    url=job.get("url", ""),
                    description=self._strip_html(job.get("description", "")),
                    posted_at=job.get("publication_date"),
                    raw=job,
                )
            )
        return postings
