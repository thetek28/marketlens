-- ══════════════════════════════════════════════════════════════
-- MARKETLENS UNIFIED SCHEMA - Admin + User Integration
-- ══════════════════════════════════════════════════════════════

-- ══════════════════════════════════════════════════════════════
-- 1. ENHANCE EXISTING TABLES
-- ══════════════════════════════════════════════════════════════

-- Products: add user_id for user-specific state (notes, tags, custom data)
ALTER TABLE products ADD COLUMN IF NOT EXISTS user_id INTEGER;
ALTER TABLE products ADD COLUMN IF NOT EXISTS notes TEXT DEFAULT '';
ALTER TABLE products ADD COLUMN IF NOT EXISTS custom_tags JSONB DEFAULT '[]';
ALTER TABLE products ADD COLUMN IF NOT EXISTS is_tracked BOOLEAN DEFAULT FALSE;
ALTER TABLE products ADD COLUMN IF NOT EXISTS is_watchlisted BOOLEAN DEFAULT FALSE;

-- Suppliers: add user_id for user-created suppliers
ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS user_id INTEGER;

-- supplier_products: add user_id
ALTER TABLE supplier_products ADD COLUMN IF NOT EXISTS user_id INTEGER;

-- price_history: add user_id
ALTER TABLE price_history ADD COLUMN IF NOT EXISTS user_id INTEGER;

-- inventory: add user_id
ALTER TABLE inventory ADD COLUMN IF NOT EXISTS user_id INTEGER;

-- product_comments: add user_id (replace author text)
ALTER TABLE product_comments ADD COLUMN IF NOT EXISTS user_id INTEGER;

-- product_tasks: add user_id
ALTER TABLE product_tasks ADD COLUMN IF NOT EXISTS user_id INTEGER;

-- ══════════════════════════════════════════════════════════════
-- 2. ENHANCED SUBSCRIPTIONS (credit system)
-- ══════════════════════════════════════════════════════════════

-- Add credit columns to existing subscriptions
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS ai_credits_used INTEGER DEFAULT 0;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS ai_credits_limit INTEGER DEFAULT 50;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS research_used INTEGER DEFAULT 0;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS research_limit INTEGER DEFAULT 10;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS tracking_used INTEGER DEFAULT 0;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS tracking_limit INTEGER DEFAULT 5;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS supplier_search_used INTEGER DEFAULT 0;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS supplier_search_limit INTEGER DEFAULT 3;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS listing_gen_used INTEGER DEFAULT 0;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS listing_gen_limit INTEGER DEFAULT 2;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS export_used INTEGER DEFAULT 0;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS export_limit INTEGER DEFAULT 5;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS billing_cycle TEXT DEFAULT 'monthly';
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS renewal_date TIMESTAMP;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMP;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS cancel_reason TEXT;

-- Update existing free subscriptions with default limits
UPDATE subscriptions SET
    ai_credits_limit = 50, research_limit = 10, tracking_limit = 5,
    supplier_search_limit = 3, listing_gen_limit = 2, export_limit = 5
WHERE tier = 'free' AND ai_credits_limit = 0;

-- ══════════════════════════════════════════════════════════════
-- 3. USER-OWNED TABLES
-- ══════════════════════════════════════════════════════════════

-- Watchlist (user's saved products to monitor)
CREATE TABLE IF NOT EXISTS user_watchlist (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    asin TEXT NOT NULL,
    product_name TEXT DEFAULT '',
    category TEXT DEFAULT '',
    amazon_price REAL DEFAULT 0,
    rating REAL DEFAULT 0,
    review_count INTEGER DEFAULT 0,
    ai_score REAL DEFAULT 0,
    traffic_light TEXT DEFAULT 'RED',
    notes TEXT DEFAULT '',
    priority INTEGER DEFAULT 0,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, asin)
);

-- Tracking (user's actively tracked products)
CREATE TABLE IF NOT EXISTS user_tracking (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    asin TEXT NOT NULL,
    product_name TEXT DEFAULT '',
    category TEXT DEFAULT '',
    amazon_price REAL DEFAULT 0,
    rating REAL DEFAULT 0,
    review_count INTEGER DEFAULT 0,
    target_price REAL DEFAULT 0,
    alert_on_price_drop BOOLEAN DEFAULT TRUE,
    alert_on_review_milestone BOOLEAN DEFAULT FALSE,
    alert_on_stock_change BOOLEAN DEFAULT FALSE,
    last_checked_at TIMESTAMP,
    status TEXT DEFAULT 'active',
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, asin)
);

