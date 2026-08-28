-- MarketLens Product Intelligence Migration
-- Adds observation history, source provenance, scoring, dedup, and data quality

CREATE SCHEMA IF NOT EXISTS marketlens;
SET search_path TO public, marketlens;

-- ═══════════════════════════════════════════════════════════
-- ALTER PRODUCTS TABLE — Add canonical product fields
-- ═══════════════════════════════════════════════════════════

ALTER TABLE products ADD COLUMN IF NOT EXISTS normalized_title TEXT DEFAULT '';
ALTER TABLE products ADD COLUMN IF NOT EXISTS canonical_url TEXT DEFAULT '';
ALTER TABLE products ADD COLUMN IF NOT EXISTS brand TEXT DEFAULT '';
ALTER TABLE products ADD COLUMN IF NOT EXISTS model_number TEXT DEFAULT '';
ALTER TABLE products ADD COLUMN IF NOT EXISTS marketplace TEXT DEFAULT 'US';
ALTER TABLE products ADD COLUMN IF NOT EXISTS upc TEXT DEFAULT '';
ALTER TABLE products ADD COLUMN IF NOT EXISTS ean TEXT DEFAULT '';
ALTER TABLE products ADD COLUMN IF NOT EXISTS gtin TEXT DEFAULT '';
ALTER TABLE products ADD COLUMN IF NOT EXISTS product_url TEXT DEFAULT '';
ALTER TABLE products ADD COLUMN IF NOT EXISTS image_url TEXT DEFAULT '';
ALTER TABLE products ADD COLUMN IF NOT EXISTS parent_asin TEXT DEFAULT '';
ALTER TABLE products ADD COLUMN IF NOT EXISTS variant_group TEXT DEFAULT '';
ALTER TABLE products ADD COLUMN IF NOT EXISTS data_quality_score REAL DEFAULT 0.0;
ALTER TABLE products ADD COLUMN IF NOT EXISTS opportunity_score REAL DEFAULT 0.0;
ALTER TABLE products ADD COLUMN IF NOT EXISTS opportunity_confidence TEXT DEFAULT 'low';
ALTER TABLE products ADD COLUMN IF NOT EXISTS scoring_version TEXT DEFAULT '';
ALTER TABLE products ADD COLUMN IF NOT EXISTS score_breakdown JSONB DEFAULT '{}';
ALTER TABLE products ADD COLUMN IF NOT EXISTS last_observed_at TIMESTAMP;
ALTER TABLE products ADD COLUMN IF NOT EXISTS source_count INTEGER DEFAULT 0;
ALTER TABLE products ADD COLUMN IF NOT EXISTS observation_count INTEGER DEFAULT 0;
ALTER TABLE products ADD COLUMN IF NOT EXISTS price_trend TEXT DEFAULT 'stable';
ALTER TABLE products ADD COLUMN IF NOT EXISTS review_velocity REAL DEFAULT 0.0;
ALTER TABLE products ADD COLUMN IF NOT EXISTS score_fingerprint TEXT DEFAULT '';
ALTER TABLE products ADD COLUMN IF NOT EXISTS data_freshness_hours INTEGER DEFAULT 0;

-- Composite unique constraint: one product per marketplace
-- (Only add if not already present — ASIN alone is already UNIQUE)
-- We keep ASIN UNIQUE as primary since most products are single-marketplace

