CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE fighters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    slug TEXT NOT NULL,
    full_name TEXT NOT NULL,
    aliases TEXT[] NOT NULL DEFAULT '{}'
);
CREATE UNIQUE INDEX idx_fighters_slug ON fighters (slug);

CREATE TABLE articles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    source TEXT NOT NULL,
    guid TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    published_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX idx_articles_source_guid ON articles (source, guid);

-- One row per (article, fighter, scorer) so the free VADER baseline and the
-- LLM scorer can coexist for the same article without overwriting each other.
CREATE TABLE fighter_sentiment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    article_id UUID NOT NULL REFERENCES articles(id),
    fighter_id UUID NOT NULL REFERENCES fighters(id),
    scorer TEXT NOT NULL,
    sentiment_score REAL NOT NULL,
    confidence REAL,
    rationale TEXT
);
CREATE UNIQUE INDEX idx_fighter_sentiment_natural_key
    ON fighter_sentiment (article_id, fighter_id, scorer);

CREATE TABLE ingest_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    source TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'running',
    records_processed INTEGER NOT NULL DEFAULT 0,
    llm_cost_usd REAL NOT NULL DEFAULT 0,
    error TEXT
);