-- Research jobs (tracks user research activity)
CREATE TABLE IF NOT EXISTS research_jobs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    query TEXT NOT NULL DEFAULT '',
    marketplace TEXT DEFAULT 'US',
    category TEXT DEFAULT '',
    status TEXT DEFAULT 'queued',
    result_count INTEGER DEFAULT 0,
    ai_analysis_used BOOLEAN DEFAULT FALSE,
    ai_credits_cost INTEGER DEFAULT 0,
    error TEXT DEFAULT '',
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User notifications (centered notification system)
CREATE TABLE IF NOT EXISTS user_notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    notification_type TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT DEFAULT '',
    severity TEXT DEFAULT 'info',
    is_read BOOLEAN DEFAULT FALSE,
    action_url TEXT DEFAULT '',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User analytics events
CREATE TABLE IF NOT EXISTS user_analytics (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    event_data JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- AI usage tracking (per-user credit consumption)
CREATE TABLE IF NOT EXISTS ai_usage_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action_type TEXT NOT NULL,
    credits_cost INTEGER DEFAULT 0,
    description TEXT DEFAULT '',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User settings (per-user preferences)
CREATE TABLE IF NOT EXISTS user_settings (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    setting_key TEXT NOT NULL,
    setting_value TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, setting_key)
);

-- ══════════════════════════════════════════════════════════════
-- 4. AUDIT LOGGING (admin actions on users)
-- ══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS admin_action_log (
    id SERIAL PRIMARY KEY,
    admin_user_id INTEGER,
    admin_username TEXT NOT NULL,
    target_user_id INTEGER,
    target_username TEXT DEFAULT '',
    action TEXT NOT NULL,
    previous_value JSONB,
    new_value JSONB,
    reason TEXT DEFAULT '',
    ip_address TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ══════════════════════════════════════════════════════════════
-- 5. INDEXES
-- ══════════════════════════════════════════════════════════════

CREATE INDEX IF NOT EXISTS idx_products_user ON products(user_id);
CREATE INDEX IF NOT EXISTS idx_products_tracked ON products(is_tracked) WHERE is_tracked = TRUE;
CREATE INDEX IF NOT EXISTS idx_products_watchlisted ON products(is_watchlisted) WHERE is_watchlisted = TRUE;
CREATE INDEX IF NOT EXISTS idx_suppliers_user ON suppliers(user_id);
CREATE INDEX IF NOT EXISTS idx_watchlist_user ON user_watchlist(user_id);
CREATE INDEX IF NOT EXISTS idx_watchlist_asin ON user_watchlist(asin);
CREATE INDEX IF NOT EXISTS idx_tracking_user ON user_tracking(user_id);
CREATE INDEX IF NOT EXISTS idx_tracking_asin ON user_tracking(asin);
CREATE INDEX IF NOT EXISTS idx_tracking_status ON user_tracking(status);
CREATE INDEX IF NOT EXISTS idx_research_user ON research_jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_research_status ON research_jobs(status);
CREATE INDEX IF NOT EXISTS idx_research_created ON research_jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_notif_user ON user_notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_user_notif_read ON user_notifications(is_read);
CREATE INDEX IF NOT EXISTS idx_user_analytics_user ON user_analytics(user_id);
CREATE INDEX IF NOT EXISTS idx_user_analytics_type ON user_analytics(event_type);
CREATE INDEX IF NOT EXISTS idx_ai_usage_user ON ai_usage_log(user_id);
CREATE INDEX IF NOT EXISTS idx_ai_usage_created ON ai_usage_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_settings_user ON user_settings(user_id);
CREATE INDEX IF NOT EXISTS idx_admin_action_log_admin ON admin_action_log(admin_user_id);
CREATE INDEX IF NOT EXISTS idx_admin_action_log_target ON admin_action_log(target_user_id);
CREATE INDEX IF NOT EXISTS idx_admin_action_log_created ON admin_action_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_comments_user ON product_comments(user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_user ON product_tasks(user_id);
