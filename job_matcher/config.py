from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List

import yaml


@dataclass
class Config:
    raw: dict[str, Any]
    path: Path

    # --- convenience accessors -------------------------------------------------
    @property
    def cv_path(self) -> Path:
        return self.path.parent / self.raw["cv"]["path"]

    @property
    def search(self) -> dict[str, Any]:
        return self.raw.get("search", {})

    @property
    def boards(self) -> dict[str, Any]:
        return self.raw.get("boards", {})

    @property
    def matching(self) -> dict[str, Any]:
        return self.raw.get("matching", {})

    @property
    def llm(self) -> dict[str, Any]:
        return self.raw.get("llm", {})

    @property
    def state_db_path(self) -> Path:
        return self.path.parent / self.raw.get("state", {}).get(
            "db_path", "data/seen_jobs.sqlite3"
        )

    @property
    def report_path(self) -> Path:
        return self.path.parent / self.raw.get("output", {}).get(
            "report_path", "report.md"
        )

    @property
    def open_github_issue(self) -> bool:
        return bool(self.raw.get("output", {}).get("open_github_issue", False))

    @property
    def email_recipients(self) -> list[str]:
        # Recipients are just addresses, not secrets, so they live in
        # config.yaml. SMTP credentials still come from env/secrets only.
        return list(self.raw.get("output", {}).get("email_recipients", []) or [])

    # --- secrets, always from env, never from the yaml file ---------------------
    @property
    def ollama_api_key(self) -> str | None:
        return os.environ.get("OLLAMA_API_KEY")

    @property
    def github_token(self) -> str | None:
        return os.environ.get("GH_ISSUE_TOKEN") or os.environ.get("GITHUB_TOKEN")

    @property
    def github_repository(self) -> str | None:
        return os.environ.get("GITHUB_REPOSITORY")


def load_config(path: str | Path = "config.yaml") -> Config:
    p = Path(path).resolve()
    with open(p, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return Config(raw=raw, path=p)
