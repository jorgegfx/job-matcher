from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import requests

DEFAULT_HEADERS = {
    "User-Agent": "job-matcher-bot/0.1 (+https://github.com/) personal-use-agent"
}
DEFAULT_TIMEOUT = 20


@dataclass
class JobPosting:
    source: str
    title: str
    company: str
    location: str
    url: str
    description: str
    posted_at: str | None = None
    raw: dict = field(default_factory=dict)

    @property
    def job_id(self) -> str:
        """Stable dedup key: source + URL, hashed."""
        return hashlib.sha256(f"{self.source}:{self.url}".encode()).hexdigest()[:24]

    @property
    def text_blob(self) -> str:
        """Combined text used for keyword filtering and embedding."""
        return f"{self.title}\n{self.company}\n{self.location}\n{self.description}"


class Fetcher:
    """Base class for a job board fetcher. Subclass and implement fetch()."""

    name: str = "base"

    def fetch(self) -> list[JobPosting]:
        raise NotImplementedError

    @staticmethod
    def _get(url: str, params: dict | None = None) -> requests.Response:
        resp = requests.get(
            url, params=params, headers=DEFAULT_HEADERS, timeout=DEFAULT_TIMEOUT
        )
        resp.raise_for_status()
        return resp

    @staticmethod
    def _strip_html(text: str) -> str:
        import re

        text = re.sub(r"<[^>]+>", " ", text or "")
        text = re.sub(r"\s+", " ", text)
        return text.strip()
