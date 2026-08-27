-- ══════════════════════════════════════════════════════════════
-- MARKETLENS BILLING SYSTEM - Stripe Integration Schema
-- ══════════════════════════════════════════════════════════════

-- ══════════════════════════════════════════════════════════════
-- 1. STRIPE CUSTOMER MAPPING
-- ══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS billing_customers (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    stripe_customer_id TEXT UNIQUE NOT NULL,
    email TEXT DEFAULT '',
    name TEXT DEFAULT '',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ══════════════════════════════════════════════════════════════
-- 2. BILLING SUBSCRIPTIONS (authoritative source)
-- ══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS billing_subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    billing_customer_id INTEGER REFERENCES billing_customers(id),
    plan_id INTEGER REFERENCES admin_plans(id),
    stripe_subscription_id TEXT UNIQUE,
    stripe_price_id TEXT DEFAULT '',
    status TEXT DEFAULT 'incomplete',
    -- incomplete, active, past_due, cancelled, unpaid, trialing, paused, expired
    billing_cycle TEXT DEFAULT 'monthly',
    -- monthly, yearly
    current_period_start TIMESTAMP,
    current_period_end TIMESTAMP,
    cancel_at_period_end BOOLEAN DEFAULT FALSE,
    cancelled_at TIMESTAMP,
    trial_start TIMESTAMP,
    trial_end TIMESTAMP,
    ai_credits_used INTEGER DEFAULT 0,
    research_used INTEGER DEFAULT 0,
    tracking_used INTEGER DEFAULT 0,
    supplier_search_used INTEGER DEFAULT 0,
    listing_gen_used INTEGER DEFAULT 0,
    export_used INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ══════════════════════════════════════════════════════════════
-- 3. PAYMENT RECORDS
-- ══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS billing_payments (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    subscription_id INTEGER REFERENCES billing_subscriptions(id) ON DELETE SET NULL,
    stripe_payment_intent_id TEXT,
    stripe_invoice_id TEXT,
    amount INTEGER DEFAULT 0,
    -- amount in cents
    currency TEXT DEFAULT 'usd',
    status TEXT DEFAULT 'pending',
    -- pending, succeeded, failed, refunded, partially_refunded, cancelled
    payment_method_type TEXT DEFAULT '',
    payment_method_last4 TEXT DEFAULT '',
    payment_method_brand TEXT DEFAULT '',
    description TEXT DEFAULT '',
    receipt_url TEXT DEFAULT '',
    refund_amount INTEGER DEFAULT 0,
    refund_reason TEXT DEFAULT '',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ══════════════════════════════════════════════════════════════
-- 4. INVOICES
-- ══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS billing_invoices (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    subscription_id INTEGER REFERENCES billing_subscriptions(id) ON DELETE SET NULL,
    stripe_invoice_id TEXT UNIQUE,
    invoice_number TEXT DEFAULT '',
    amount_due INTEGER DEFAULT 0,
    amount_paid INTEGER DEFAULT 0,
    amount_refunded INTEGER DEFAULT 0,
    currency TEXT DEFAULT 'usd',
    status TEXT DEFAULT 'draft',
    -- draft, open, paid, void, uncollectible
    invoice_url TEXT DEFAULT '',
    invoice_pdf TEXT DEFAULT '',
    period_start TIMESTAMP,
    period_end TIMESTAMP,
    billing_reason TEXT DEFAULT '',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ══════════════════════════════════════════════════════════════
-- 5. WEBHOOK EVENTS (idempotency)
-- ══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS billing_webhook_events (
    id SERIAL PRIMARY KEY,
    stripe_event_id TEXT UNIQUE NOT NULL,
    event_type TEXT NOT NULL,
    status TEXT DEFAULT 'received',
    -- received, processing, processed, failed, ignored
    payload JSONB DEFAULT '{}',
    error TEXT DEFAULT '',
    retry_count INTEGER DEFAULT 0,
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_webhook_event_type ON billing_webhook_events(event_type);
CREATE INDEX IF NOT EXISTS idx_webhook_event_status ON billing_webhook_events(status);
CREATE INDEX IF NOT EXISTS idx_webhook_event_created ON billing_webhook_events(created_at DESC);

-- ══════════════════════════════════════════════════════════════
-- 6. PROMO CODES
-- ══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS billing_promo_codes (
    id SERIAL PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    stripe_promo_code_id TEXT DEFAULT '',
    discount_type TEXT DEFAULT 'percentage',
    -- percentage, fixed_amount
    discount_value INTEGER DEFAULT 0,
    -- percentage (1-100) or amount in cents
    currency TEXT DEFAULT 'usd',
    max_uses INTEGER DEFAULT 0,
    -- 0 = unlimited
    used_count INTEGER DEFAULT 0,
    eligible_plans JSONB DEFAULT '[]',
    -- array of plan slugs, empty = all plans
    duration TEXT DEFAULT 'once',
    -- once, repeating, forever
    duration_in_months INTEGER DEFAULT 0,
    expires_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ══════════════════════════════════════════════════════════════
-- 7. ADMIN SUBSCRIPTION OVERRIDES (grants)
-- ══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS billing_overrides (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_id INTEGER REFERENCES admin_plans(id),
    granted_by INTEGER REFERENCES admin_users(id),
    reason TEXT DEFAULT '',
    start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_date TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ══════════════════════════════════════════════════════════════
-- 8. BILLING AUDIT LOG
-- ══════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS billing_audit_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER,
    admin_id INTEGER,
    action TEXT NOT NULL,
    entity_type TEXT DEFAULT '',
    entity_id INTEGER DEFAULT 0,
    previous_value JSONB,
    new_value JSONB,
    reason TEXT DEFAULT '',
    ip_address TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ══════════════════════════════════════════════════════════════
-- 9. INDEXES
-- ══════════════════════════════════════════════════════════════

CREATE INDEX IF NOT EXISTS idx_billing_customer_user ON billing_customers(user_id);
CREATE INDEX IF NOT EXISTS idx_billing_customer_stripe ON billing_customers(stripe_customer_id);
CREATE INDEX IF NOT EXISTS idx_billing_sub_user ON billing_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_billing_sub_stripe ON billing_subscriptions(stripe_subscription_id);
CREATE INDEX IF NOT EXISTS idx_billing_sub_status ON billing_subscriptions(status);
CREATE INDEX IF NOT EXISTS idx_billing_sub_plan ON billing_subscriptions(plan_id);
CREATE INDEX IF NOT EXISTS idx_billing_payments_user ON billing_payments(user_id);
CREATE INDEX IF NOT EXISTS idx_billing_payments_status ON billing_payments(status);
CREATE INDEX IF NOT EXISTS idx_billing_payments_stripe ON billing_payments(stripe_payment_intent_id);
CREATE INDEX IF NOT EXISTS idx_billing_invoices_user ON billing_invoices(user_id);
CREATE INDEX IF NOT EXISTS idx_billing_invoices_stripe ON billing_invoices(stripe_invoice_id);
CREATE INDEX IF NOT EXISTS idx_billing_invoices_status ON billing_invoices(status);
CREATE INDEX IF NOT EXISTS idx_billing_promo_code ON billing_promo_codes(code);
CREATE INDEX IF NOT EXISTS idx_billing_override_user ON billing_overrides(user_id);
CREATE INDEX IF NOT EXISTS idx_billing_audit_user ON billing_audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_billing_audit_action ON billing_audit_log(action);
CREATE INDEX IF NOT EXISTS idx_billing_audit_created ON billing_audit_log(created_at DESC);

-- ══════════════════════════════════════════════════════════════
-- 10. SEED DEFAULT PLANS (ensure Stripe price IDs placeholder)
-- ══════════════════════════════════════════════════════════════

-- Add stripe_price_id columns to admin_plans if not exists
ALTER TABLE admin_plans ADD COLUMN IF NOT EXISTS stripe_price_id_monthly TEXT DEFAULT '';
ALTER TABLE admin_plans ADD COLUMN IF NOT EXISTS stripe_price_id_yearly TEXT DEFAULT '';
ALTER TABLE admin_plans ADD COLUMN IF NOT EXISTS stripe_product_id TEXT DEFAULT '';
ALTER TABLE admin_plans ADD COLUMN IF NOT EXISTS description TEXT DEFAULT '';
ALTER TABLE admin_plans ADD COLUMN IF NOT EXISTS features JSONB DEFAULT '{}';

-- Update plan descriptions
UPDATE admin_plans SET description = 'For users getting started with product research' WHERE slug = 'free';
UPDATE admin_plans SET description = 'For serious product researchers and sellers' WHERE slug = 'pro';
UPDATE admin_plans SET description = 'For advanced sellers and growing teams' WHERE slug = 'business';

-- Update plan features JSON
UPDATE admin_plans SET features = '{
    "product_research": true,
    "ai_analysis": "limited",
    "product_ideas": "limited",
    "tracking": false,
    "supplier_sourcing": "limited",
    "listing_generator": "limited",
    "analytics": "basic",
    "api_access": false,
    "export": "limited",
    "team_features": false,
    "priority_support": false
}' WHERE slug = 'free';

UPDATE admin_plans SET features = '{
    "product_research": true,
    "ai_analysis": true,
    "product_ideas": true,
    "tracking": true,
    "supplier_sourcing": true,
    "listing_generator": true,
    "analytics": "advanced",
    "api_access": false,
    "export": true,
    "team_features": false,
    "priority_support": false
}' WHERE slug = 'pro';

UPDATE admin_plans SET features = '{
    "product_research": true,
    "ai_analysis": true,
    "product_ideas": true,
    "tracking": true,
    "supplier_sourcing": true,
    "listing_generator": true,
    "analytics": "advanced",
    "api_access": true,
    "export": true,
    "team_features": true,
    "priority_support": true
}' WHERE slug = 'business';
