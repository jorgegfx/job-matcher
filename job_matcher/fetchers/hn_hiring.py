from __future__ import annotations

from .base import Fetcher, JobPosting

# Algolia's free, keyless HN Search API. We find the latest
# "Who is Hiring?" story by Ask HN author, then pull its top-level comments,
# each of which is one job posting.
SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date"
ITEM_URL = "https://hn.algolia.com/api/v1/items/{id}"


class HNHiringFetcher(Fetcher):
    """Hacker News monthly 'Who is Hiring?' thread, via the free Algolia
    HN Search API (no key required)."""

    name = "hn_hiring"

    def __init__(self, max_results: int = 100):
        self.max_results = max_results

    def _find_latest_thread_id(self) -> str | None:
        data = self._get(
            SEARCH_URL,
            params={
                "query": "Who is Hiring",
                "tags": "story,author_whoishiring",
                "hitsPerPage": 1,
            },
        ).json()
        hits = data.get("hits", [])
        return hits[0]["objectID"] if hits else None

    def fetch(self) -> list[JobPosting]:
        thread_id = self._find_latest_thread_id()
        if not thread_id:
            return []

        item = self._get(ITEM_URL.format(id=thread_id)).json()
        comments = item.get("children", [])[: self.max_results]

        postings = []
        for c in comments:
            text = self._strip_html(c.get("text", ""))
            if not text:
                continue
            title = text.split(" | ")[0][:120] if " | " in text else text[:120]
            postings.append(
                JobPosting(
                    source=self.name,
                    title=title,
                    company="",
                    location="",
                    url=f"https://news.ycombinator.com/item?id={c.get('id')}",
                    description=text,
                    posted_at=None,
                    raw={"thread_id": thread_id},
                )
            )
        return postings
