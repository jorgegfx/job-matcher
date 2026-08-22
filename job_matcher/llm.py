from __future__ import annotations

import json
from dataclasses import dataclass

from .fetchers.base import JobPosting

OLLAMA_CLOUD_HOST = "https://ollama.com"

SYSTEM_PROMPT = (
    "You are a precise, no-fluff technical recruiter assistant. Given a "
    "candidate's CV and a single job posting, assess fit. Respond with ONLY "
    "a JSON object, no markdown fences, no preamble, with this exact shape: "
    '{"fit_score": <0-100 integer>, "strengths": ["..."], "gaps": ["..."], '
    '"one_line_verdict": "..."}. Keep each list to at most 4 short items.'
)


@dataclass
class FitAnalysis:
    fit_score: int
    strengths: list[str]
    gaps: list[str]
    one_line_verdict: str


class OllamaCloudClient:
    """Client for Ollama's hosted cloud models (ollama.com), used only for
    the final, cost-bearing step: a narrative fit analysis on the small
    shortlist that survives the free local-embedding ranking stage.
    """

    def __init__(self, api_key: str, model: str = "gpt-oss:120b", temperature: float = 0.2):
        if not api_key:
            raise ValueError(
                "OLLAMA_API_KEY is not set. Get one at https://ollama.com/settings/keys "
                "and export it as an environment variable / repo secret."
            )
        from ollama import Client

        self._client = Client(
            host=OLLAMA_CLOUD_HOST,
            headers={"Authorization": f"Bearer {api_key}"},
        )
        self.model = model
        self.temperature = temperature

    def analyze_fit(self, cv_text: str, job: JobPosting) -> FitAnalysis:
        user_prompt = (
            f"CANDIDATE CV:\n{cv_text[:6000]}\n\n"
            f"JOB POSTING\nTitle: {job.title}\nCompany: {job.company}\n"
            f"Location: {job.location}\nURL: {job.url}\n"
            f"Description:\n{job.description[:4000]}"
        )

        response = self._client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            options={"temperature": self.temperature},
        )

        content = response["message"]["content"].strip()
        content = _strip_code_fences(content)

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # Degrade gracefully rather than crashing the whole run over one
            # malformed LLM response.
            return FitAnalysis(
                fit_score=0,
                strengths=[],
                gaps=["LLM response could not be parsed as JSON."],
                one_line_verdict="(analysis failed — see raw response in logs)",
            )

        return FitAnalysis(
            fit_score=int(data.get("fit_score", 0)),
            strengths=list(data.get("strengths", []))[:4],
            gaps=list(data.get("gaps", []))[:4],
            one_line_verdict=str(data.get("one_line_verdict", "")),
        )


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()
