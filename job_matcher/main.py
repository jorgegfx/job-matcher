from __future__ import annotations

import argparse
import sys

from .config import Config, load_config
from .cv_loader import load_cv_text
from .embeddings import LocalEmbedder
from .fetchers import GreenhouseFetcher, HNHiringFetcher, RemotiveFetcher, WeWorkRemotelyFetcher
from .fetchers.base import Fetcher, JobPosting
from .llm import OllamaCloudClient
from .matcher import RankedJob, keyword_filter, rank_by_similarity
from .notify import build_report_markdown, open_github_issue, write_report
from .state import SeenJobsStore


def build_fetchers(config: Config) -> list[Fetcher]:
    boards = config.boards
    fetchers: list[Fetcher] = []

    rem = boards.get("remotive", {})
    if rem.get("enabled"):
        fetchers.append(RemotiveFetcher(category=rem.get("category")))

    wwr = boards.get("weworkremotely", {})
    if wwr.get("enabled") and wwr.get("feeds"):
        fetchers.append(WeWorkRemotelyFetcher(feed_urls=wwr["feeds"]))

    hn = boards.get("hn_hiring", {})
    if hn.get("enabled"):
        fetchers.append(HNHiringFetcher(max_results=hn.get("max_results", 100)))

    gh = boards.get("greenhouse", {})
    if gh.get("enabled") and gh.get("company_tokens"):
        fetchers.append(GreenhouseFetcher(company_tokens=gh["company_tokens"]))

    return fetchers


def fetch_all(fetchers: list[Fetcher]) -> list[JobPosting]:
    all_jobs: list[JobPosting] = []
    for fetcher in fetchers:
        try:
            jobs = fetcher.fetch()
            print(f"[{fetcher.name}] fetched {len(jobs)} postings")
            all_jobs.extend(jobs)
        except Exception as exc:  # noqa: BLE001 - one bad board shouldn't kill the run
            print(f"[{fetcher.name}] fetch failed: {exc}", file=sys.stderr)
    return all_jobs


def run(config_path: str, use_llm: bool = True) -> None:
    config = load_config(config_path)

    cv_text = load_cv_text(config.cv_path)
    print(f"Loaded CV ({len(cv_text)} chars) from {config.cv_path}")

    fetchers = build_fetchers(config)
    raw_jobs = fetch_all(fetchers)
    print(f"Total raw postings fetched: {len(raw_jobs)}")

    with SeenJobsStore(config.state_db_path) as store:
        # Dedup first — cheapest possible filter, and guarantees a listing
        # is never embedded or LLM-analyzed twice across runs.
        new_jobs = [j for j in raw_jobs if not store.has_seen(j.job_id)]
        print(f"New (unseen) postings: {len(new_jobs)}")

        search_cfg = config.search
        filtered = keyword_filter(
            new_jobs,
            must_include_any=search_cfg.get("must_include_any", []),
            exclude_any=search_cfg.get("exclude_any", []),
            location_include_any=search_cfg.get("location_include_any", []),
        )
        print(f"Survived keyword filter: {len(filtered)}")

        matching_cfg = config.matching
        embedder = LocalEmbedder(matching_cfg.get("embedding_model", "all-MiniLM-L6-v2"))
        ranked = rank_by_similarity(
            filtered,
            cv_text=cv_text,
            embedder=embedder,
            min_similarity=matching_cfg.get("min_similarity", 0.35),
        )
        print(f"Survived embedding similarity threshold: {len(ranked)}")

        llm_cfg = config.llm
        max_candidates = llm_cfg.get("max_candidates", 12)
        shortlist = ranked[:max_candidates]

        results: list[tuple[RankedJob, object | None]] = []

        llm_client = None
        if use_llm and shortlist:
            llm_client = OllamaCloudClient(
                api_key=config.ollama_api_key,
                model=llm_cfg.get("model", "gpt-oss:120b"),
                temperature=llm_cfg.get("temperature", 0.2),
            )

        for r in shortlist:
            analysis = None
            if llm_client:
                try:
                    analysis = llm_client.analyze_fit(cv_text, r.job)
                except Exception as exc:  # noqa: BLE001
                    print(f"LLM analysis failed for {r.job.url}: {exc}", file=sys.stderr)
            results.append((r, analysis))

        # Mark every *fetched* new job as seen (not just the shortlisted
        # ones) so noise that didn't match this time doesn't get
        # re-evaluated on every future run either.
        for j in new_jobs:
            store.mark_seen(j.job_id, source=j.source, title=j.title, url=j.url)

        report_md = build_report_markdown(results)
        write_report(report_md, config.report_path)
        print(f"Report written to {config.report_path}")

        if config.open_github_issue and results:
            try:
                open_github_issue(
                    report_md,
                    repo=config.github_repository,
                    token=config.github_token,
                    num_matches=len(results),
                )
                print("Opened GitHub Issue with results.")
            except Exception as exc:  # noqa: BLE001
                print(f"Could not open GitHub Issue: {exc}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch, filter, and rank job postings against a CV.")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip the Ollama Cloud step; only run the free keyword+embedding stages.",
    )
    args = parser.parse_args()
    run(config_path=args.config, use_llm=not args.no_llm)


if __name__ == "__main__":
    main()
