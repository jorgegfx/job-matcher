from __future__ import annotations

from dataclasses import dataclass

from .embeddings import LocalEmbedder
from .fetchers.base import JobPosting


@dataclass
class RankedJob:
    job: JobPosting
    similarity: float


def keyword_filter(
    jobs: list[JobPosting],
    must_include_any: list[str],
    exclude_any: list[str],
    location_include_any: list[str],
) -> list[JobPosting]:
    """Cheap first pass: pure string matching, no model involved. This is
    what does the heavy lifting of cutting an unfiltered feed down before
    anything touches the embedding model or the LLM.
    """
    survivors = []
    for job in jobs:
        blob = job.text_blob.lower()

        if exclude_any and any(term.lower() in blob for term in exclude_any):
            continue

        if must_include_any and not any(
            term.lower() in blob for term in must_include_any
        ):
            continue

        if location_include_any:
            loc_blob = f"{job.location} {job.description}".lower()
            if not any(term.lower() in loc_blob for term in location_include_any):
                continue

        survivors.append(job)
    return survivors


def rank_by_similarity(
    jobs: list[JobPosting],
    cv_text: str,
    embedder: LocalEmbedder,
    min_similarity: float = 0.35,
) -> list[RankedJob]:
    """Second pass: rank surviving jobs by cosine similarity to the CV,
    using a local embedding model. Zero API cost, runs on CPU."""
    if not jobs:
        return []

    cv_vec = embedder.embed([cv_text])[0]
    job_vecs = embedder.embed([j.text_blob for j in jobs])

    sims = job_vecs @ cv_vec  # already normalized -> cosine similarity
    ranked = [
        RankedJob(job=job, similarity=float(sim))
        for job, sim in zip(jobs, sims)
        if sim >= min_similarity
    ]
    ranked.sort(key=lambda r: r.similarity, reverse=True)
    return ranked
