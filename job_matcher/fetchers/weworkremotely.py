from __future__ import annotations

import feedparser

from .base import Fetcher, JobPosting


class WeWorkRemotelyFetcher(Fetcher):
    """We Work Remotely publishes free RSS feeds per category, no key needed.
    e.g. https://weworkremotely.com/categories/remote-programming-jobs.rss
    """

    name = "weworkremotely"

    def __init__(self, feed_urls: list[str]):
        self.feed_urls = feed_urls

    def fetch(self) -> list[JobPosting]:
        postings: list[JobPosting] = []
        for feed_url in self.feed_urls:
            parsed = feedparser.parse(feed_url)
            for entry in parsed.entries:
                title = entry.get("title", "")
                company = ""
                # WWR titles are typically "Company: Job Title"
                if ":" in title:
                    company, _, title_rest = title.partition(":")
                    title = title_rest.strip()
                    company = company.strip()

                postings.append(
                    JobPosting(
                        source=self.name,
                        title=title,
                        company=company,
                        location=entry.get("weworkremotely_region", "Remote"),
                        url=entry.get("link", ""),
                        description=self._strip_html(entry.get("summary", "")),
                        posted_at=entry.get("published"),
                        raw={"feed_url": feed_url},
                    )
                )
        return postings
