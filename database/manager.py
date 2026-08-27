"""Database manager for suppliers and product pricing."""

import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

if getattr(sys, 'frozen', False):
    _DB_BASE = os.path.dirname(os.path.dirname(sys.executable))
else:
    _DB_BASE = str(Path(__file__).parent.parent)

try:
    from utils.paths import DB_PATH as _DEFAULT_DB_PATH
except ImportError:
    _DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "marketlens.db")


class DatabaseManager:
    """Manages SQLite database for suppliers, products, and pricing."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = os.environ.get("MLENS_DB_PATH", _DEFAULT_DB_PATH)
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=-8000")
            conn.execute("PRAGMA temp_store=MEMORY")
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS suppliers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS supplier_products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    supplier_id INTEGER NOT NULL,
                    product_name TEXT NOT NULL,
                    asin TEXT DEFAULT '',
                    sku TEXT DEFAULT '',
                    unit_cost REAL DEFAULT 0.0,
                    shipping_cost REAL DEFAULT 0.0,
                    min_order INTEGER DEFAULT 1,
                    bulk_prices TEXT DEFAULT '{}',
                    notes TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS product_pricing (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                    margin_percent REAL DEFAULT 0.0,
                    roi_percent REAL DEFAULT 0.0,
                    break_even_units INTEGER DEFAULT 0,
                    target_margin REAL DEFAULT 30.0,
                    notes TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS product_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asin TEXT UNIQUE NOT NULL,
                    product_data TEXT DEFAULT '{}',
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.commit()

            try:
                cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_product_pricing_asin_unique ON product_pricing(asin)")
            except sqlite3.OperationalError:
                pass

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_suppliers_name ON suppliers(name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_suppliers_rating ON suppliers(rating)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_supplier_products_supplier ON supplier_products(supplier_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_supplier_products_asin ON supplier_products(asin)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_product_pricing_asin ON product_pricing(asin)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_product_cache_asin ON product_cache(asin)")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asin TEXT UNIQUE NOT NULL,
                    name TEXT DEFAULT '',
                    category TEXT DEFAULT '',
                    amazon_price REAL DEFAULT 0,
                    rating REAL DEFAULT 0,
                    review_count INTEGER DEFAULT 0,
                    ai_score REAL DEFAULT 0,
                    estimated_margin_pct REAL DEFAULT 0,
                    traffic_light TEXT DEFAULT 'RED',
                    priority_tier TEXT DEFAULT '',
                    seller_info TEXT DEFAULT '{}',
                    supplier_price REAL DEFAULT 0,
                    full_data TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_asin ON products(asin)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_ai_score ON products(ai_score DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asin TEXT NOT NULL,
                    product_name TEXT DEFAULT '',
                    source TEXT DEFAULT 'amazon',
                    price REAL DEFAULT 0,
                    old_price REAL DEFAULT 0,
                    currency TEXT DEFAULT 'GBP',
                    in_stock INTEGER DEFAULT 1,
                    rating REAL DEFAULT 0,
                    review_count INTEGER DEFAULT 0,
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_price_history_asin ON price_history(asin)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_price_history_date ON price_history(recorded_at DESC)")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS review_sentiment (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asin TEXT NOT NULL,
                    product_name TEXT DEFAULT '',
                    total_reviews INTEGER DEFAULT 0,
                    positive_pct REAL DEFAULT 0,
                    negative_pct REAL DEFAULT 0,
                    neutral_pct REAL DEFAULT 0,
                    top_complaints TEXT DEFAULT '[]',
                    top_praises TEXT DEFAULT '[]',
                    recurring_issues TEXT DEFAULT '[]',
                    improvement_ideas TEXT DEFAULT '[]',
                    summary TEXT DEFAULT '',
                    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_review_sentiment_asin ON review_sentiment(asin)")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS seasonality_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asin TEXT NOT NULL,
                    product_name TEXT DEFAULT '',
                    month INTEGER DEFAULT 0,
                    demand_level TEXT DEFAULT 'medium',
                    search_volume REAL DEFAULT 0,
                    sales_estimate REAL DEFAULT 0,
                    peak_month INTEGER DEFAULT 0,
                    low_month INTEGER DEFAULT 0,
                    season_pattern TEXT DEFAULT '',
                    notes TEXT DEFAULT '',
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_seasonality_asin ON seasonality_data(asin)")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS competitor_tracking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asin TEXT NOT NULL,
                    product_name TEXT DEFAULT '',
                    competitor_asin TEXT DEFAULT '',
                    competitor_name TEXT DEFAULT '',
                    competitor_price REAL DEFAULT 0,
                    competitor_rating REAL DEFAULT 0,
                    competitor_reviews INTEGER DEFAULT 0,
                    competitor_rank INTEGER DEFAULT 0,
                    competitor_stock TEXT DEFAULT 'in_stock',
                    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_competitor_asin ON competitor_tracking(asin)")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS inventory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asin TEXT NOT NULL,
                    product_name TEXT DEFAULT '',
                    sku TEXT DEFAULT '',
                    current_stock INTEGER DEFAULT 0,
                    reorder_point INTEGER DEFAULT 0,
                    reorder_quantity INTEGER DEFAULT 0,
                    unit_cost REAL DEFAULT 0,
                    fba_shipment_id TEXT DEFAULT '',
                    fba_status TEXT DEFAULT 'pending',
                    warehouse TEXT DEFAULT 'FBA',
                    last_restocked TEXT DEFAULT '',
                    days_of_stock INTEGER DEFAULT 0,
                    monthly_velocity INTEGER DEFAULT 0,
                    notes TEXT DEFAULT '',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_inventory_asin ON inventory(asin)")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS product_comments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asin TEXT NOT NULL,
                    author TEXT DEFAULT 'User',
                    comment TEXT DEFAULT '',
                    comment_type TEXT DEFAULT 'note',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_comments_asin ON product_comments(asin)")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS product_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asin TEXT NOT NULL,
                    product_name TEXT DEFAULT '',
                    task TEXT DEFAULT '',
                    assignee TEXT DEFAULT 'Unassigned',
                    priority TEXT DEFAULT 'medium',
                    status TEXT DEFAULT 'todo',
                    due_date TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_asin ON product_tasks(asin)")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT DEFAULT '',
                    password_hash TEXT NOT NULL,
                    display_name TEXT DEFAULT '',
                    is_active INTEGER DEFAULT 1,
                    is_admin INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    tier TEXT NOT NULL DEFAULT 'free',
                    starts_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_tier ON subscriptions(tier)")

            conn.commit()

    # ── User Methods ──────────────────────────────────────────

    def create_user(self, username: str, password_hash: str, email: str = "", display_name: str = "") -> Optional[int]:
        """Create a new user. Returns user_id or None if username exists."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO users (username, email, password_hash, display_name) VALUES (?, ?, ?, ?)",
                    (username, email, password_hash, display_name or username)
                )
                user_id = cursor.lastrowid
                conn.commit()
                return user_id
            except sqlite3.IntegrityError:
                return None

    def get_user_by_username(self, username: str) -> Optional[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    # ── Subscription Methods ──────────────────────────────────

    def create_subscription(self, user_id: int, tier: str = "free", days: int = 0) -> int:
        """Create a subscription. For free tier, days=0 means no expiry. Returns subscription_id."""
        from datetime import datetime, timedelta
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            expires_at = None
            if days > 0:
                expires_at = (datetime.utcnow() + timedelta(days=days)).isoformat()
            cursor.execute(
                "INSERT INTO subscriptions (user_id, tier, expires_at) VALUES (?, ?, ?)",
                (user_id, tier, expires_at)
            )
            sub_id = cursor.lastrowid
            conn.commit()
            return sub_id

    def get_active_subscription(self, user_id: int) -> Optional[Dict]:
        """Get the active subscription for a user. Checks expiry."""
        from datetime import datetime
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM subscriptions WHERE user_id = ? AND is_active = 1 ORDER BY id DESC LIMIT 1",
                (user_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            sub = dict(row)
            if sub["expires_at"]:
                expires = datetime.fromisoformat(sub["expires_at"])
                if datetime.utcnow() > expires:
                    sub["is_active"] = 0
                    sub["expired"] = True
                else:
                    sub["expired"] = False
                    sub["days_left"] = (expires - datetime.utcnow()).days
            else:
                sub["expired"] = False
                sub["days_left"] = None
            return sub

    def upgrade_subscription(self, user_id: int, tier: str, days: int) -> bool:
        """Deactivate old subscription and create a new one."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE subscriptions SET is_active = 0 WHERE user_id = ? AND is_active = 1",
                (user_id,)
            )
            conn.commit()
        self.create_subscription(user_id, tier, days)
        return True

    def get_all_users(self) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, email, display_name, is_active, is_admin, created_at FROM users ORDER BY id")
            return [dict(r) for r in cursor.fetchall()]

    def batch_upsert_products(self, products: List[Dict[str, Any]]):
        """Batch insert or update products."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()
            for p in products:
                cursor.execute("""
                    INSERT INTO products (asin, name, category, amazon_price, rating, review_count,
                        ai_score, estimated_margin_pct, traffic_light, priority_tier, seller_info,
                        supplier_price, full_data, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(asin) DO UPDATE SET
                        name=excluded.name, category=excluded.category,
                        amazon_price=excluded.amazon_price, rating=excluded.rating,
                        review_count=excluded.review_count, ai_score=excluded.ai_score,
                        estimated_margin_pct=excluded.estimated_margin_pct,
                        traffic_light=excluded.traffic_light, priority_tier=excluded.priority_tier,
                        seller_info=excluded.seller_info, supplier_price=excluded.supplier_price,
                        full_data=excluded.full_data, updated_at=CURRENT_TIMESTAMP
                """, (
                    p.get("asin", ""), p.get("name", p.get("title", "")),
                    p.get("category", ""), p.get("amazon_price", 0),
                    p.get("rating", 0), p.get("review_count", 0),
                    p.get("ai_score", 0), p.get("estimated_margin_pct", 0),
                    p.get("traffic_light", "RED"), p.get("priority", {}).get("tier", ""),
                    json.dumps(p.get("seller_info", {})), p.get("supplier_price", 0),
                    json.dumps(p, default=str)
                ))
            conn.commit()

    def get_products_count(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]

    def get_all_products_from_db(self) -> List[Dict[str, Any]]:
        """Load all products from database, returning full_data JSON."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT full_data FROM products ORDER BY ai_score DESC").fetchall()
            products = []
            for row in rows:
                try:
                    data = json.loads(row["full_data"])
                    products.append(data)
                except Exception:
                    continue
            return products

    def add_supplier(self, supplier: Dict[str, Any]) -> Optional[int]:
        """Add a new supplier. Returns supplier ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO suppliers (name, location, country, website, contact_person,
                    contact_email, contact_phone, contact_whatsapp, contact_skype, contact_wechat,
                    company_name, business_type, year_established, employee_count,
                    moq, lead_time_days, payment_terms, shipping_methods, certifications,
                    rating, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                supplier.get("name", ""),
                supplier.get("location", ""),
                supplier.get("country", ""),
                supplier.get("website", ""),
                supplier.get("contact_person", ""),
                supplier.get("contact_email", ""),
                supplier.get("contact_phone", ""),
                supplier.get("contact_whatsapp", ""),
                supplier.get("contact_skype", ""),
                supplier.get("contact_wechat", ""),
                supplier.get("company_name", ""),
                supplier.get("business_type", ""),
                supplier.get("year_established", 0),
                supplier.get("employee_count", ""),
                supplier.get("moq", 1),
                supplier.get("lead_time_days", 7),
                supplier.get("payment_terms", "T/T"),
                supplier.get("shipping_methods", ""),
                supplier.get("certifications", ""),
                supplier.get("rating", 0.0),
                supplier.get("notes", ""),
            ))
            conn.commit()
            return cursor.lastrowid

    def update_supplier(self, supplier_id: int, supplier: Dict[str, Any]):
        """Update an existing supplier."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE suppliers SET
                    name = ?, location = ?, country = ?, website = ?, contact_person = ?,
                    contact_email = ?, contact_phone = ?, contact_whatsapp = ?,
                    contact_skype = ?, contact_wechat = ?, company_name = ?,
                    business_type = ?, year_established = ?, employee_count = ?,
                    moq = ?, lead_time_days = ?, payment_terms = ?, shipping_methods = ?,
                    certifications = ?, rating = ?, notes = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                supplier.get("name", ""),
                supplier.get("location", ""),
                supplier.get("country", ""),
                supplier.get("website", ""),
                supplier.get("contact_person", ""),
                supplier.get("contact_email", ""),
                supplier.get("contact_phone", ""),
                supplier.get("contact_whatsapp", ""),
                supplier.get("contact_skype", ""),
                supplier.get("contact_wechat", ""),
                supplier.get("company_name", ""),
                supplier.get("business_type", ""),
                supplier.get("year_established", 0),
                supplier.get("employee_count", ""),
                supplier.get("moq", 1),
                supplier.get("lead_time_days", 7),
                supplier.get("payment_terms", "T/T"),
                supplier.get("shipping_methods", ""),
                supplier.get("certifications", ""),
                supplier.get("rating", 0.0),
                supplier.get("notes", ""),
                supplier_id,
            ))
            conn.commit()

    def delete_supplier(self, supplier_id: int):
        """Delete a supplier and their products."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM supplier_products WHERE supplier_id = ?", (supplier_id,))
            cursor.execute("DELETE FROM suppliers WHERE id = ?", (supplier_id,))
            conn.commit()

    def get_supplier(self, supplier_id: int) -> Optional[Dict[str, Any]]:
        """Get a single supplier by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM suppliers WHERE id = ?", (supplier_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_suppliers(self) -> List[Dict[str, Any]]:
        """Get all suppliers."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM suppliers ORDER BY name")
            return [dict(row) for row in cursor.fetchall()]

    def add_supplier_product(self, product: Dict[str, Any]) -> Optional[int]:
        """Add a product from a supplier. Returns product ID."""
        bulk_prices = product.get("bulk_prices", {})
        if isinstance(bulk_prices, dict):
            bulk_prices = json.dumps(bulk_prices)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO supplier_products (supplier_id, product_name, asin, sku,
                                              unit_cost, shipping_cost, min_order, bulk_prices, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                product.get("supplier_id", 0),
                product.get("product_name", ""),
                product.get("asin", ""),
                product.get("sku", ""),
                product.get("unit_cost", 0.0),
                product.get("shipping_cost", 0.0),
                product.get("min_order", 1),
                bulk_prices,
                product.get("notes", ""),
            ))
            conn.commit()
            return cursor.lastrowid

    def get_supplier_products(self, supplier_id: Optional[int] = None, asin: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get products, optionally filtered by supplier or ASIN."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if supplier_id:
                cursor.execute("""
                    SELECT sp.*, s.name as supplier_name
                    FROM supplier_products sp
                    JOIN suppliers s ON sp.supplier_id = s.id
                    WHERE sp.supplier_id = ?
                    ORDER BY sp.unit_cost
                """, (supplier_id,))
            elif asin:
                cursor.execute("""
                    SELECT sp.*, s.name as supplier_name
                    FROM supplier_products sp
                    JOIN suppliers s ON sp.supplier_id = s.id
                    WHERE sp.asin = ?
                    ORDER BY sp.unit_cost
                """, (asin,))
            else:
                cursor.execute("""
                    SELECT sp.*, s.name as supplier_name
                    FROM supplier_products sp
                    JOIN suppliers s ON sp.supplier_id = s.id
                    ORDER BY sp.product_name, sp.unit_cost
                """)

            rows = [dict(row) for row in cursor.fetchall()]
            for row in rows:
                bulk = row.get("bulk_prices", "{}")
                if isinstance(bulk, str):
                    try:
                        row["bulk_prices"] = json.loads(bulk)
                    except json.JSONDecodeError:
                        row["bulk_prices"] = {}
            return rows

    def save_pricing(self, pricing: Dict[str, Any]) -> Optional[int]:
        """Save or update product pricing atomically. Returns pricing ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO product_pricing (asin, product_name, supplier_id, supplier_cost,
                    shipping_cost, customs_duty, packaging_cost, fba_fee, referral_fee,
                    total_landed_cost, current_market_price, suggested_price, min_price,
                    max_price, profit_per_unit, margin_percent, roi_percent,
                    break_even_units, target_margin, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(asin) DO UPDATE SET
                    product_name=excluded.product_name, supplier_id=excluded.supplier_id,
                    supplier_cost=excluded.supplier_cost, shipping_cost=excluded.shipping_cost,
                    customs_duty=excluded.customs_duty, packaging_cost=excluded.packaging_cost,
                    fba_fee=excluded.fba_fee, referral_fee=excluded.referral_fee,
                    total_landed_cost=excluded.total_landed_cost,
                    current_market_price=excluded.current_market_price,
                    suggested_price=excluded.suggested_price, min_price=excluded.min_price,
                    max_price=excluded.max_price, profit_per_unit=excluded.profit_per_unit,
                    margin_percent=excluded.margin_percent, roi_percent=excluded.roi_percent,
                    break_even_units=excluded.break_even_units, target_margin=excluded.target_margin,
                    notes=excluded.notes, updated_at=CURRENT_TIMESTAMP
            """, (
                pricing.get("asin", ""),
                pricing.get("product_name", ""),
                pricing.get("supplier_id"),
                pricing.get("supplier_cost", 0.0),
                pricing.get("shipping_cost", 0.0),
                pricing.get("customs_duty", 0.0),
                pricing.get("packaging_cost", 0.0),
                pricing.get("fba_fee", 0.0),
                pricing.get("referral_fee", 0.0),
                pricing.get("total_landed_cost", 0.0),
                pricing.get("current_market_price", 0.0),
                pricing.get("suggested_price", 0.0),
                pricing.get("min_price", 0.0),
                pricing.get("max_price", 0.0),
                pricing.get("profit_per_unit", 0.0),
                pricing.get("margin_percent", 0.0),
                pricing.get("roi_percent", 0.0),
                pricing.get("break_even_units", 0),
                pricing.get("target_margin", 30.0),
                pricing.get("notes", ""),
            ))
            conn.commit()
            return cursor.lastrowid

    def get_pricing(self, asin: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get pricing for a product."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM product_pricing WHERE asin = ?", (asin,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_pricing(self) -> List[Dict[str, Any]]:
        """Get all pricing records."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT pp.*, s.name as supplier_name
                FROM product_pricing pp
                LEFT JOIN suppliers s ON pp.supplier_id = s.id
                ORDER BY pp.margin_percent DESC
            """)
            return [dict(row) for row in cursor.fetchall()]

    def cache_product(self, asin: str, data: Dict[str, Any]):
        """Cache product data from API."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO product_cache (asin, product_data, last_updated)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (asin, json.dumps(data)))
            conn.commit()

    def get_cached_product(self, asin: str, max_age_hours: int = 24) -> Optional[Dict[str, Any]]:
        """Get cached product data if fresh enough."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM product_cache
                WHERE asin = ?
                AND datetime(last_updated, '+' || ? || ' hours') > datetime('now')
            """, (asin, max_age_hours))
            row = cursor.fetchone()
            if row:
                data = dict(row)
                data["product_data"] = json.loads(data.get("product_data", "{}"))
                return data
            return None

    def import_suppliers_from_csv(self, csv_path: str) -> int:
        """Import suppliers from CSV file. Returns count imported."""
        import csv
        count = 0
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                supplier = {
                    "name": row.get("name", row.get("supplier_name", "")),
                    "location": row.get("location", row.get("country", "")),
                    "website": row.get("website", row.get("url", "")),
                    "contact_email": row.get("email", row.get("contact_email", "")),
                    "contact_phone": row.get("phone", row.get("contact_phone", "")),
                    "moq": int(row.get("moq", 1)),
                    "lead_time_days": int(row.get("lead_time", row.get("lead_time_days", 7))),
                    "payment_terms": row.get("payment_terms", "T/T"),
                    "rating": float(row.get("rating", 0)),
                    "notes": row.get("notes", ""),
                }
                if supplier["name"]:
                    self.add_supplier(supplier)
                    count += 1
        return count

    def export_suppliers_to_csv(self, csv_path: str) -> int:
        """Export suppliers to CSV file. Returns count exported."""
        import csv
        suppliers = self.get_all_suppliers()
        if not suppliers:
            return 0

        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=suppliers[0].keys())
            writer.writeheader()
            writer.writerows(suppliers)
        return len(suppliers)

    def record_price(self, asin: str, product_name: str, source: str,
                     price: float, old_price: float = 0, in_stock: bool = True,
                     rating: float = 0, review_count: int = 0):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO price_history (asin, product_name, source, price, old_price, in_stock, rating, review_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (asin, product_name, source, price, old_price, int(in_stock), rating, review_count))
            conn.commit()

    def get_price_history(self, asin: str, limit: int = 100) -> list:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM price_history WHERE asin=? ORDER BY recorded_at DESC LIMIT ?",
                (asin, limit)
            ).fetchall()
            return [dict(r) for r in rows]

    def save_review_sentiment(self, asin: str, product_name: str, data: dict):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO review_sentiment (asin, product_name, total_reviews, positive_pct,
                    negative_pct, neutral_pct, top_complaints, top_praises, recurring_issues,
                    improvement_ideas, summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (asin, product_name, data.get("total_reviews", 0),
                  data.get("positive_pct", 0), data.get("negative_pct", 0), data.get("neutral_pct", 0),
                  json.dumps(data.get("top_complaints", [])), json.dumps(data.get("top_praises", [])),
                  json.dumps(data.get("recurring_issues", [])), json.dumps(data.get("improvement_ideas", [])),
                  data.get("summary", "")))
            conn.commit()

    def get_review_sentiment(self, asin: str) -> Optional[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM review_sentiment WHERE asin=? ORDER BY analyzed_at DESC LIMIT 1",
                (asin,)
            ).fetchone()
            if row:
                d = dict(row)
                for k in ("top_complaints", "top_praises", "recurring_issues", "improvement_ideas"):
                    d[k] = json.loads(d.get(k, "[]"))
                return d
            return None

    def save_seasonality(self, asin: str, product_name: str, data: dict):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO seasonality_data (asin, product_name, month, demand_level,
                    search_volume, sales_estimate, peak_month, low_month, season_pattern, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (asin, product_name, data.get("month", 0), data.get("demand_level", "medium"),
                  data.get("search_volume", 0), data.get("sales_estimate", 0),
                  data.get("peak_month", 0), data.get("low_month", 0),
                  data.get("season_pattern", ""), data.get("notes", "")))
            conn.commit()

    def get_seasonality(self, asin: str) -> list:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM seasonality_data WHERE asin=? ORDER BY recorded_at DESC LIMIT 12",
                (asin,)
            ).fetchall()
            return [dict(r) for r in rows]

    def record_competitor(self, asin: str, product_name: str, comp: dict):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO competitor_tracking (asin, product_name, competitor_asin,
                    competitor_name, competitor_price, competitor_rating, competitor_reviews,
                    competitor_rank, competitor_stock)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (asin, product_name, comp.get("competitor_asin", ""),
                  comp.get("competitor_name", ""), comp.get("competitor_price", 0),
                  comp.get("competitor_rating", 0), comp.get("competitor_reviews", 0),
                  comp.get("competitor_rank", 0), comp.get("competitor_stock", "in_stock")))
            conn.commit()

    def get_competitors(self, asin: str, limit: int = 50) -> list:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM competitor_tracking WHERE asin=? ORDER BY recorded_at DESC LIMIT ?",
                (asin, limit)
            ).fetchall()
            return [dict(r) for r in rows]

    def save_inventory(self, asin: str, product_name: str, data: dict):
        with sqlite3.connect(self.db_path) as conn:
            existing = conn.execute("SELECT id FROM inventory WHERE asin=?", (asin,)).fetchone()
            if existing:
                conn.execute("""
                    UPDATE inventory SET product_name=?, sku=?, current_stock=?, reorder_point=?,
                        reorder_quantity=?, unit_cost=?, fba_shipment_id=?, fba_status=?,
                        warehouse=?, last_restocked=?, days_of_stock=?, monthly_velocity=?, notes=?,
                        updated_at=CURRENT_TIMESTAMP
                    WHERE asin=?
                """, (product_name, data.get("sku", ""), data.get("current_stock", 0),
                      data.get("reorder_point", 0), data.get("reorder_quantity", 0),
                      data.get("unit_cost", 0), data.get("fba_shipment_id", ""),
                      data.get("fba_status", "pending"), data.get("warehouse", "FBA"),
                      data.get("last_restocked", ""), data.get("days_of_stock", 0),
                      data.get("monthly_velocity", 0), data.get("notes", ""), asin))
            else:
                conn.execute("""
                    INSERT INTO inventory (asin, product_name, sku, current_stock, reorder_point,
                        reorder_quantity, unit_cost, fba_shipment_id, fba_status, warehouse,
                        last_restocked, days_of_stock, monthly_velocity, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (asin, product_name, data.get("sku", ""), data.get("current_stock", 0),
                      data.get("reorder_point", 0), data.get("reorder_quantity", 0),
                      data.get("unit_cost", 0), data.get("fba_shipment_id", ""),
                      data.get("fba_status", "pending"), data.get("warehouse", "FBA"),
                      data.get("last_restocked", ""), data.get("days_of_stock", 0),
                      data.get("monthly_velocity", 0), data.get("notes", "")))
            conn.commit()

    def get_inventory(self, asin: Optional[str] = None) -> list:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if asin:
                rows = conn.execute("SELECT * FROM inventory WHERE asin=?", (asin,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM inventory ORDER BY updated_at DESC").fetchall()
            return [dict(r) for r in rows]

    def add_comment(self, asin: str, author: str, comment: str, comment_type: str = "note"):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO product_comments (asin, author, comment, comment_type)
                VALUES (?, ?, ?, ?)
            """, (asin, author, comment, comment_type))
            conn.commit()

    def get_comments(self, asin: str) -> list:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM product_comments WHERE asin=? ORDER BY created_at DESC",
                (asin,)
            ).fetchall()
            return [dict(r) for r in rows]

    def add_task(self, asin: str, product_name: str, task: str, assignee: str = "Unassigned",
                 priority: str = "medium", due_date: str = ""):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO product_tasks (asin, product_name, task, assignee, priority, status, due_date)
                VALUES (?, ?, ?, ?, ?, 'todo', ?)
            """, (asin, product_name, task, assignee, priority, due_date))
            conn.commit()

    def get_tasks(self, asin: Optional[str] = None) -> list:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if asin:
                rows = conn.execute("SELECT * FROM product_tasks WHERE asin=? ORDER BY created_at DESC", (asin,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM product_tasks ORDER BY created_at DESC").fetchall()
            return [dict(r) for r in rows]

    def update_task_status(self, task_id: int, status: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE product_tasks SET status=? WHERE id=?", (status, task_id))
            conn.commit()

    def delete_task(self, task_id: int):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM product_tasks WHERE id=?", (task_id,))
            conn.commit()
