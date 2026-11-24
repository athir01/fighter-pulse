"""Postgres write layer — idempotent upserts on natural keys, same pattern
used throughout: reruns update in place instead of duplicating.
"""

from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache

import psycopg

from .config import get_settings
from .models import ParsedArticle, ScoredMention


@lru_cache
def get_conn() -> psycopg.Connection:
    settings = get_settings()
    return psycopg.connect(settings.database_url, autocommit=True)


def _now() -> datetime:
    return datetime.now(UTC)


class Repository:
    def __init__(self, conn: psycopg.Connection) -> None:
        self._c = conn

    def upsert_article(self, article: ParsedArticle) -> tuple[str, bool]:
        """Insert or update an article. Returns ``(article_id, content_changed)``.

        ``content_changed`` is True for new articles and for articles whose
        content differs from what's stored. The ``WHERE ... IS DISTINCT FROM``
        clause turns a no-op update into *no* update, so the CTE returns no
        row and we fall through to a plain lookup. Callers use the flag to
        skip re-scoring (and re-paying the LLM for) unchanged articles —
        idempotent is not the same as incremental.
        """
        params = (
            article.source,
            article.guid,
            article.url,
            article.title,
            article.summary,
            article.published_at,
        )
        row = self._c.execute(
            """
            WITH upserted AS (
                INSERT INTO articles (source, guid, url, title, summary, published_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (source, guid) DO UPDATE SET
                    url = EXCLUDED.url,
                    title = EXCLUDED.title,
                    summary = EXCLUDED.summary,
                    published_at = EXCLUDED.published_at,
                    updated_at = now()
                WHERE (articles.url, articles.title, articles.summary, articles.published_at)
                    IS DISTINCT FROM
                    (EXCLUDED.url, EXCLUDED.title, EXCLUDED.summary, EXCLUDED.published_at)
                RETURNING id
            )
            SELECT id, TRUE FROM upserted
            UNION ALL
            SELECT id, FALSE FROM articles
            WHERE source = %s AND guid = %s AND NOT EXISTS (SELECT 1 FROM upserted)
            """,
            (*params, article.source, article.guid),
        ).fetchone()
        assert row is not None
        return str(row[0]), bool(row[1])

    def scorers_for_article(self, article_id: str) -> set[str]:
        rows = self._c.execute(
            "SELECT DISTINCT scorer FROM fighter_sentiment WHERE article_id = %s", (article_id,)
        ).fetchall()
        return {str(r[0]) for r in rows}

    def upsert_fighter(self, slug: str, full_name: str, aliases: list[str]) -> None:
        self._c.execute(
            """
            INSERT INTO fighters (slug, full_name, aliases)
            VALUES (%s, %s, %s)
            ON CONFLICT (slug) DO UPDATE SET
                full_name = EXCLUDED.full_name,
                aliases = EXCLUDED.aliases,
                updated_at = now()
            """,
            (slug, full_name, aliases),
        )

    def fighter_ids_by_slug(self) -> dict[str, str]:
        """Load the whole slug -> id map once, instead of one query per scored row (N+1)."""
        rows = self._c.execute("SELECT slug, id FROM fighters").fetchall()
        return {str(slug): str(fid) for slug, fid in rows}

    def upsert_fighter_sentiment(
        self, article_id: str, fighter_id: str, scored: ScoredMention
    ) -> None:
        self._c.execute(
            """
            INSERT INTO fighter_sentiment
                (article_id, fighter_id, scorer, sentiment_score, confidence, rationale)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (article_id, fighter_id, scorer) DO UPDATE SET
                sentiment_score = EXCLUDED.sentiment_score,
                confidence = EXCLUDED.confidence,
                rationale = EXCLUDED.rationale,
                updated_at = now()
            """,
            (
                article_id,
                fighter_id,
                scored.scorer,
                scored.sentiment_score,
                scored.confidence,
                scored.rationale,
            ),
        )

    def start_run(self, source: str) -> str:
        row = self._c.execute(
            "INSERT INTO ingest_runs (source, started_at) VALUES (%s, %s) RETURNING id",
            (source, _now()),
        ).fetchone()
        assert row is not None
        return str(row[0])

    def finish_run(
        self,
        run_id: str,
        *,
        status: str,
        records_processed: int,
        llm_cost_usd: float,
        error: str | None,
    ) -> None:
        """``llm_cost_usd`` must be THIS run's spend only — total_llm_spend() sums it."""
        self._c.execute(
            """
            UPDATE ingest_runs
            SET finished_at = %s, status = %s, records_processed = %s,
                llm_cost_usd = %s, error = %s
            WHERE id = %s
            """,
            (_now(), status, records_processed, llm_cost_usd, error, run_id),
        )

    def total_llm_spend(self) -> float:
        row = self._c.execute(
            "SELECT COALESCE(SUM(llm_cost_usd), 0) FROM ingest_runs"
        ).fetchone()
        assert row is not None
        return float(row[0])