-- ═══════════════════════════════════════════════════════════
-- PRODUCT OBSERVATIONS — Time-series market data
-- ═══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS product_observations (
    id SERIAL PRIMARY KEY,
    asin TEXT NOT NULL,
    price REAL,
    rating REAL,
    review_count INTEGER,
    bsr_rank INTEGER,
    seller_count INTEGER,
    in_stock BOOLEAN DEFAULT TRUE,
    source TEXT DEFAULT '',
    marketplace TEXT DEFAULT 'US',
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    raw_data JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_obs_asin ON product_observations(asin);
CREATE INDEX IF NOT EXISTS idx_obs_asin_time ON product_observations(asin, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_obs_recorded ON product_observations(recorded_at DESC);

-- ═══════════════════════════════════════════════════════════
-- PRODUCT SOURCES — Source provenance per product
-- ═══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS product_sources (
    id SERIAL PRIMARY KEY,
    asin TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_type TEXT DEFAULT 'marketplace',
    raw_product_data JSONB DEFAULT '{}',
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confidence REAL DEFAULT 1.0,
    is_primary BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_src_asin ON product_sources(asin);
CREATE INDEX IF NOT EXISTS idx_src_name ON product_sources(source_name);

-- ═══════════════════════════════════════════════════════════
-- SCORING HISTORY — Versioned score snapshots
-- ═══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS scoring_history (
    id SERIAL PRIMARY KEY,
    asin TEXT NOT NULL,
    scoring_version TEXT NOT NULL DEFAULT 'v2.4',
    opportunity_score REAL DEFAULT 0.0,
    confidence TEXT DEFAULT 'low',
    score_breakdown JSONB DEFAULT '{}',
    inputs_used JSONB DEFAULT '{}',
    missing_inputs JSONB DEFAULT '[]',
    data_quality_score REAL DEFAULT 0.0,
    ai_model TEXT DEFAULT '',
    ai_provider TEXT DEFAULT '',
    prompt_version TEXT DEFAULT '',
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_score_asin ON scoring_history(asin);
CREATE INDEX IF NOT EXISTS idx_score_asin_time ON scoring_history(asin, calculated_at DESC);

-- ═══════════════════════════════════════════════════════════
-- PRODUCT MERGE LOG — Dedup/merge audit trail
-- ═══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS product_merge_log (
    id SERIAL PRIMARY KEY,
    canonical_asin TEXT NOT NULL,
    merged_asin TEXT NOT NULL,
    merge_reason TEXT DEFAULT '',
    confidence REAL DEFAULT 1.0,
    matched_fields JSONB DEFAULT '[]',
    merged_by TEXT DEFAULT 'system',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_merge_canonical ON product_merge_log(canonical_asin);
CREATE INDEX IF NOT EXISTS idx_merge_merged ON product_merge_log(merged_asin);

-- ═══════════════════════════════════════════════════════════
-- DUPLICATE REVIEW QUEUE — Uncertain matches for admin
-- ═══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS duplicate_review_queue (
    id SERIAL PRIMARY KEY,
    product_a_asin TEXT NOT NULL,
    product_b_asin TEXT NOT NULL,
    match_confidence REAL DEFAULT 0.0,
    match_reasons JSONB DEFAULT '[]',
    status TEXT DEFAULT 'pending',
    reviewed_by INTEGER,
    reviewed_at TIMESTAMP,
    resolution TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dq_status ON duplicate_review_queue(status);
CREATE INDEX IF NOT EXISTS idx_dq_asins ON duplicate_review_queue(product_a_asin, product_b_asin);

-- ═══════════════════════════════════════════════════════════
-- SCORING WEIGHTS — Configurable scoring model
-- ═══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS scoring_weights (
    id SERIAL PRIMARY KEY,
    scoring_version TEXT NOT NULL DEFAULT 'v2.4',
    demand_weight REAL DEFAULT 0.20,
    competition_weight REAL DEFAULT 0.20,
    profitability_weight REAL DEFAULT 0.20,
    trend_weight REAL DEFAULT 0.10,
    market_gap_weight REAL DEFAULT 0.10,
    review_opportunity_weight REAL DEFAULT 0.05,
    price_stability_weight REAL DEFAULT 0.05,
    supplier_potential_weight REAL DEFAULT 0.05,
    risk_weight REAL DEFAULT 0.05,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Seed default weights
INSERT INTO scoring_weights (scoring_version, demand_weight, competition_weight, profitability_weight, trend_weight, market_gap_weight, review_opportunity_weight, price_stability_weight, supplier_potential_weight, risk_weight)
VALUES ('v2.4', 0.20, 0.20, 0.20, 0.10, 0.10, 0.05, 0.05, 0.05, 0.05)
ON CONFLICT DO NOTHING;

-- ═══════════════════════════════════════════════════════════
-- CATEGORY BENCHMARKS — For relative scoring
-- ═══════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS category_benchmarks (
    id SERIAL PRIMARY KEY,
    category TEXT NOT NULL,
    marketplace TEXT DEFAULT 'US',
    avg_reviews REAL DEFAULT 0.0,
    avg_price REAL DEFAULT 0.0,
    avg_rating REAL DEFAULT 0.0,
    avg_margin REAL DEFAULT 0.0,
    product_count INTEGER DEFAULT 0,
    median_reviews REAL DEFAULT 0.0,
    median_price REAL DEFAULT 0.0,
    p90_reviews REAL DEFAULT 0.0,
    p90_price REAL DEFAULT 0.0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_bench_cat_market ON category_benchmarks(category, marketplace);

-- ═══════════════════════════════════════════════════════════
-- ADDITIONAL INDEXES
-- ═══════════════════════════════════════════════════════════

CREATE INDEX IF NOT EXISTS idx_products_normalized_title ON products(normalized_title);
CREATE INDEX IF NOT EXISTS idx_products_brand ON products(brand);
CREATE INDEX IF NOT EXISTS idx_products_marketplace ON products(marketplace);
CREATE INDEX IF NOT EXISTS idx_products_data_quality ON products(data_quality_score DESC);
CREATE INDEX IF NOT EXISTS idx_products_opportunity ON products(opportunity_score DESC);
CREATE INDEX IF NOT EXISTS idx_products_last_observed ON products(last_observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_products_parent_asin ON products(parent_asin);

-- GIN index for full_data JSONB queries
CREATE INDEX IF NOT EXISTS idx_products_full_data ON products USING GIN(full_data);

-- Done
