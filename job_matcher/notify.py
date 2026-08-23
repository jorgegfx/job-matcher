from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
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
        lines.append(
            f"**{job.company or 'Unknown company'}** — {job.location or 'n/a'}"
        )
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


def open_github_issue(report_md: str, repo: str, token: str, num_matches: int) -> None:
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


def send_email_report(report_md: str, recipients: list[str]) -> None:
    """Emails the run's report via SMTP.

    All connection details come from environment variables — set these as
    GitHub Actions repo secrets and pass them into the workflow's `env:`
    block, never hardcode them in config.yaml:

        SMTP_HOST       e.g. smtp.gmail.com
        SMTP_PORT       e.g. 587 (STARTTLS) or 465 (implicit TLS). Defaults to 587.
        SMTP_USERNAME   login user for the SMTP server
        SMTP_PASSWORD   password / app password / API key
        SMTP_FROM       "From" address (defaults to SMTP_USERNAME)

    Most providers (Gmail, SendGrid, Mailgun, SES SMTP, etc.) work with this
    same STARTTLS flow — only the host/port/credentials change.

    Silently no-ops if there are no recipients, so callers can wire this up
    unconditionally without an extra `if` at the call site. Missing SMTP
    config or a send failure raises, so a broken mail setup shows up
    clearly in the Action logs instead of failing silently.
    """
    if not recipients:
        return

    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", "587"))
    username = os.environ.get("SMTP_USERNAME")
    password = os.environ.get("SMTP_PASSWORD")
    sender = os.environ.get("SMTP_FROM") or username

    missing = [
        name
        for name, val in [
            ("SMTP_HOST", host),
            ("SMTP_USERNAME", username),
            ("SMTP_PASSWORD", password),
        ]
        if not val
    ]
    if missing:
        raise RuntimeError(
            "send_email_report: missing required environment variable(s): "
            f"{', '.join(missing)}. Set them as GitHub Actions secrets and "
            "pass them into the workflow's `env:` block."
        )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Job matches report"
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(report_md, "plain", "utf-8"))
    msg.attach(MIMEText(_markdown_to_html(report_md), "html", "utf-8"))

    if port == 465:
        # Implicit TLS from the start of the connection.
        with smtplib.SMTP_SSL(host, port, timeout=30) as server:
            server.login(username, password)
            server.sendmail(sender, recipients, msg.as_string())
    else:
        # STARTTLS: plain connection upgraded to TLS. Covers 587 (and most
        # other non-465 ports providers use).
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.starttls()
            server.login(username, password)
            server.sendmail(sender, recipients, msg.as_string())


def _markdown_to_html(report_md: str) -> str:
    """Very small, dependency-free Markdown-to-HTML pass, just enough to
    render this module's own report format (##, [text](url), bullets, bold)
    legibly in an email client. Not a general Markdown parser.
    """
    import html
    import re

    lines = report_md.splitlines()
    html_lines: list[str] = []
    in_list = False

    for line in lines:
        stripped = line.strip()

        if not stripped:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            continue

        if stripped.startswith("## "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h2>{_inline_markdown(stripped[3:])}</h2>")
        elif stripped.startswith("# "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h1>{_inline_markdown(stripped[2:])}</h1>")
        elif stripped.startswith("- "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{_inline_markdown(stripped[2:])}</li>")
        else:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<p>{_inline_markdown(stripped)}</p>")

    if in_list:
        html_lines.append("</ul>")

    body = "\n".join(html_lines)
    return f"<html><body style='font-family: sans-serif;'>{body}</body></html>"


def _inline_markdown(text: str) -> str:
    """Escapes HTML, then applies inline [text](url) links and **bold**."""
    import html
    import re

    escaped = html.escape(text)
    escaped = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    return escaped
