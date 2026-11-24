"""CLI entrypoint: ``python -m ingest.run``.

For each discovered article: resolve fighter mentions (free) -> score with
VADER (free) -> score with the LLM scorer (cost-capped). One bad article is
logged and skipped, not fatal to the run.

Incremental by default: an article whose content hasn't changed since a
scorer last scored it is not re-scored. RSS feeds return the same ~20-50
recent items on every poll, so without this every run would re-pay the LLM
for articles it has already scored.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

from .config import get_settings
from .cost_tracker import CostCapExceeded, CostTracker
from .db import Repository, get_conn
from .entities import FighterMatcher, load_roster
from .models import ScoredMention
from .scoring.classical import VaderScorer
from .scoring.llm import LlmScorer
from .sources.rss import RssSource

log = logging.getLogger("fighter_pulse")

_PLACEHOLDER_API_KEY = "sk-ant-your-key"


def _write_scores(
    repo: Repository, article_id: str, fighter_ids: dict[str, str], scores: Iterable[ScoredMention]
) -> int:
    written = 0
    for scored in scores:
        fighter_id = fighter_ids.get(scored.fighter_slug)
        if fighter_id is None:
            log.warning("unknown_fighter_slug slug=%s", scored.fighter_slug)
            continue
        repo.upsert_fighter_sentiment(article_id, fighter_id, scored)
        written += 1
    return written


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()
    repo = Repository(get_conn())

    # Seed the roster every run (idempotent, ~200 upserts). Previously, forgetting
    # `python -m ingest.seed_fighters` made every score silently drop because the
    # slug -> id lookup returned nothing — a "successful" run that wrote 0 rows.
    roster = load_roster()
    for fighter in roster:
        repo.upsert_fighter(fighter["slug"], fighter["full_name"], fighter["aliases"])
    fighter_ids = repo.fighter_ids_by_slug()
    matcher = FighterMatcher(roster)

    prior_spend = repo.total_llm_spend()
    cost_tracker = CostTracker(cap_usd=settings.llm_cost_cap_usd, spent_usd=prior_spend)
    log.info("llm_budget spent=$%.4f cap=$%.2f", prior_spend, settings.llm_cost_cap_usd)

    vader = VaderScorer()
    llm: LlmScorer | None = None
    if settings.anthropic_api_key != _PLACEHOLDER_API_KEY:
        llm = LlmScorer(cost_tracker)
    else:
        log.warning("llm_disabled: ANTHROPIC_API_KEY is still the .env.example placeholder")

    source = RssSource(
        user_agent=settings.ingest_user_agent, rate_limit_rps=settings.ingest_rate_limit_rps
    )
    run_id = repo.start_run(source.source_name)
    records = articles_seen = articles_skipped = articles_failed = 0
    status = "success"
    error: str | None = None

    try:
        for article in source.discover():
            articles_seen += 1
            try:
                article_id, changed = repo.upsert_article(article)
                text = f"{article.title}\n{article.summary or ''}"
                mentions = matcher.find(text)
                if not mentions:
                    continue

                already_scored = set() if changed else repo.scorers_for_article(article_id)
                if vader.name in already_scored and (llm is None or llm.name in already_scored):
                    articles_skipped += 1
                    continue

                if vader.name not in already_scored:
                    records += _write_scores(
                        repo, article_id, fighter_ids, vader.score(text, mentions)
                    )

                if llm is not None and llm.name not in already_scored:
                    try:
                        records += _write_scores(
                            repo, article_id, fighter_ids, llm.score(text, mentions)
                        )
                    except CostCapExceeded as exc:
                        # Stop asking for the rest of the run instead of raising per article.
                        log.warning("llm_cost_cap_reached, disabling LLM for this run: %s", exc)
                        llm = None
            except Exception as exc:  # one bad article must not abort the run
                articles_failed += 1
                log.error("article_failed url=%s error=%r", article.url, exc)
    except Exception as exc:
        status = "failed"
        error = repr(exc)
        log.error("run_failed source=%s error=%s", source.source_name, error)
    finally:
        if status == "success" and articles_failed:
            status = "partial"
            error = f"{articles_failed} of {articles_seen} articles failed"
        repo.finish_run(
            run_id,
            status=status,
            records_processed=records,
            # This run's spend only. Writing cost_tracker.spent_usd (which includes
            # prior runs) double-counted history, since total_llm_spend() SUMs rows.
            llm_cost_usd=cost_tracker.spent_usd - prior_spend,
            error=error,
        )

    log.info(
        "run_complete status=%s articles=%d skipped_unchanged=%d failed=%d records=%d "
        "llm_spend_this_run=$%.4f",
        status,
        articles_seen,
        articles_skipped,
        articles_failed,
        records,
        cost_tracker.spent_usd - prior_spend,
    )
    return 0 if status == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
