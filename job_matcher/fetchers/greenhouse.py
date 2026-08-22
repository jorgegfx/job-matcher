from __future__ import annotations

from .base import Fetcher, JobPosting

API_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"


class GreenhouseFetcher(Fetcher):
    """Any company using Greenhouse exposes a free public JSON API at
    boards-api.greenhouse.io/v1/boards/<token>/jobs. No key required.
    Find <token> in the company's careers URL (boards.greenhouse.io/<token>).
    """

    name = "greenhouse"

    def __init__(self, company_tokens: list[str]):
        self.company_tokens = company_tokens

    def fetch(self) -> list[JobPosting]:
        postings: list[JobPosting] = []
        for token in self.company_tokens:
            try:
                data = self._get(
                    API_URL.format(token=token), params={"content": "true"}
                ).json()
            except Exception:
                # A bad/renamed token shouldn't kill the whole run.
                continue

            for job in data.get("jobs", []):
                location = (job.get("location") or {}).get("name", "")
                postings.append(
                    JobPosting(
                        source=f"greenhouse:{token}",
                        title=job.get("title", ""),
                        company=token,
                        location=location,
                        url=job.get("absolute_url", ""),
                        description=self._strip_html(job.get("content", "")),
                        posted_at=job.get("updated_at"),
                        raw=job,
                    )
                )
        return postings
