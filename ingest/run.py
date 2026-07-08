"""CLI entrypoint: ``python -m ingest.run``.

For each discovered article: resolve fighter mentions (free) -> score with
VADER (free) -> score with the LLM scorer (cost-capped). One bad article is
logged and skipped, not fatal to the run — same resilience pattern as any
production ingest worker.
"""

from __future__ import annotations

import logging

from .config import get_settings
from .cost_tracker import CostCapExceeded, CostTracker
from .db import Repository, get_conn
from .entities import find_fighter_mentions, load_roster
from .scoring.classical import VaderScorer
from .scoring.llm import LlmScorer
from .sources.rss import RssSource

log = logging.getLogger("fighter_pulse")


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    repo = Repository(get_conn())

    cost_tracker = CostTracker(
        cap_usd=settings.llm_cost_cap_usd, spent_usd=repo.total_llm_spend()
    )
    log.info(
        "llm_budget_status", extra={"spent": cost_tracker.spent_usd, "cap": cost_tracker.cap_usd}
    )

    roster = load_roster()
    vader = VaderScorer()
    llm = LlmScorer(cost_tracker)

    source = RssSource()
    run_id = repo.start_run(source.source_name)
    records = 0
    status = "success"
    error: str | None = None

    try:
        for article in source.discover():
            try:
                article_id = repo.upsert_article(article)
                text = f"{article.title}\n{article.summary or ''}"
                mentions = find_fighter_mentions(text, roster)
                if not mentions:
                    continue

                for scored in vader.score(text, mentions):
                    fighter_id = repo.resolve_fighter_id(scored.fighter_slug)
                    if fighter_id:
                        repo.upsert_fighter_sentiment(article_id, fighter_id, scored)
                        records += 1

                try:
                    for scored in llm.score(text, mentions):
                        fighter_id = repo.resolve_fighter_id(scored.fighter_slug)
                        if fighter_id:
                            repo.upsert_fighter_sentiment(article_id, fighter_id, scored)
                            records += 1
                except CostCapExceeded as exc:
                    log.warning("llm_cost_cap_reached: %s", exc)
                    # Free VADER scores already written; just stop paying for LLM calls.
            except Exception as exc:  # one bad article must not abort the run
                log.error("article_failed url=%s error=%r", article.url, exc)
    except Exception as exc:
        status = "failed"
        error = repr(exc)
        log.error("run_failed source=%s error=%s", source.source_name, error)
    finally:
        repo.finish_run(
            run_id,
            status=status,
            records_processed=records,
            llm_cost_usd=cost_tracker.spent_usd,
            error=error,
        )

    log.info("run_complete status=%s records=%d llm_spend=$%.4f", status, records, cost_tracker.spent_usd)
    return 0 if status == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
