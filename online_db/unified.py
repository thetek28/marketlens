"""Unified Database Manager for MarketLens.

Single source of truth for all data operations.
Handles user ownership, subscriptions, credits, features, and admin operations.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)


class UnifiedDB:
    """Unified database manager - single source of truth for all MarketLens data."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self._ensure_schema()

    def _conn(self):
        conn = psycopg2.connect(self.database_url, sslmode="require")
        with conn.cursor() as cur:
            cur.execute("SET search_path TO public, marketlens")
        conn.commit()
        return conn

    def _exec(self, query, params=(), fetch="none"):
        conn = self._conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, params)
                if fetch == "one":
                    row = cur.fetchone(); conn.commit(); return dict(row) if row else None
                elif fetch == "all":
                    rows = cur.fetchall(); conn.commit(); return [dict(r) for r in rows]
                elif fetch == "scalar":
                    val = cur.fetchone()[0] if cur.rowcount > 0 else None; conn.commit(); return val
                else:
                    conn.commit(); return cur.rowcount
        except Exception:
            conn.rollback(); raise
        finally:
            conn.close()

    def _ensure_schema(self):
        """Run unified migration on startup."""
        try:
            conn = self._conn()
            with conn.cursor() as cur:
                # Run 003_unified.sql parts inline
                for stmt in [
                    "ALTER TABLE products ADD COLUMN IF NOT EXISTS user_id INTEGER",
                    "ALTER TABLE products ADD COLUMN IF NOT EXISTS notes TEXT DEFAULT ''",
                    "ALTER TABLE products ADD COLUMN IF NOT EXISTS custom_tags JSONB DEFAULT '[]'",
                    "ALTER TABLE products ADD COLUMN IF NOT EXISTS is_tracked BOOLEAN DEFAULT FALSE",
                    "ALTER TABLE products ADD COLUMN IF NOT EXISTS is_watchlisted BOOLEAN DEFAULT FALSE",
                    "ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS user_id INTEGER",
                    "ALTER TABLE price_history ADD COLUMN IF NOT EXISTS user_id INTEGER",
                    "ALTER TABLE inventory ADD COLUMN IF NOT EXISTS user_id INTEGER",
                    "ALTER TABLE product_comments ADD COLUMN IF NOT EXISTS user_id INTEGER",
                    "ALTER TABLE product_tasks ADD COLUMN IF NOT EXISTS user_id INTEGER",
                    "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS ai_credits_used INTEGER DEFAULT 0",
                    "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS ai_credits_limit INTEGER DEFAULT 50",
                    "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS research_used INTEGER DEFAULT 0",
                    "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS research_limit INTEGER DEFAULT 10",
                    "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS tracking_used INTEGER DEFAULT 0",
                    "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS tracking_limit INTEGER DEFAULT 5",
                    "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS supplier_search_used INTEGER DEFAULT 0",
                    "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS supplier_search_limit INTEGER DEFAULT 3",
                    "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS listing_gen_used INTEGER DEFAULT 0",
                    "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS listing_gen_limit INTEGER DEFAULT 2",
                    "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS export_used INTEGER DEFAULT 0",
                    "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS export_limit INTEGER DEFAULT 5",
                    "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS billing_cycle TEXT DEFAULT 'monthly'",
                    "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS renewal_date TIMESTAMP",
                    "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMP",
                    "ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS cancel_reason TEXT",
                ]:
                    try: cur.execute(stmt)
                    except Exception: pass
                conn.commit()

                # Create new tables
                for ddl in [
                    """CREATE TABLE IF NOT EXISTS user_watchlist (
                        id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        asin TEXT NOT NULL, product_name TEXT DEFAULT '', category TEXT DEFAULT '',
                        amazon_price REAL DEFAULT 0, rating REAL DEFAULT 0, review_count INTEGER DEFAULT 0,
                        ai_score REAL DEFAULT 0, traffic_light TEXT DEFAULT 'RED', notes TEXT DEFAULT '',
                        priority INTEGER DEFAULT 0, added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, asin))""",
                    """CREATE TABLE IF NOT EXISTS user_tracking (
                        id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        asin TEXT NOT NULL, product_name TEXT DEFAULT '', category TEXT DEFAULT '',
                        amazon_price REAL DEFAULT 0, rating REAL DEFAULT 0, review_count INTEGER DEFAULT 0,
                        target_price REAL DEFAULT 0, alert_on_price_drop BOOLEAN DEFAULT TRUE,
                        alert_on_review_milestone BOOLEAN DEFAULT FALSE, alert_on_stock_change BOOLEAN DEFAULT FALSE,
                        last_checked_at TIMESTAMP, status TEXT DEFAULT 'active',
                        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id, asin))""",
                    """CREATE TABLE IF NOT EXISTS research_jobs (
                        id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        query TEXT NOT NULL DEFAULT '', marketplace TEXT DEFAULT 'US', category TEXT DEFAULT '',
                        status TEXT DEFAULT 'queued', result_count INTEGER DEFAULT 0,
                        ai_analysis_used BOOLEAN DEFAULT FALSE, ai_credits_cost INTEGER DEFAULT 0,
                        error TEXT DEFAULT '', started_at TIMESTAMP, completed_at TIMESTAMP,
                        duration_ms INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
                    """CREATE TABLE IF NOT EXISTS user_notifications (
                        id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        notification_type TEXT NOT NULL, title TEXT NOT NULL, message TEXT DEFAULT '',
                        severity TEXT DEFAULT 'info', is_read BOOLEAN DEFAULT FALSE,
                        action_url TEXT DEFAULT '', metadata JSONB DEFAULT '{}',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
                    """CREATE TABLE IF NOT EXISTS ai_usage_log (
                        id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        action_type TEXT NOT NULL, credits_cost INTEGER DEFAULT 0,
                        description TEXT DEFAULT '', metadata JSONB DEFAULT '{}',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
                    """CREATE TABLE IF NOT EXISTS user_settings (
                        id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        setting_key TEXT NOT NULL, setting_value TEXT DEFAULT '',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, setting_key))""",
                    """CREATE TABLE IF NOT EXISTS admin_action_log (
                        id SERIAL PRIMARY KEY, admin_user_id INTEGER, admin_username TEXT NOT NULL,
                        target_user_id INTEGER, target_username TEXT DEFAULT '', action TEXT NOT NULL,
                        previous_value JSONB, new_value JSONB, reason TEXT DEFAULT '',
                        ip_address TEXT DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
                ]:
                    try: cur.execute(ddl)
                    except Exception: pass
                conn.commit()

                # Indexes
                for idx in [
                    "CREATE INDEX IF NOT EXISTS idx_products_user ON products(user_id)",
                    "CREATE INDEX IF NOT EXISTS idx_watchlist_user ON user_watchlist(user_id)",
                    "CREATE INDEX IF NOT EXISTS idx_tracking_user ON user_tracking(user_id)",
                    "CREATE INDEX IF NOT EXISTS idx_research_user ON research_jobs(user_id)",
                    "CREATE INDEX IF NOT EXISTS idx_research_status ON research_jobs(status)",
                    "CREATE INDEX IF NOT EXISTS idx_user_notif_user ON user_notifications(user_id)",
                    "CREATE INDEX IF NOT EXISTS idx_ai_usage_user ON ai_usage_log(user_id)",
                    "CREATE INDEX IF NOT EXISTS idx_admin_action_log_target ON admin_action_log(target_user_id)",
                ]:
                    try: cur.execute(idx)
                    except Exception: pass
                conn.commit()

            conn.close()
            logger.info("Unified schema initialized")
        except Exception as e:
            logger.error("Schema init failed: %s", e)

    # ════════════════════════════════════════════════════════════
    # USERS
    # ════════════════════════════════════════════════════════════

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        return self._exec("SELECT id, username, email, display_name, is_active, is_admin, created_at, last_login FROM users WHERE id = %s", (user_id,), "one")

    def get_user_by_username(self, username: str) -> Optional[Dict]:
        return self._exec("SELECT id, username, email, password_hash, display_name, is_active, is_admin FROM users WHERE username = %s", (username,), "one")

    def create_user(self, username: str, password_hash: str, email: str = "") -> Optional[int]:
        row = self._exec("INSERT INTO users (username, password_hash, email) VALUES (%s, %s, %s) RETURNING id", (username, password_hash, email), "one")
        return row["id"] if row else None

    def update_user(self, user_id: int, **kwargs):
        allowed = {"email", "display_name", "is_active", "is_admin"}
        sets, vals = [], []
        for k, v in kwargs.items():
            if k in allowed:
                sets.append(f"{k} = %s"); vals.append(v)
        if sets:
            vals.append(user_id)
            self._exec(f"UPDATE users SET {', '.join(sets)} WHERE id = %s", tuple(vals))

    def set_user_active(self, user_id: int, active: bool):
        self._exec("UPDATE users SET is_active = %s WHERE id = %s", (1 if active else 0, user_id))

    def get_all_users(self, page=1, per_page=25, search="", status=""):
        where, params = [], []
        if search:
            where.append("(u.username ILIKE %s OR u.email ILIKE %s)")
            params.extend([f"%{search}%", f"%{search}%"])
        if status:
            where.append("u.is_active = %s")
            params.append(1 if status == "active" else 0)
        wc = " AND ".join(where) if where else "1=1"
        total = self._exec(f"SELECT COUNT(*) as c FROM users u WHERE {wc}", params, "one")["c"]
        offset = (page - 1) * per_page
        params.extend([per_page, offset])
        users = self._exec(f"""
            SELECT u.id, u.username, u.email, u.display_name, u.is_active, u.is_admin, u.created_at, u.last_login,
                   s.tier, s.ai_credits_used, s.ai_credits_limit, s.research_used, s.research_limit
            FROM users u
            LEFT JOIN subscriptions s ON u.id = s.user_id AND s.is_active = 1
            WHERE {wc} ORDER BY u.id DESC LIMIT %s OFFSET %s
        """, tuple(params), "all")
        return {"users": users, "total": total, "page": page, "per_page": per_page}

    # ════════════════════════════════════════════════════════════
    # SUBSCRIPTIONS & CREDITS
    # ════════════════════════════════════════════════════════════

    TIER_LIMITS = {
        "free":     {"ai_credits": 50,   "research": 10,  "tracking": 5,   "suppliers": 3,   "listings": 2,   "exports": 5},
        "pro":      {"ai_credits": 500,  "research": 100, "tracking": 50,  "suppliers": 25,  "listings": 20,  "exports": 50},
        "business": {"ai_credits": 2000, "research": 500, "tracking": 200, "suppliers": 100, "listings": 100, "exports": 200},
    }

    def get_subscription(self, user_id: int) -> Optional[Dict]:
        return self._exec(
            "SELECT * FROM subscriptions WHERE user_id = %s AND is_active = 1 ORDER BY created_at DESC LIMIT 1",
            (user_id,), "one"
        )

    def create_subscription(self, user_id: int, tier: str = "free", days: int = 30):
        limits = self.TIER_LIMITS.get(tier, self.TIER_LIMITS["free"])
        expiry = datetime.now() + timedelta(days=days) if days > 0 else None
        self._exec(
            """INSERT INTO subscriptions (user_id, tier, expiry_date, ai_credits_limit, research_limit,
               tracking_limit, supplier_search_limit, listing_gen_limit, export_limit)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (user_id, tier, expiry, limits["ai_credits"], limits["research"], limits["tracking"],
             limits["suppliers"], limits["listings"], limits["exports"])
        )

    def upgrade_subscription(self, user_id: int, tier: str, days: int = 30):
        self._exec("UPDATE subscriptions SET is_active = 0 WHERE user_id = %s AND is_active = 1", (user_id,))
        self.create_subscription(user_id, tier, days)

    def change_plan(self, user_id: int, new_tier: str):
        """Change plan and update limits."""
        limits = self.TIER_LIMITS.get(new_tier, self.TIER_LIMITS["free"])
        sub = self.get_subscription(user_id)
        if not sub:
            self.create_subscription(user_id, new_tier)
            return
        # Reset used counts on upgrade, keep on downgrade
        reset_credits = sub["ai_credits_used"] if new_tier in ("free",) and sub["tier"] in ("pro", "business") else 0
        self._exec(
            """UPDATE subscriptions SET tier=%s, ai_credits_limit=%s, research_limit=%s,
               tracking_limit=%s, supplier_search_limit=%s, listing_gen_limit=%s, export_limit=%s,
               ai_credits_used = CASE WHEN %s = 'upgrade' THEN 0 ELSE ai_credits_used END,
               research_used = CASE WHEN %s = 'upgrade' THEN 0 ELSE research_used END,
               tracking_used = CASE WHEN %s = 'upgrade' THEN 0 ELSE tracking_used END,
               supplier_search_used = CASE WHEN %s = 'upgrade' THEN 0 ELSE supplier_search_used END,
               listing_gen_used = CASE WHEN %s = 'upgrade' THEN 0 ELSE listing_gen_used END
               WHERE user_id = %s AND is_active = 1""",
            (new_tier, limits["ai_credits"], limits["research"], limits["tracking"],
             limits["suppliers"], limits["listings"], limits["exports"],
             "upgrade", "upgrade", "upgrade", "upgrade", "upgrade", user_id)
        )

    def adjust_credits(self, user_id: int, amount: int, reason: str = "") -> Dict:
        """Add or remove AI credits. Returns new balance."""
        sub = self.get_subscription(user_id)
        if not sub:
            return {"error": "No active subscription"}
        old = sub["ai_credits_used"]
        new_used = max(0, old - amount) if amount > 0 else old + abs(amount)
        # Ensure we don't exceed limit
        new_used = min(new_used, sub["ai_credits_limit"])
        self._exec("UPDATE subscriptions SET ai_credits_used = %s WHERE id = %s", (new_used, sub["id"]))
        return {"previous": old, "new": new_used, "amount": amount, "reason": reason}

    def check_credits(self, user_id: int, cost: int = 1) -> bool:
        """Check if user has enough AI credits."""
        sub = self.get_subscription(user_id)
        if not sub:
            return False
        return (sub["ai_credits_limit"] - sub["ai_credits_used"]) >= cost

    def consume_credit(self, user_id: int, action_type: str, cost: int = 1, description: str = "") -> bool:
        """Consume AI credits. Returns True if successful."""
        sub = self.get_subscription(user_id)
        if not sub:
            return False
        remaining = sub["ai_credits_limit"] - sub["ai_credits_used"]
        if remaining < cost:
            return False
        self._exec("UPDATE subscriptions SET ai_credits_used = ai_credits_used + %s WHERE id = %s", (cost, sub["id"]))
        self._exec(
            "INSERT INTO ai_usage_log (user_id, action_type, credits_cost, description) VALUES (%s, %s, %s, %s)",
            (user_id, action_type, cost, description)
        )
        return True

    def check_and_consume_usage(self, user_id: int, limit_type: str, cost: int = 1) -> bool:
        """Check and consume a usage limit (research, tracking, suppliers, listings, exports)."""
        sub = self.get_subscription(user_id)
        if not sub:
            return False
        col_used = f"{limit_type}_used"
        col_limit = f"{limit_type}_limit"
        if col_used not in sub or col_limit not in sub:
            return False
        if (sub[col_limit] - sub[col_used]) < cost:
            return False
        self._exec(f"UPDATE subscriptions SET {col_used} = {col_used} + %s WHERE id = %s", (cost, sub["id"]))
        return True

    def get_user_usage(self, user_id: int) -> Dict:
        """Get full usage breakdown for a user."""
        sub = self.get_subscription(user_id)
        if not sub:
            return {"tier": "none", "limits": {}, "used": {}, "remaining": {}}
        limits = {
            "ai_credits": sub.get("ai_credits_limit", 0),
            "research": sub.get("research_limit", 0),
            "tracking": sub.get("tracking_limit", 0),
            "suppliers": sub.get("supplier_search_limit", 0),
            "listings": sub.get("listing_gen_limit", 0),
            "exports": sub.get("export_limit", 0),
        }
        used = {
            "ai_credits": sub.get("ai_credits_used", 0),
            "research": sub.get("research_used", 0),
            "tracking": sub.get("tracking_used", 0),
            "suppliers": sub.get("supplier_search_used", 0),
            "listings": sub.get("listing_gen_used", 0),
            "exports": sub.get("export_used", 0),
        }
        remaining = {k: limits[k] - used[k] for k in limits}
        return {"tier": sub["tier"], "limits": limits, "used": used, "remaining": remaining}

    # ════════════════════════════════════════════════════════════
    # PRODUCTS (user-owned)
    # ════════════════════════════════════════════════════════════

    def get_user_products(self, user_id: int, page=1, per_page=20) -> Dict:
        total = self._exec("SELECT COUNT(*) as c FROM products WHERE user_id = %s", (user_id,), "one")["c"]
        offset = (page - 1) * per_page
        products = self._exec(
            "SELECT * FROM products WHERE user_id = %s ORDER BY updated_at DESC LIMIT %s OFFSET %s",
            (user_id, per_page, offset), "all"
        )
        return {"products": products, "total": total, "page": page, "per_page": per_page}

    def add_user_product(self, user_id: int, asin: str, data: dict = None) -> bool:
        """Add a product to user's collection (with ownership)."""
        d = data or {}
        try:
            self._exec(
                """INSERT INTO products (user_id, asin, name, category, amazon_price, rating,
                   review_count, ai_score, estimated_margin_pct, traffic_light, notes, custom_tags)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (asin) DO UPDATE SET
                     user_id = COALESCE(products.user_id, EXCLUDED.user_id),
                     notes = COALESCE(NULLIF(EXCLUDED.notes, ''), products.notes),
                     custom_tags = CASE WHEN EXCLUDED.custom_tags != '[]' THEN EXCLUDED.custom_tags ELSE products.custom_tags END,
                     updated_at = CURRENT_TIMESTAMP""",
                (user_id, asin, d.get("name", ""), d.get("category", ""), d.get("amazon_price", 0),
                 d.get("rating", 0), d.get("review_count", 0), d.get("ai_score", 0),
                 d.get("estimated_margin_pct", 0), d.get("traffic_light", "RED"),
                 d.get("notes", ""), json.dumps(d.get("custom_tags", [])))
            )
            return True
        except Exception as e:
            logger.error("Add product failed: %s", e)
            return False

    # ════════════════════════════════════════════════════════════
    # WATCHLIST
    # ════════════════════════════════════════════════════════════

    def get_watchlist(self, user_id: int) -> List[Dict]:
        return self._exec("SELECT * FROM user_watchlist WHERE user_id = %s ORDER BY added_at DESC", (user_id,), "all")

    def add_to_watchlist(self, user_id: int, asin: str, data: dict = None) -> bool:
        d = data or {}
        try:
            self._exec(
                """INSERT INTO user_watchlist (user_id, asin, product_name, category, amazon_price,
                   rating, review_count, ai_score, traffic_light, notes)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (user_id, asin) DO NOTHING""",
                (user_id, asin, d.get("name", ""), d.get("category", ""), d.get("amazon_price", 0),
                 d.get("rating", 0), d.get("review_count", 0), d.get("ai_score", 0),
                 d.get("traffic_light", "RED"), d.get("notes", ""))
            )
            return True
        except Exception:
            return False

    def remove_from_watchlist(self, user_id: int, asin: str):
        self._exec("DELETE FROM user_watchlist WHERE user_id = %s AND asin = %s", (user_id, asin))

    def is_watchlisted(self, user_id: int, asin: str) -> bool:
        r = self._exec("SELECT 1 FROM user_watchlist WHERE user_id = %s AND asin = %s", (user_id, asin), "one")
        return r is not None

    # ════════════════════════════════════════════════════════════
    # TRACKING
    # ════════════════════════════════════════════════════════════

    def get_tracking(self, user_id: int) -> List[Dict]:
        return self._exec("SELECT * FROM user_tracking WHERE user_id = %s ORDER BY added_at DESC", (user_id,), "all")

    def add_tracking(self, user_id: int, asin: str, data: dict = None) -> bool:
        d = data or {}
        try:
            self._exec(
                """INSERT INTO user_tracking (user_id, asin, product_name, category, amazon_price,
                   rating, review_count, target_price, alert_on_price_drop)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (user_id, asin) DO NOTHING""",
                (user_id, asin, d.get("name", ""), d.get("category", ""), d.get("amazon_price", 0),
                 d.get("rating", 0), d.get("review_count", 0), d.get("target_price", 0),
                 d.get("alert_on_price_drop", True))
            )
            return True
        except Exception:
            return False

    def remove_tracking(self, user_id: int, asin: str):
        self._exec("DELETE FROM user_tracking WHERE user_id = %s AND asin = %s", (user_id, asin))

    def is_tracking(self, user_id: int, asin: str) -> bool:
        r = self._exec("SELECT 1 FROM user_tracking WHERE user_id = %s AND asin = %s", (user_id, asin), "one")
        return r is not None

    # ════════════════════════════════════════════════════════════
    # RESEARCH
    # ════════════════════════════════════════════════════════════

    def create_research_job(self, user_id: int, query: str, marketplace: str = "US", category: str = "") -> int:
        row = self._exec(
            "INSERT INTO research_jobs (user_id, query, marketplace, category, status) VALUES (%s,%s,%s,%s,'queued') RETURNING id",
            (user_id, query, marketplace, category), "one"
        )
        return row["id"] if row else 0

    def update_research_job(self, job_id: int, status: str = None, result_count: int = None, error: str = None, ai_used: bool = None, credits_cost: int = None, duration_ms: int = None):
        sets, vals = [], []
        if status: sets.append("status = %s"); vals.append(status)
        if result_count is not None: sets.append("result_count = %s"); vals.append(result_count)
        if error: sets.append("error = %s"); vals.append(error)
        if ai_used is not None: sets.append("ai_analysis_used = %s"); vals.append(ai_used)
        if credits_cost is not None: sets.append("ai_credits_cost = %s"); vals.append(credits_cost)
        if duration_ms is not None: sets.append("duration_ms = %s"); vals.append(duration_ms)
        if status == "running": sets.append("started_at = CURRENT_TIMESTAMP")
        if status in ("completed", "failed"): sets.append("completed_at = CURRENT_TIMESTAMP")
        if sets:
            vals.append(job_id)
            self._exec(f"UPDATE research_jobs SET {', '.join(sets)} WHERE id = %s", tuple(vals))

    def get_user_research(self, user_id: int, page=1, per_page=20) -> Dict:
        total = self._exec("SELECT COUNT(*) as c FROM research_jobs WHERE user_id = %s", (user_id,), "one")["c"]
        offset = (page - 1) * per_page
        jobs = self._exec(
            "SELECT * FROM research_jobs WHERE user_id = %s ORDER BY created_at DESC LIMIT %s OFFSET %s",
            (user_id, per_page, offset), "all"
        )
        return {"jobs": jobs, "total": total, "page": page, "per_page": per_page}

    # ════════════════════════════════════════════════════════════
    # LISTINGS
    # ════════════════════════════════════════════════════════════

    def save_listing(self, asin: str, user_id: int, listing: dict) -> Optional[int]:
        max_ver = self._exec("SELECT COALESCE(MAX(version_number), 0) FROM listing_versions WHERE asin=%s AND user_id=%s", (asin, user_id), "scalar") or 0
        row = self._exec(
            """INSERT INTO listing_versions (asin, user_id, version_number, title, bullets,
               description, search_terms, backend_keywords, seo_score)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (asin, user_id, max_ver + 1, listing.get("title", ""),
             json.dumps(listing.get("bullets", [])), listing.get("description", ""),
             listing.get("search_terms", ""), listing.get("backend_keywords", ""),
             listing.get("seo_score", 0)), "one"
        )
        return row["id"] if row else None

    def get_user_listings(self, user_id: int) -> List[Dict]:
        return self._exec(
            "SELECT * FROM listing_versions WHERE user_id = %s ORDER BY created_at DESC",
            (user_id,), "all"
        )

    # ════════════════════════════════════════════════════════════
    # NOTIFICATIONS
    # ════════════════════════════════════════════════════════════

    def add_notification(self, user_id: int, ntype: str, title: str, message: str = "", severity: str = "info", action_url: str = ""):
        self._exec(
            "INSERT INTO user_notifications (user_id, notification_type, title, message, severity, action_url) VALUES (%s,%s,%s,%s,%s,%s)",
            (user_id, ntype, title, message, severity, action_url)
        )

    def get_notifications(self, user_id: int, unread_only: bool = False) -> List[Dict]:
        where = "AND is_read = FALSE" if unread_only else ""
        return self._exec(
            f"SELECT * FROM user_notifications WHERE user_id = %s {where} ORDER BY created_at DESC LIMIT 50",
            (user_id,), "all"
        )

    def mark_notification_read(self, user_id: int, notif_id: int):
        self._exec("UPDATE user_notifications SET is_read = TRUE WHERE id = %s AND user_id = %s", (notif_id, user_id))

    def unread_count(self, user_id: int) -> int:
        return self._exec("SELECT COUNT(*) as c FROM user_notifications WHERE user_id = %s AND is_read = FALSE", (user_id,), "one")["c"]

    # ════════════════════════════════════════════════════════════
    # ADMIN AUDIT LOG
    # ════════════════════════════════════════════════════════════

    def log_admin_action(self, admin_user_id: int, admin_username: str, target_user_id: int,
                         target_username: str, action: str, previous_value=None, new_value=None,
                         reason: str = "", ip: str = ""):
        self._exec(
            """INSERT INTO admin_action_log (admin_user_id, admin_username, target_user_id,
               target_username, action, previous_value, new_value, reason, ip_address)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (admin_user_id, admin_username, target_user_id, target_username, action,
             json.dumps(previous_value) if previous_value else None,
             json.dumps(new_value) if new_value else None, reason, ip)
        )

    def get_admin_actions(self, page=1, per_page=25) -> Dict:
        total = self._exec("SELECT COUNT(*) as c FROM admin_action_log", (), "one")["c"]
        offset = (page - 1) * per_page
        logs = self._exec(
            "SELECT * FROM admin_action_log ORDER BY created_at DESC LIMIT %s OFFSET %s",
            (per_page, offset), "all"
        )
        return {"logs": logs, "total": total, "page": page, "per_page": per_page}

    # ════════════════════════════════════════════════════════════
    # GLOBAL QUERIES (for admin dashboard)
    # ════════════════════════════════════════════════════════════

    def admin_dashboard_stats(self) -> Dict:
        users = self._exec("SELECT COUNT(*) as c FROM users", (), "one")["c"]
        active = self._exec("SELECT COUNT(*) as c FROM users WHERE is_active = 1", (), "one")["c"]
        products = self._exec("SELECT COUNT(*) as c FROM products", (), "one")["c"]
        tracked = self._exec("SELECT COUNT(*) as c FROM user_tracking WHERE status = 'active'", (), "one")["c"]
        watchlisted = self._exec("SELECT COUNT(*) as c FROM user_watchlist", (), "one")["c"]
        research_total = self._exec("SELECT COUNT(*) as c FROM research_jobs", (), "one")["c"]
        research_running = self._exec("SELECT COUNT(*) as c FROM research_jobs WHERE status = 'running'", (), "one")["c"]
        listings = self._exec("SELECT COUNT(*) as c FROM listing_versions", (), "one")["c"]
        ai_usage = self._exec("SELECT COALESCE(SUM(credits_cost), 0) as c FROM ai_usage_log", (), "one")["c"]
        # MRR from active subscriptions
        mrr = self._exec("""
            SELECT COALESCE(SUM(CASE WHEN tier='pro' THEN 29.99 WHEN tier='business' THEN 79.99 ELSE 0 END), 0) as c
            FROM subscriptions WHERE is_active = 1
        """, (), "one")["c"]
        return {
            "users": {"total": users, "active": active},
            "products": {"total": products, "tracked": tracked, "watchlisted": watchlisted},
            "research": {"total": research_total, "running": research_running},
            "listings": {"total": listings},
            "ai_usage": {"total_credits": ai_usage},
            "revenue": {"mrr": mrr},
        }

    def admin_user_detail(self, user_id: int) -> Dict:
        user = self.get_user_by_id(user_id)
        if not user:
            return {"error": "User not found"}
        sub = self.get_subscription(user_id)
        usage = self.get_user_usage(user_id)
        products_count = self._exec("SELECT COUNT(*) as c FROM products WHERE user_id = %s", (user_id,), "one")["c"]
        watchlist_count = self._exec("SELECT COUNT(*) as c FROM user_watchlist WHERE user_id = %s", (user_id,), "one")["c"]
        tracking_count = self._exec("SELECT COUNT(*) as c FROM user_tracking WHERE user_id = %s", (user_id,), "one")["c"]
        research_count = self._exec("SELECT COUNT(*) as c FROM research_jobs WHERE user_id = %s", (user_id,), "one")["c"]
        listing_count = self._exec("SELECT COUNT(*) as c FROM listing_versions WHERE user_id = %s", (user_id,), "one")["c"]
        ai_total = self._exec("SELECT COALESCE(SUM(credits_cost), 0) as c FROM ai_usage_log WHERE user_id = %s", (user_id,), "one")["c"]
        recent_actions = self._exec(
            "SELECT * FROM admin_action_log WHERE target_user_id = %s ORDER BY created_at DESC LIMIT 10",
            (user_id,), "all"
        )
        recent_research = self._exec(
            "SELECT * FROM research_jobs WHERE user_id = %s ORDER BY created_at DESC LIMIT 10",
            (user_id,), "all"
        )
        return {
            "user": user,
            "subscription": sub,
            "usage": usage,
            "stats": {
                "products": products_count, "watchlist": watchlist_count, "tracking": tracking_count,
                "research": research_count, "listings": listing_count, "ai_credits_used": ai_total,
            },
            "recent_actions": recent_actions,
            "recent_research": recent_research,
        }

    def admin_get_all_research(self, page=1, per_page=25, status="", user_id=None) -> Dict:
        where, params = [], []
        if status: where.append("r.status = %s"); params.append(status)
        if user_id: where.append("r.user_id = %s"); params.append(user_id)
        wc = " AND ".join(where) if where else "1=1"
        total = self._exec(f"SELECT COUNT(*) as c FROM research_jobs r WHERE {wc}", params, "one")["c"]
        offset = (page - 1) * per_page
        params.extend([per_page, offset])
        jobs = self._exec(f"""
            SELECT r.*, u.username FROM research_jobs r
            LEFT JOIN users u ON r.user_id = u.id
            WHERE {wc} ORDER BY r.created_at DESC LIMIT %s OFFSET %s
        """, tuple(params), "all")
        return {"jobs": jobs, "total": total, "page": page, "per_page": per_page}

    def admin_get_all_watchlists(self, page=1, per_page=25) -> Dict:
        total = self._exec("SELECT COUNT(*) as c FROM user_watchlist", (), "one")["c"]
        offset = (page - 1) * per_page
        items = self._exec("""
            SELECT w.*, u.username FROM user_watchlist w
            LEFT JOIN users u ON w.user_id = u.id
            ORDER BY w.added_at DESC LIMIT %s OFFSET %s
        """, (per_page, offset), "all")
        return {"items": items, "total": total, "page": page, "per_page": per_page}

    # ════════════════════════════════════════════════════════════
    # EXISTING QUERIES (backward compat)
    # ════════════════════════════════════════════════════════════

    def get_all_products_from_db(self) -> List[Dict]:
        rows = self._exec(
            "SELECT asin, name, category, amazon_price, rating, review_count, "
            "ai_score, estimated_margin_pct, traffic_light, priority_tier, "
            "supplier_price, seller_info, full_data, created_at, updated_at "
            "FROM products ORDER BY ai_score DESC", fetch="all")
        products = []
        for row in rows:
            try:
                fd = row.get("full_data") or {}
                if isinstance(fd, str): fd = json.loads(fd)
                product = {k: row.get(k, 0) for k in ["asin","name","category","amazon_price","rating","review_count","ai_score","estimated_margin_pct","traffic_light","priority_tier","supplier_price"]}
                if fd and isinstance(fd, dict): product.update(fd)
                products.append(product)
            except Exception:
                continue
        return products

    def batch_upsert_products(self, products: List[Dict]):
        query = """
            INSERT INTO products (asin, name, category, amazon_price, rating, review_count,
                ai_score, estimated_margin_pct, traffic_light, priority_tier, seller_info,
                supplier_price, full_data, updated_at)
            VALUES (%(asin)s, %(name)s, %(category)s, %(amazon_price)s, %(rating)s, %(review_count)s,
                %(ai_score)s, %(estimated_margin_pct)s, %(traffic_light)s, %(priority_tier)s,
                %(seller_info)s, %(supplier_price)s, %(full_data)s, CURRENT_TIMESTAMP)
            ON CONFLICT (asin) DO UPDATE SET
                name=EXCLUDED.name, category=EXCLUDED.category,
                amazon_price=EXCLUDED.amazon_price, rating=EXCLUDED.rating,
                review_count=EXCLUDED.review_count, ai_score=EXCLUDED.ai_score,
                estimated_margin_pct=EXCLUDED.estimated_margin_pct,
                traffic_light=EXCLUDED.traffic_light, priority_tier=EXCLUDED.priority_tier,
                seller_info=EXCLUDED.seller_info, supplier_price=EXCLUDED.supplier_price,
                full_data=EXCLUDED.full_data, updated_at=CURRENT_TIMESTAMP
        """
        params_list = [{
            "asin": p.get("asin", ""), "name": p.get("name", p.get("title", "")),
            "category": p.get("category", ""), "amazon_price": p.get("amazon_price", 0),
            "rating": p.get("rating", 0), "review_count": p.get("review_count", 0),
            "ai_score": p.get("ai_score", 0), "estimated_margin_pct": p.get("estimated_margin_pct", 0),
            "traffic_light": p.get("traffic_light", "RED"),
            "priority_tier": p.get("priority", {}).get("tier", "") if isinstance(p.get("priority"), dict) else p.get("priority_tier", ""),
            "seller_info": json.dumps(p.get("seller_info", {})),
            "supplier_price": p.get("supplier_price", 0),
            "full_data": json.dumps(p, default=str),
        } for p in products]

        conn = self._conn()
        try:
            with conn.cursor() as cur:
                psycopg2.extras.execute_batch(cur, query, params_list, page_size=500)
                conn.commit()
        except Exception:
            conn.rollback(); raise
        finally:
            conn.close()

    def add_supplier(self, supplier: Dict) -> Optional[int]:
        row = self._exec("""
            INSERT INTO suppliers (name, location, country, website, contact_person,
                contact_email, contact_phone, company_name, business_type, moq,
                lead_time_days, payment_terms, shipping_methods, certifications, rating, notes)
            VALUES (%(name)s, %(location)s, %(country)s, %(website)s, %(contact_person)s,
                %(contact_email)s, %(contact_phone)s, %(company_name)s, %(business_type)s, %(moq)s,
                %(lead_time_days)s, %(payment_terms)s, %(shipping_methods)s, %(certifications)s,
                %(rating)s, %(notes)s) RETURNING id
        """, {
            "name": supplier.get("name", ""), "location": supplier.get("location", ""),
            "country": supplier.get("country", ""), "website": supplier.get("website", ""),
            "contact_person": supplier.get("contact_person", ""),
            "contact_email": supplier.get("contact_email", ""),
            "contact_phone": supplier.get("contact_phone", ""),
            "company_name": supplier.get("company_name", ""),
            "business_type": supplier.get("business_type", ""),
            "moq": supplier.get("moq", 1), "lead_time_days": supplier.get("lead_time_days", 7),
            "payment_terms": supplier.get("payment_terms", "T/T"),
            "shipping_methods": supplier.get("shipping_methods", ""),
            "certifications": supplier.get("certifications", ""),
            "rating": supplier.get("rating", 0.0), "notes": supplier.get("notes", ""),
        }, "one")
        return row["id"] if row else None

    def get_all_suppliers(self) -> List[Dict]:
        return self._exec("SELECT * FROM suppliers ORDER BY name", fetch="all")

    def delete_supplier(self, supplier_id: int):
        self._exec("DELETE FROM suppliers WHERE id = %s", (supplier_id,))

    def record_price(self, asin, product_name, source, price, old_price=0):
        self._exec(
            "INSERT INTO price_history (asin, product_name, source, price, old_price) VALUES (%s,%s,%s,%s,%s)",
            (asin, product_name, source, price, old_price)
        )

    def get_price_history(self, asin, limit=100):
        return self._exec("SELECT * FROM price_history WHERE asin=%s ORDER BY recorded_at DESC LIMIT %s", (asin, limit), "all")

    def save_inventory(self, asin, product_name, data):
        self._exec(
            """INSERT INTO inventory (asin, product_name, sku, current_stock, reorder_point,
               reorder_quantity, unit_cost, notes) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (asin) DO UPDATE SET
               product_name=EXCLUDED.product_name, current_stock=EXCLUDED.current_stock,
               reorder_point=EXCLUDED.reorder_point, unit_cost=EXCLUDED.unit_cost, notes=EXCLUDED.notes,
               updated_at=CURRENT_TIMESTAMP""",
            (asin, product_name, data.get("sku", ""), data.get("current_stock", 0),
             data.get("reorder_point", 10), data.get("reorder_quantity", 100),
             data.get("unit_cost", 0), data.get("notes", ""))
        )

    def get_inventory(self, asin=None):
        if asin: return self._exec("SELECT * FROM inventory WHERE asin=%s", (asin,), "all")
        return self._exec("SELECT * FROM inventory ORDER BY product_name", fetch="all")

    def add_comment(self, asin, author, comment, comment_type="note", user_id=None):
        self._exec(
            "INSERT INTO product_comments (asin, author, comment, comment_type, user_id) VALUES (%s,%s,%s,%s,%s)",
            (asin, author, comment, comment_type, user_id)
        )

    def get_comments(self, asin):
        return self._exec("SELECT * FROM product_comments WHERE asin=%s ORDER BY created_at DESC", (asin,), "all")

    def add_task(self, asin, product_name, task, assignee="Unassigned", priority="medium", user_id=None):
        row = self._exec(
            "INSERT INTO product_tasks (asin, product_name, task, assignee, priority, user_id) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
            (asin, product_name, task, assignee, priority, user_id), "one"
        )
        return row["id"] if row else None

    def get_tasks(self, asin=None):
        if asin: return self._exec("SELECT * FROM product_tasks WHERE asin=%s ORDER BY created_at DESC", (asin,), "all")
        return self._exec("SELECT * FROM product_tasks ORDER BY created_at DESC", fetch="all")

    def toggle_task(self, task_id):
        row = self._exec("UPDATE product_tasks SET status = CASE WHEN status='done' THEN 'todo' ELSE 'done' END WHERE id=%s RETURNING status", (task_id,), "one")
        return row["status"] == "done" if row else False

    def get_stats(self):
        return {
            "products": self._exec("SELECT COUNT(*) FROM products", fetch="scalar") or 0,
            "suppliers": self._exec("SELECT COUNT(*) FROM suppliers", fetch="scalar") or 0,
            "users": self._exec("SELECT COUNT(*) FROM users", fetch="scalar") or 0,
            "listings": self._exec("SELECT COUNT(*) FROM listing_versions", fetch="scalar") or 0,
            "db_size": self._exec("SELECT pg_size_pretty(pg_database_size(current_database()))", fetch="scalar") or "N/A",
        }
