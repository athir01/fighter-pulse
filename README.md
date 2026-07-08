# fighter-pulse

Batch pipeline that ingests MMA news, resolves which fighter(s) each article
mentions, and scores sentiment per fighter — with a hard-capped LLM budget and
a free baseline for comparison.

## Why this exists

Generic sentiment analysis on short text can't tell you *who* the sentiment is
about. "Jones would destroy Ngannou" is positive for one fighter and negative
for the other — a plain sentiment classifier scores the whole sentence as one
number. This pipeline solves the actual hard part (entity attribution), not
just the easy part (is this positive or negative).

## Architecture

```
RSS feeds ──▶ discover ──▶ upsert article ──▶ find fighter mentions (free, fuzzy match)
                                                        │
                                    ┌───────────────────┼────────────────────┐
                                    ▼                                        ▼
                    VADER (free, whole-article sentiment)      Claude Haiku 4.5 (cost-capped,
                    — the eval baseline                        per-fighter attribution + sentiment
                                    │                           in one combined call)
                                    └───────────────┬────────────────────────┘
                                                     ▼
                                     upsert fighter_sentiment (idempotent, one row
                                     per article × fighter × scorer)
```

- **Ingestion**: RSS feeds only (no scraping — RSS is explicitly meant for
  programmatic consumption, so there's no ToS risk).
- **Entity resolution**: free fuzzy string matching (`rapidfuzz`) against a
  seed fighter roster (`data/fighters_seed.json`).
- **Scoring**: two scorers behind a common interface (`ingest/scoring/`) so
  they can be compared, not just swapped —
  - `VaderScorer`: free, local, whole-article sentiment. Can't attribute
    sentiment to a specific fighter — kept as the eval baseline.
  - `LlmScorer`: Claude Haiku 4.5, one combined call per article that
    disambiguates *and* scores every mentioned fighter. Every call is checked
    against a **hard cost cap** (`LLM_COST_CAP_USD`, default $5) before it's
    made, tracked via `ingest/cost_tracker.py`, persisted across runs in
    `ingest_runs.llm_cost_usd`.
- **Storage**: Postgres, idempotent upserts on natural keys — reruns update
  rows in place instead of duplicating.
- **Evaluation**: `eval/` compares both scorers against a hand-labeled gold
  set (`eval/gold_set.csv`) — the piece that makes this a measured pipeline,
  not just one that produces plausible-looking numbers.

## Setup

```bash
docker compose up -d          # local Postgres
cp .env.example .env.local    # fill in DATABASE_URL / ANTHROPIC_API_KEY
psql "$DATABASE_URL" -f db/migrations/0001_init.sql
uv pip install -e ".[dev]"
python -m ingest.run
```

## Testing

```bash
ruff check .
mypy ingest
pytest -v
```
