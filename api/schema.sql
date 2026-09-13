CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,          -- 'manual', 'trader_joes' (kroger is queried live, never stored)
    vendor TEXT NOT NULL,          -- display name, e.g. 'Whole Foods', 'Trader Joe''s'
    store_code TEXT,               -- vendor's own store identifier, when applicable
    full_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    category TEXT,
    unit_price NUMERIC(10, 2) NOT NULL,  -- total price for the item as sold, not price-per-unit
    pack_qty NUMERIC,              -- e.g. 64 for "64 fl oz" - null when unparseable
    pack_unit TEXT,                -- 'fl_oz' | 'oz' | 'count' - null when unparseable
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Safe to re-run against the existing table (pre-dates these columns).
ALTER TABLE products ADD COLUMN IF NOT EXISTS pack_qty NUMERIC;
ALTER TABLE products ADD COLUMN IF NOT EXISTS pack_unit TEXT;
ALTER TABLE products ADD COLUMN IF NOT EXISTS embedding vector(768);

CREATE INDEX IF NOT EXISTS idx_products_full_name_trgm
    ON products USING gin (lower(full_name) gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_products_embedding
    ON products USING hnsw (embedding vector_cosine_ops);

-- One row per (product, vendor, day) - built from real search traffic and
-- from CSV/Trader-Joe's imports, so "lowest in 30 days" has something to
-- look back on without a separate scraping/cron job.
CREATE TABLE IF NOT EXISTS price_history (
    id SERIAL PRIMARY KEY,
    normalized_name TEXT NOT NULL,
    vendor TEXT NOT NULL,
    source TEXT NOT NULL,
    price NUMERIC(10, 2) NOT NULL,
    observed_date DATE NOT NULL DEFAULT CURRENT_DATE,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (normalized_name, vendor, observed_date)
);

CREATE INDEX IF NOT EXISTS idx_price_history_lookup
    ON price_history (normalized_name, vendor, observed_date);

CREATE TABLE IF NOT EXISTS price_alerts (
    id SERIAL PRIMARY KEY,
    email TEXT NOT NULL,
    search_term TEXT NOT NULL,
    normalized_term TEXT NOT NULL,
    target_price NUMERIC(10, 2) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT true,
    last_notified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
