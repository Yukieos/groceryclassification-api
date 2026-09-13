CREATE EXTENSION IF NOT EXISTS pg_trgm;

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

CREATE INDEX IF NOT EXISTS idx_products_full_name_trgm
    ON products USING gin (lower(full_name) gin_trgm_ops);
