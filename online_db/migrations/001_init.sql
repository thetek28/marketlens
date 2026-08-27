-- MarketLens PostgreSQL Migration
-- Run this to initialize the database schema

-- Create schema
CREATE SCHEMA IF NOT EXISTS marketlens;
SET search_path TO public, marketlens;

-- ═══════════════════════════════════════════════════════════
-- SUPPLIERS
-- ═══════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS suppliers (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    location TEXT DEFAULT '',
    country TEXT DEFAULT '',
    website TEXT DEFAULT '',
    contact_person TEXT DEFAULT '',
    contact_email TEXT DEFAULT '',
    contact_phone TEXT DEFAULT '',
    contact_whatsapp TEXT DEFAULT '',
    contact_skype TEXT DEFAULT '',
    contact_wechat TEXT DEFAULT '',
    company_name TEXT DEFAULT '',
    business_type TEXT DEFAULT '',
    year_established INTEGER DEFAULT 0,
    employee_count TEXT DEFAULT '',
    moq INTEGER DEFAULT 1,
    lead_time_days INTEGER DEFAULT 7,
    payment_terms TEXT DEFAULT 'T/T',
    shipping_methods TEXT DEFAULT '',
    certifications TEXT DEFAULT '',
    rating REAL DEFAULT 0.0,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS supplier_products (
    id SERIAL PRIMARY KEY,
    supplier_id INTEGER NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
    product_name TEXT NOT NULL,
    asin TEXT DEFAULT '',
    sku TEXT DEFAULT '',
    unit_cost REAL DEFAULT 0.0,
    shipping_cost REAL DEFAULT 0.0,
    min_order INTEGER DEFAULT 1,
    bulk_prices JSONB DEFAULT '{}',
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ═══════════════════════════════════════════════════════════
-- PRODUCT PRICING
-- ═══════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS product_pricing (
    id SERIAL PRIMARY KEY,
    asin TEXT NOT NULL UNIQUE,
    product_name TEXT DEFAULT '',
    supplier_id INTEGER,
    supplier_cost REAL DEFAULT 0.0,
    shipping_cost REAL DEFAULT 0.0,
    customs_duty REAL DEFAULT 0.0,
    packaging_cost REAL DEFAULT 0.0,
    fba_fee REAL DEFAULT 0.0,
    referral_fee REAL DEFAULT 0.0,
    total_landed_cost REAL DEFAULT 0.0,
    current_market_price REAL DEFAULT 0.0,
    suggested_price REAL DEFAULT 0.0,
    min_price REAL DEFAULT 0.0,
    max_price REAL DEFAULT 0.0,
    profit_per_unit REAL DEFAULT 0.0,
    margin_pct REAL DEFAULT 0.0,
    roi_pct REAL DEFAULT 0.0,
    break_even_units INTEGER DEFAULT 0,
    target_margin REAL DEFAULT 0.0,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ═══════════════════════════════════════════════════════════
-- PRODUCT CACHE
-- ═══════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS product_cache (
    id SERIAL PRIMARY KEY,
    asin TEXT NOT NULL UNIQUE,
    product_data JSONB NOT NULL DEFAULT '{}',
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ═══════════════════════════════════════════════════════════
-- PRODUCTS
-- ═══════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    asin TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL DEFAULT '',
    category TEXT DEFAULT '',
    amazon_price REAL DEFAULT 0.0,
    rating REAL DEFAULT 0.0,
    review_count INTEGER DEFAULT 0,
    ai_score REAL DEFAULT 0.0,
    estimated_margin_pct REAL DEFAULT 0.0,
    traffic_light TEXT DEFAULT 'RED',
    priority_tier TEXT DEFAULT '',
    supplier_price REAL DEFAULT 0.0,
    seller_info JSONB DEFAULT '{}',
    full_data JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ═══════════════════════════════════════════════════════════
-- PRICE HISTORY
-- ═══════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS price_history (
    id SERIAL PRIMARY KEY,
    asin TEXT NOT NULL,
    product_name TEXT DEFAULT '',
    source TEXT DEFAULT '',
    price REAL DEFAULT 0.0,
    old_price REAL DEFAULT 0.0,
    in_stock INTEGER DEFAULT 1,
    rating REAL DEFAULT 0.0,
    review_count INTEGER DEFAULT 0,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ═══════════════════════════════════════════════════════════
-- REVIEW SENTIMENT
-- ═══════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS review_sentiment (
    id SERIAL PRIMARY KEY,
    asin TEXT NOT NULL,
    product_name TEXT DEFAULT '',
    total_reviews INTEGER DEFAULT 0,
    positive_pct REAL DEFAULT 0.0,
    negative_pct REAL DEFAULT 0.0,
    neutral_pct REAL DEFAULT 0.0,
    top_complaints JSONB DEFAULT '[]',
    top_praises JSONB DEFAULT '[]',
    recurring_issues JSONB DEFAULT '[]',
    improvement_ideas JSONB DEFAULT '[]',
    summary TEXT DEFAULT '',
    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ═══════════════════════════════════════════════════════════
-- SEASONALITY
-- ═══════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS seasonality_data (
    id SERIAL PRIMARY KEY,
    asin TEXT NOT NULL,
    product_name TEXT DEFAULT '',
    month INTEGER DEFAULT 0,
    demand_level TEXT DEFAULT 'medium',
    search_volume REAL DEFAULT 0.0,
    sales_estimate REAL DEFAULT 0.0,
    peak_months TEXT DEFAULT '',
    low_months TEXT DEFAULT '',
    season_pattern TEXT DEFAULT '',
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ═══════════════════════════════════════════════════════════
-- COMPETITOR TRACKING
-- ═══════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS competitor_tracking (
    id SERIAL PRIMARY KEY,
    asin TEXT NOT NULL,
    product_name TEXT DEFAULT '',
    competitor_asin TEXT DEFAULT '',
    competitor_name TEXT DEFAULT '',
    competitor_price REAL DEFAULT 0.0,
    competitor_rating REAL DEFAULT 0.0,
    competitor_reviews INTEGER DEFAULT 0,
    competitor_rank INTEGER DEFAULT 0,
    in_stock INTEGER DEFAULT 1,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ═══════════════════════════════════════════════════════════
-- INVENTORY
-- ═══════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS inventory (
    id SERIAL PRIMARY KEY,
    asin TEXT NOT NULL UNIQUE,
    product_name TEXT DEFAULT '',
    sku TEXT DEFAULT '',
    current_stock INTEGER DEFAULT 0,
    reorder_point INTEGER DEFAULT 10,
    reorder_quantity INTEGER DEFAULT 100,
    unit_cost REAL DEFAULT 0.0,
    fba_shipment_id TEXT DEFAULT '',
    fba_status TEXT DEFAULT '',
    warehouse TEXT DEFAULT '',
    last_restock_date TEXT DEFAULT '',
    days_of_stock INTEGER DEFAULT 0,
    monthly_velocity REAL DEFAULT 0.0,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ═══════════════════════════════════════════════════════════
-- COMMENTS & TASKS
-- ═══════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS product_comments (
    id SERIAL PRIMARY KEY,
    asin TEXT NOT NULL,
    author TEXT DEFAULT '',
    comment TEXT DEFAULT '',
    comment_type TEXT DEFAULT 'note',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS product_tasks (
    id SERIAL PRIMARY KEY,
    asin TEXT NOT NULL,
    product_name TEXT DEFAULT '',
    task TEXT DEFAULT '',
    assignee TEXT DEFAULT 'Unassigned',
    priority TEXT DEFAULT 'medium',
    status TEXT DEFAULT 'todo',
    due_date TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ═══════════════════════════════════════════════════════════
-- USERS & AUTH
-- ═══════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    email TEXT DEFAULT '',
    password_hash TEXT NOT NULL,
    display_name TEXT DEFAULT '',
    is_active INTEGER DEFAULT 1,
    is_admin INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tier TEXT NOT NULL DEFAULT 'free',
    start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expiry_date TIMESTAMP,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ═══════════════════════════════════════════════════════════
-- LISTING VERSIONS
-- ═══════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS listing_versions (
    id SERIAL PRIMARY KEY,
    asin TEXT NOT NULL,
    user_id INTEGER,
    version_number INTEGER DEFAULT 1,
    title TEXT DEFAULT '',
    bullets JSONB DEFAULT '[]',
    description TEXT DEFAULT '',
    search_terms TEXT DEFAULT '',
    backend_keywords TEXT DEFAULT '',
    seo_score INTEGER DEFAULT 0,
    compliance_data JSONB DEFAULT '{}',
    keywords JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ═══════════════════════════════════════════════════════════
-- INDEXES
-- ═══════════════════════════════════════════════════════════
CREATE INDEX IF NOT EXISTS idx_suppliers_name ON suppliers(name);
CREATE INDEX IF NOT EXISTS idx_suppliers_rating ON suppliers(rating);
CREATE INDEX IF NOT EXISTS idx_supplier_products_supplier ON supplier_products(supplier_id);
CREATE INDEX IF NOT EXISTS idx_supplier_products_asin ON supplier_products(asin);
CREATE INDEX IF NOT EXISTS idx_product_pricing_asin ON product_pricing(asin);
CREATE INDEX IF NOT EXISTS idx_product_cache_asin ON product_cache(asin);
CREATE INDEX IF NOT EXISTS idx_products_asin ON products(asin);
CREATE INDEX IF NOT EXISTS idx_products_ai_score ON products(ai_score DESC);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
CREATE INDEX IF NOT EXISTS idx_price_history_asin ON price_history(asin);
CREATE INDEX IF NOT EXISTS idx_price_history_recorded ON price_history(recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_review_sentiment_asin ON review_sentiment(asin);
CREATE INDEX IF NOT EXISTS idx_seasonality_asin ON seasonality_data(asin);
CREATE INDEX IF NOT EXISTS idx_competitor_asin ON competitor_tracking(asin);
CREATE INDEX IF NOT EXISTS idx_inventory_asin ON inventory(asin);
CREATE INDEX IF NOT EXISTS idx_comments_asin ON product_comments(asin);
CREATE INDEX IF NOT EXISTS idx_tasks_asin ON product_tasks(asin);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_tier ON subscriptions(tier);
CREATE INDEX IF NOT EXISTS idx_listing_versions_asin ON listing_versions(asin);

-- Done
