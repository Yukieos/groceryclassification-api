CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    source TEXT NOT NULL,          -- 'manual', 'trader_joes' (kroger is queried live, never stored)
    vendor TEXT NOT NULL,          -- display name, e.g. 'Whole Foods', 'Trader Joe''s'
    store_code TEXT,               -- vendor's own store identifier, when applicable
    full_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    category TEXT,
    unit_price NUMERIC(10, 2) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_products_full_name_trgm
    ON products USING gin (lower(full_name) gin_trgm_ops);
