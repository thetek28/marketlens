-- ══════════════════════════════════════════════════════════════
-- MARKETLENS ADMIN CENTER - Database Schema
-- ══════════════════════════════════════════════════════════════

-- Admin users (separate from regular users)
CREATE TABLE IF NOT EXISTS admin_users (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'support',  -- super_admin, admin, support, data_admin, billing
    display_name TEXT DEFAULT '',
    is_active BOOLEAN DEFAULT TRUE,
    mfa_enabled BOOLEAN DEFAULT FALSE,
    mfa_secret TEXT,
    last_login TIMESTAMP,
    last_ip TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Admin roles and permissions
CREATE TABLE IF NOT EXISTS admin_roles (
    id SERIAL PRIMARY KEY,
    role_name TEXT NOT NULL UNIQUE,
    permissions JSONB DEFAULT '[]',
    description TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default roles
INSERT INTO admin_roles (role_name, permissions, description) VALUES
('super_admin', '["*"]', 'Full access to everything'),
('admin', '["users.read","users.write","subscriptions.read","subscriptions.write","products.read","products.write","research.read","suppliers.read","suppliers.write","credits.read","credits.write","support.read","support.write","audit.read"]', 'Manage users, subscriptions, data, credits'),
('support', '["users.read","subscriptions.read","usage.read","support.read","support.write","audit.read"]', 'View users, subscriptions, support'),
('data_admin', '["products.read","products.write","research.read","research.write","suppliers.read","suppliers.write","data_sources.read","data_sources.write","sync.read","sync.write"]', 'Manage product data, research, suppliers, data sources'),
('billing', '["subscriptions.read","subscriptions.write","plans.read","plans.write","credits.read","credits.write","payments.read","usage.read"]', 'Manage subscriptions, plans, billing, credits')
ON CONFLICT (role_name) DO NOTHING;

-- Plans
CREATE TABLE IF NOT EXISTS admin_plans (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    slug TEXT NOT NULL UNIQUE,
    price_monthly REAL DEFAULT 0,
    price_yearly REAL DEFAULT 0,
    currency TEXT DEFAULT 'USD',
    ai_credits_monthly INTEGER DEFAULT 0,
    research_limit INTEGER DEFAULT 0,
    tracking_limit INTEGER DEFAULT 0,
    supplier_search_limit INTEGER DEFAULT 0,
    listing_gen_limit INTEGER DEFAULT 0,
    export_limit INTEGER DEFAULT 0,
    api_access BOOLEAN DEFAULT FALSE,
    advanced_analytics BOOLEAN DEFAULT FALSE,
    product_ideas_access TEXT DEFAULT 'limited',  -- none, limited, full
    history_retention_days INTEGER DEFAULT 30,
    team_members INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,
    is_default BOOLEAN DEFAULT FALSE,
    features JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default plans
INSERT INTO admin_plans (name, slug, price_monthly, price_yearly, ai_credits_monthly, research_limit, tracking_limit, supplier_search_limit, listing_gen_limit, export_limit, api_access, advanced_analytics, product_ideas_access, history_retention_days, is_default) VALUES
('Free', 'free', 0, 0, 50, 10, 5, 3, 2, 5, FALSE, FALSE, 'limited', 7, TRUE),
('Pro', 'pro', 29.99, 299.99, 500, 100, 50, 25, 20, 50, FALSE, TRUE, 'full', 90, FALSE),
('Business', 'business', 79.99, 799.99, 2000, 500, 200, 100, 100, 200, TRUE, TRUE, 'full', 365, FALSE)
ON CONFLICT (name) DO NOTHING;

-- Subscriptions (links users to plans)
CREATE TABLE IF NOT EXISTS admin_subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    plan_id INTEGER NOT NULL REFERENCES admin_plans(id),
    status TEXT NOT NULL DEFAULT 'active',  -- active, trial, past_due, cancelled, expired, paused
    billing_cycle TEXT DEFAULT 'monthly',  -- monthly, yearly
    start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_date TIMESTAMP,
    renewal_date TIMESTAMP,
    trial_end_date TIMESTAMP,
    cancelled_at TIMESTAMP,
    cancel_reason TEXT,
    ai_credits_used INTEGER DEFAULT 0,
    ai_credits_limit INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Feature flags
CREATE TABLE IF NOT EXISTS admin_feature_flags (
    id SERIAL PRIMARY KEY,
    flag_name TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT '',
    is_enabled BOOLEAN DEFAULT FALSE,
    scope TEXT DEFAULT 'global',  -- global, plan, user
    scope_value TEXT DEFAULT '',
    rollout_percentage INTEGER DEFAULT 100,
    created_by INTEGER REFERENCES admin_users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Audit logs (append-only)
CREATE TABLE IF NOT EXISTS admin_audit_logs (
    id SERIAL PRIMARY KEY,
    admin_id INTEGER REFERENCES admin_users(id),
    admin_email TEXT NOT NULL,
    action TEXT NOT NULL,
    target_type TEXT DEFAULT '',
    target_id TEXT DEFAULT '',
    previous_value JSONB,
    new_value JSONB,
    reason TEXT DEFAULT '',
    ip_address TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- System settings
CREATE TABLE IF NOT EXISTS admin_system_settings (
    id SERIAL PRIMARY KEY,
    setting_key TEXT NOT NULL UNIQUE,
    setting_value JSONB DEFAULT '{}',
    setting_type TEXT DEFAULT 'general',  -- general, security, billing, maintenance
    description TEXT DEFAULT '',
    requires_restart BOOLEAN DEFAULT FALSE,
    updated_by INTEGER REFERENCES admin_users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default system settings
INSERT INTO admin_system_settings (setting_key, setting_value, setting_type, description) VALUES
('default_marketplace', '"US"', 'general', 'Default marketplace for new users'),
('default_currency', '"USD"', 'general', 'Default currency'),
('maintenance_mode', 'false', 'maintenance', 'Enable maintenance mode'),
('maintenance_message', '"System maintenance in progress. Please try again later."', 'maintenance', 'Message shown during maintenance'),
('max_research_per_day', '100', 'general', 'Max research jobs per user per day'),
('ai_provider', '"openai"', 'general', 'Active AI provider'),
('ai_model', '"gpt-4"', 'general', 'Active AI model'),
('data_refresh_interval_minutes', '60', 'general', 'Data refresh interval'),
('backup_retention_days', '30', 'general', 'Backup retention period'),
('audit_log_retention_days', '365', 'security', 'Audit log retention')
ON CONFLICT (setting_key) DO NOTHING;

-- Background jobs
CREATE TABLE IF NOT EXISTS admin_jobs (
    id SERIAL PRIMARY KEY,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',  -- queued, running, completed, failed, cancelled
    user_id INTEGER,
    payload JSONB DEFAULT '{}',
    result JSONB DEFAULT '{}',
    error TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Admin notifications
CREATE TABLE IF NOT EXISTS admin_notifications (
    id SERIAL PRIMARY KEY,
    admin_id INTEGER REFERENCES admin_users(id),
    notification_type TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT DEFAULT '',
    severity TEXT DEFAULT 'info',  -- info, warning, error, critical
    is_read BOOLEAN DEFAULT FALSE,
    action_url TEXT DEFAULT '',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Support tickets
CREATE TABLE IF NOT EXISTS admin_support_tickets (
    id SERIAL PRIMARY KEY,
    user_id INTEGER,
    subject TEXT NOT NULL,
    status TEXT DEFAULT 'open',  -- open, in_progress, waiting, resolved, closed
    priority TEXT DEFAULT 'medium',  -- low, medium, high, urgent
    assigned_to INTEGER REFERENCES admin_users(id),
    category TEXT DEFAULT 'general',
    last_response_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Backup records
CREATE TABLE IF NOT EXISTS admin_backups (
    id SERIAL PRIMARY KEY,
    backup_type TEXT NOT NULL,  -- full, incremental, database_only
    status TEXT NOT NULL DEFAULT 'pending',  -- pending, running, completed, failed
    file_path TEXT DEFAULT '',
    file_size BIGINT DEFAULT 0,
    database_size BIGINT DEFAULT 0,
    created_by INTEGER REFERENCES admin_users(id),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_ms INTEGER,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Server health snapshots
CREATE TABLE IF NOT EXISTS admin_health_snapshots (
    id SERIAL PRIMARY KEY,
    cpu_usage REAL DEFAULT 0,
    memory_usage REAL DEFAULT 0,
    disk_usage REAL DEFAULT 0,
    database_status TEXT DEFAULT 'unknown',
    api_status TEXT DEFAULT 'unknown',
    worker_status TEXT DEFAULT 'unknown',
    response_time_ms INTEGER DEFAULT 0,
    error_rate REAL DEFAULT 0,
    active_connections INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_admin_users_username ON admin_users(username);
CREATE INDEX IF NOT EXISTS idx_admin_users_email ON admin_users(email);
CREATE INDEX IF NOT EXISTS idx_admin_users_role ON admin_users(role);
CREATE INDEX IF NOT EXISTS idx_admin_subscriptions_user_id ON admin_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_admin_subscriptions_plan_id ON admin_subscriptions(plan_id);
CREATE INDEX IF NOT EXISTS idx_admin_subscriptions_status ON admin_subscriptions(status);
CREATE INDEX IF NOT EXISTS idx_admin_audit_logs_admin_id ON admin_audit_logs(admin_id);
CREATE INDEX IF NOT EXISTS idx_admin_audit_logs_action ON admin_audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_admin_audit_logs_created_at ON admin_audit_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_admin_jobs_status ON admin_jobs(status);
CREATE INDEX IF NOT EXISTS idx_admin_jobs_type ON admin_jobs(job_type);
CREATE INDEX IF NOT EXISTS idx_admin_jobs_created_at ON admin_jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_admin_notifications_admin_id ON admin_notifications(admin_id);
CREATE INDEX IF NOT EXISTS idx_admin_notifications_read ON admin_notifications(is_read);
CREATE INDEX IF NOT EXISTS idx_admin_health_snapshots_created_at ON admin_health_snapshots(created_at);

-- ══════════════════════════════════════════════════════════════
-- SEED DEFAULT SUPER ADMIN
-- ══════════════════════════════════════════════════════════════
INSERT INTO admin_users (username, email, password_hash, role, display_name)
VALUES ('admin', 'admin@marketlens.com', '$2b$12$hvAnaG28/TZo9f7l6r/sz.M2qzeJOnwcoUX2VP5dn99rm/OT8BdJ2', 'super_admin', 'Super Admin')
ON CONFLICT (username) DO NOTHING;
