from __future__ import annotations

from pathlib import Path

import requests

from .llm import FitAnalysis
from .matcher import RankedJob


def build_report_markdown(
    ranked_with_analysis: list[tuple[RankedJob, FitAnalysis | None]],
) -> str:
    lines = ["# Job matches\n"]
    if not ranked_with_analysis:
        lines.append("No new matching postings found in this run.\n")
        return "\n".join(lines)

    for ranked, analysis in ranked_with_analysis:
        job = ranked.job
        lines.append(f"## [{job.title}]({job.url})")
        lines.append(f"**{job.company or 'Unknown company'}** — {job.location or 'n/a'}")
        lines.append(f"- Source: `{job.source}`")
        lines.append(f"- Embedding similarity: `{ranked.similarity:.3f}`")
        if analysis:
            lines.append(f"- LLM fit score: **{analysis.fit_score}/100**")
            lines.append(f"- Verdict: {analysis.one_line_verdict}")
            if analysis.strengths:
                lines.append("- Strengths: " + "; ".join(analysis.strengths))
            if analysis.gaps:
                lines.append("- Gaps: " + "; ".join(analysis.gaps))
        lines.append("")

    return "\n".join(lines)


def write_report(report_md: str, path: Path) -> None:
    path.write_text(report_md, encoding="utf-8")


def open_github_issue(
    report_md: str, repo: str, token: str, num_matches: int
) -> None:
    """Opens a GitHub Issue with the run's results. Requires the workflow
    to grant `issues: write` permission (the default GITHUB_TOKEN can do
    this for same-repo issues — see the workflow file).
    """
    if not repo or not token:
        return

    url = f"https://api.github.com/repos/{repo}/issues"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    payload = {
        "title": f"Job matches — {num_matches} new posting(s)",
        "body": report_md,
        "labels": ["job-matcher"],
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=20)
    resp.raise_for_status()
