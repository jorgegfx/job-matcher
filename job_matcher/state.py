from __future__ import annotations

import sqlite3
from pathlib import Path


class SeenJobsStore:
    """Tracks which job postings have already been processed, so repeated
    Action runs never re-embed or re-send the same listing to the LLM.

    Backed by a single SQLite file that the workflow commits back to the
    repo after each run.
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_jobs (
                job_id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                title TEXT,
                url TEXT,
                first_seen_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self._conn.commit()

    def has_seen(self, job_id: str) -> bool:
        cur = self._conn.execute(
            "SELECT 1 FROM seen_jobs WHERE job_id = ?", (job_id,)
        )
        return cur.fetchone() is not None

    def mark_seen(self, job_id: str, source: str, title: str, url: str) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO seen_jobs (job_id, source, title, url) "
            "VALUES (?, ?, ?, ?)",
            (job_id, source, title, url),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "SeenJobsStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
