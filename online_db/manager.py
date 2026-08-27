"""PostgreSQL Database Manager for online/cloud deployment.

Mirrors the interface of database.manager.DatabaseManager but uses PostgreSQL
with connection pooling for concurrent access in a multi-user environment.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
import psycopg2.extras
from psycopg2 import pool

from .config import DatabaseConfig

logger = logging.getLogger(__name__)


class OnlineDatabaseManager:
    """PostgreSQL database manager with connection pooling."""

    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.config = config or DatabaseConfig()
        self.config.validate()
        self._pool: Optional[pool.ThreadedConnectionPool] = None
        self._init_pool()
        self._init_schema()

    def _init_pool(self):
        """Initialize connection pool."""
        try:
            self._pool = pool.ThreadedConnectionPool(
                self.config.min_connections,
                self.config.max_connections,
                host=self.config.host,
                port=self.config.port,
                dbname=self.config.database,
                user=self.config.user,
                password=self.config.password,
                connect_timeout=self.config.connection_timeout,
                options=f"-c search_path=public,marketlens",
            )
            logger.info("PostgreSQL connection pool initialized: %s:%d/%s",
                        self.config.host, self.config.port, self.config.database)
        except Exception as e:
            logger.error("Failed to initialize connection pool: %s", e)
            raise

    def _get_conn(self):
        """Get a connection from the pool."""
        return self._pool.getconn()

    def _put_conn(self, conn):
        """Return a connection to the pool."""
        self._pool.putconn(conn)

    def _execute(self, query: str, params: tuple = (), fetch: str = "none") -> Any:
        """Execute a query with automatic connection management."""
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, params)
                if fetch == "one":
                    return dict(cur.fetchone()) if cur.rowcount > 0 else None
                elif fetch == "all":
                    return [dict(row) for row in cur.fetchall()]
                elif fetch == "scalar":
                    return cur.fetchone()[0] if cur.rowcount > 0 else None
                else:
                    conn.commit()
                    return cur.rowcount
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

    def _execute_many(self, query: str, params_list: List[tuple]) -> int:
        """Execute a query with multiple parameter sets."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                psycopg2.extras.execute_batch(cur, query, params_list, page_size=500)
                conn.commit()
                return cur.rowcount
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

    def close(self):
        """Close all connections in the pool."""
        if self._pool:
            self._pool.closeall()
            logger.info("PostgreSQL connection pool closed")

    # ════════════════════════════════════════════════════════════
    # SCHEMA INITIALIZATION
    # ════════════════════════════════════════════════════════════

    def _init_schema(self):
        """Create all tables if they don't exist."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("CREATE SCHEMA IF NOT EXISTS marketlens")
                cur.execute("SET search_path TO public, marketlens")

                cur.execute("""
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
                    )
                """)

                cur.execute("""
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
                    )
                """)

                cur.execute("""
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
                    )
                """)

                cur.execute("""
                    CREATE TABLE IF NOT EXISTS product_cache (
                        id SERIAL PRIMARY KEY,
                        asin TEXT NOT NULL UNIQUE,
                        product_data JSONB NOT NULL DEFAULT '{}',
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                cur.execute("""
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
                    )
                """)

                cur.execute("""
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
                    )
                """)

                cur.execute("""
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
                    )
                """)

                cur.execute("""
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
                    )
                """)

                cur.execute("""
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
                    )
                """)

                cur.execute("""
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
                    )
                """)

                cur.execute("""
                    CREATE TABLE IF NOT EXISTS product_comments (
                        id SERIAL PRIMARY KEY,
                        asin TEXT NOT NULL,
                        author TEXT DEFAULT '',
                        comment TEXT DEFAULT '',
                        comment_type TEXT DEFAULT 'note',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                cur.execute("""
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
                    )
                """)

                cur.execute("""
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
                    )
                """)

                cur.execute("""
                    CREATE TABLE IF NOT EXISTS subscriptions (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        tier TEXT NOT NULL DEFAULT 'free',
                        start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expiry_date TIMESTAMP,
                        is_active INTEGER DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                cur.execute("""
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
                    )
                """)

                # Indexes
                for idx_query in [
                    "CREATE INDEX IF NOT EXISTS idx_suppliers_name ON suppliers(name)",
                    "CREATE INDEX IF NOT EXISTS idx_suppliers_rating ON suppliers(rating)",
                    "CREATE INDEX IF NOT EXISTS idx_supplier_products_supplier ON supplier_products(supplier_id)",
                    "CREATE INDEX IF NOT EXISTS idx_supplier_products_asin ON supplier_products(asin)",
                    "CREATE INDEX IF NOT EXISTS idx_product_pricing_asin ON product_pricing(asin)",
                    "CREATE INDEX IF NOT EXISTS idx_product_cache_asin ON product_cache(asin)",
                    "CREATE INDEX IF NOT EXISTS idx_products_asin ON products(asin)",
                    "CREATE INDEX IF NOT EXISTS idx_products_ai_score ON products(ai_score DESC)",
                    "CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)",
                    "CREATE INDEX IF NOT EXISTS idx_price_history_asin ON price_history(asin)",
                    "CREATE INDEX IF NOT EXISTS idx_price_history_recorded ON price_history(recorded_at DESC)",
                    "CREATE INDEX IF NOT EXISTS idx_review_sentiment_asin ON review_sentiment(asin)",
                    "CREATE INDEX IF NOT EXISTS idx_seasonality_asin ON seasonality_data(asin)",
                    "CREATE INDEX IF NOT EXISTS idx_competitor_asin ON competitor_tracking(asin)",
                    "CREATE INDEX IF NOT EXISTS idx_inventory_asin ON inventory(asin)",
                    "CREATE INDEX IF NOT EXISTS idx_comments_asin ON product_comments(asin)",
                    "CREATE INDEX IF NOT EXISTS idx_tasks_asin ON product_tasks(asin)",
                    "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
                    "CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions(user_id)",
                    "CREATE INDEX IF NOT EXISTS idx_subscriptions_tier ON subscriptions(tier)",
                    "CREATE INDEX IF NOT EXISTS idx_listing_versions_asin ON listing_versions(asin)",
                ]:
                    cur.execute(idx_query)

                conn.commit()
                logger.info("PostgreSQL schema initialized successfully")
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_conn(conn)

    # ════════════════════════════════════════════════════════════
    # USERS & AUTH
    # ════════════════════════════════════════════════════════════

    def create_user(self, username: str, password_hash: str, email: str = "") -> Optional[int]:
        row = self._execute(
            "INSERT INTO users (username, password_hash, email) VALUES (%s, %s, %s) RETURNING id",
            (username, password_hash, email), fetch="one"
        )
        return row["id"] if row else None

    def get_user(self, username: str) -> Optional[Dict]:
        return self._execute(
            "SELECT id, username, email, password_hash, display_name, is_active, is_admin FROM users WHERE username = %s",
            (username,), fetch="one"
        )

    def create_subscription(self, user_id: int, tier: str = "free", days: int = 30):
        expiry = datetime.now() + timedelta(days=days) if days > 0 else None
        self._execute(
            "INSERT INTO subscriptions (user_id, tier, expiry_date) VALUES (%s, %s, %s)",
            (user_id, tier, expiry)
        )

    def upgrade_subscription(self, user_id: int, tier: str, days: int = 30):
        self._execute(
            "UPDATE subscriptions SET is_active = 0 WHERE user_id = %s AND is_active = 1",
            (user_id,)
        )
        self.create_subscription(user_id, tier, days)

    def get_subscription(self, user_id: int) -> Optional[Dict]:
        return self._execute(
            "SELECT tier, expiry_date, is_active FROM subscriptions WHERE user_id = %s AND is_active = 1",
            (user_id,), fetch="one"
        )

    def get_all_users(self) -> List[Dict]:
        return self._execute(
            "SELECT id, username, email, display_name, is_active, is_admin, created_at FROM users ORDER BY id",
            fetch="all"
        )

    # ════════════════════════════════════════════════════════════
    # PRODUCTS
    # ════════════════════════════════════════════════════════════

    def batch_upsert_products(self, products: List[Dict[str, Any]]):
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
        params_list = []
        for p in products:
            params_list.append({
                "asin": p.get("asin", ""),
                "name": p.get("name", p.get("title", "")),
                "category": p.get("category", ""),
                "amazon_price": p.get("amazon_price", 0),
                "rating": p.get("rating", 0),
                "review_count": p.get("review_count", 0),
                "ai_score": p.get("ai_score", 0),
                "estimated_margin_pct": p.get("estimated_margin_pct", 0),
                "traffic_light": p.get("traffic_light", "RED"),
                "priority_tier": p.get("priority", {}).get("tier", ""),
                "seller_info": json.dumps(p.get("seller_info", {})),
                "supplier_price": p.get("supplier_price", 0),
                "full_data": json.dumps(p, default=str),
            })
        self._execute_many(query, params_list)

    def get_products_count(self) -> int:
        return self._execute("SELECT COUNT(*) FROM products", fetch="scalar") or 0

    def get_all_products_from_db(self) -> List[Dict[str, Any]]:
        rows = self._execute("SELECT full_data FROM products ORDER BY ai_score DESC", fetch="all")
        products = []
        for row in rows:
            try:
                products.append(json.loads(row["full_data"]))
            except Exception:
                continue
        return products

    # ════════════════════════════════════════════════════════════
    # SUPPLIERS
    # ════════════════════════════════════════════════════════════

    def add_supplier(self, supplier: Dict[str, Any]) -> Optional[int]:
        row = self._execute("""
            INSERT INTO suppliers (name, location, country, website, contact_person,
                contact_email, contact_phone, contact_whatsapp, contact_skype, contact_wechat,
                company_name, business_type, year_established, employee_count,
                moq, lead_time_days, payment_terms, shipping_methods, certifications,
                rating, notes)
            VALUES (%(name)s, %(location)s, %(country)s, %(website)s, %(contact_person)s,
                %(contact_email)s, %(contact_phone)s, %(contact_whatsapp)s, %(contact_skype)s,
                %(contact_wechat)s, %(company_name)s, %(business_type)s, %(year_established)s,
                %(employee_count)s, %(moq)s, %(lead_time_days)s, %(payment_terms)s,
                %(shipping_methods)s, %(certifications)s, %(rating)s, %(notes)s)
            RETURNING id
        """, {
            "name": supplier.get("name", ""),
            "location": supplier.get("location", ""),
            "country": supplier.get("country", ""),
            "website": supplier.get("website", ""),
            "contact_person": supplier.get("contact_person", ""),
            "contact_email": supplier.get("contact_email", ""),
            "contact_phone": supplier.get("contact_phone", ""),
            "contact_whatsapp": supplier.get("contact_whatsapp", ""),
            "contact_skype": supplier.get("contact_skype", ""),
            "contact_wechat": supplier.get("contact_wechat", ""),
            "company_name": supplier.get("company_name", ""),
            "business_type": supplier.get("business_type", ""),
            "year_established": supplier.get("year_established", 0),
            "employee_count": supplier.get("employee_count", ""),
            "moq": supplier.get("moq", 1),
            "lead_time_days": supplier.get("lead_time_days", 7),
            "payment_terms": supplier.get("payment_terms", "T/T"),
            "shipping_methods": supplier.get("shipping_methods", ""),
            "certifications": supplier.get("certifications", ""),
            "rating": supplier.get("rating", 0.0),
            "notes": supplier.get("notes", ""),
        }, fetch="one")
        return row["id"] if row else None

    def update_supplier(self, supplier_id: int, supplier: Dict[str, Any]):
        self._execute("""
            UPDATE suppliers SET name=%s, location=%s, country=%s, website=%s,
                contact_person=%s, contact_email=%s, contact_phone=%s,
                contact_whatsapp=%s, contact_skype=%s, contact_wechat=%s,
                company_name=%s, business_type=%s, year_established=%s,
                employee_count=%s, moq=%s, lead_time_days=%s, payment_terms=%s,
                shipping_methods=%s, certifications=%s, rating=%s, notes=%s,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=%s
        """, (
            supplier.get("name", ""), supplier.get("location", ""),
            supplier.get("country", ""), supplier.get("website", ""),
            supplier.get("contact_person", ""), supplier.get("contact_email", ""),
            supplier.get("contact_phone", ""), supplier.get("contact_whatsapp", ""),
            supplier.get("contact_skype", ""), supplier.get("contact_wechat", ""),
            supplier.get("company_name", ""), supplier.get("business_type", ""),
            supplier.get("year_established", 0), supplier.get("employee_count", ""),
            supplier.get("moq", 1), supplier.get("lead_time_days", 7),
            supplier.get("payment_terms", "T/T"), supplier.get("shipping_methods", ""),
            supplier.get("certifications", ""), supplier.get("rating", 0.0),
            supplier.get("notes", ""), supplier_id,
        ))

    def delete_supplier(self, supplier_id: int):
        self._execute("DELETE FROM suppliers WHERE id = %s", (supplier_id,))

    def get_supplier(self, supplier_id: int) -> Optional[Dict]:
        return self._execute(
            "SELECT * FROM suppliers WHERE id = %s", (supplier_id,), fetch="one"
        )

    def get_all_suppliers(self) -> List[Dict]:
        return self._execute("SELECT * FROM suppliers ORDER BY name", fetch="all")

    def add_supplier_product(self, product: Dict[str, Any]) -> Optional[int]:
        bulk = product.get("bulk_prices", {})
        if isinstance(bulk, str):
            bulk = json.loads(bulk)
        row = self._execute("""
            INSERT INTO supplier_products (supplier_id, product_name, asin, sku,
                unit_cost, shipping_cost, min_order, bulk_prices, notes)
            VALUES (%(supplier_id)s, %(product_name)s, %(asin)s, %(sku)s,
                %(unit_cost)s, %(shipping_cost)s, %(min_order)s, %(bulk_prices)s, %(notes)s)
            RETURNING id
        """, {
            "supplier_id": product.get("supplier_id", 0),
            "product_name": product.get("product_name", ""),
            "asin": product.get("asin", ""),
            "sku": product.get("sku", ""),
            "unit_cost": product.get("unit_cost", 0.0),
            "shipping_cost": product.get("shipping_cost", 0.0),
            "min_order": product.get("min_order", 1),
            "bulk_prices": json.dumps(bulk),
            "notes": product.get("notes", ""),
        }, fetch="one")
        return row["id"] if row else None

    def get_supplier_products(self, supplier_id: Optional[int] = None, asin: Optional[str] = None) -> List[Dict]:
        query = """
            SELECT sp.*, s.name as supplier_name
            FROM supplier_products sp
            LEFT JOIN suppliers s ON sp.supplier_id = s.id
        """
        params = []
        conditions = []
        if supplier_id:
            conditions.append("sp.supplier_id = %s")
            params.append(supplier_id)
        if asin:
            conditions.append("sp.asin = %s")
            params.append(asin)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY sp.created_at DESC"
        return self._execute(query, tuple(params), fetch="all")

    # ════════════════════════════════════════════════════════════
    # PRICING
    # ════════════════════════════════════════════════════════════

    def save_pricing(self, pricing: Dict[str, Any]) -> Optional[int]:
        row = self._execute("""
            INSERT INTO product_pricing (asin, product_name, supplier_id, supplier_cost,
                shipping_cost, customs_duty, packaging_cost, fba_fee, referral_fee,
                total_landed_cost, current_market_price, suggested_price, min_price,
                max_price, profit_per_unit, margin_pct, roi_pct, break_even_units,
                target_margin, notes)
            VALUES (%(asin)s, %(product_name)s, %(supplier_id)s, %(supplier_cost)s,
                %(shipping_cost)s, %(customs_duty)s, %(packaging_cost)s, %(fba_fee)s,
                %(referral_fee)s, %(total_landed_cost)s, %(current_market_price)s,
                %(suggested_price)s, %(min_price)s, %(max_price)s, %(profit_per_unit)s,
                %(margin_pct)s, %(roi_pct)s, %(break_even_units)s, %(target_margin)s, %(notes)s)
            ON CONFLICT (asin) DO UPDATE SET
                product_name=EXCLUDED.product_name, supplier_id=EXCLUDED.supplier_id,
                supplier_cost=EXCLUDED.supplier_cost, shipping_cost=EXCLUDED.shipping_cost,
                customs_duty=EXCLUDED.customs_duty, packaging_cost=EXCLUDED.packaging_cost,
                fba_fee=EXCLUDED.fba_fee, referral_fee=EXCLUDED.referral_fee,
                total_landed_cost=EXCLUDED.total_landed_cost,
                current_market_price=EXCLUDED.current_market_price,
                suggested_price=EXCLUDED.suggested_price, min_price=EXCLUDED.min_price,
                max_price=EXCLUDED.max_price, profit_per_unit=EXCLUDED.profit_per_unit,
                margin_pct=EXCLUDED.margin_pct, roi_pct=EXCLUDED.roi_pct,
                break_even_units=EXCLUDED.break_even_units,
                target_margin=EXCLUDED.target_margin, notes=EXCLUDED.notes,
                updated_at=CURRENT_TIMESTAMP
            RETURNING id
        """, {
            "asin": pricing.get("asin", ""),
            "product_name": pricing.get("product_name", ""),
            "supplier_id": pricing.get("supplier_id"),
            "supplier_cost": pricing.get("supplier_cost", 0.0),
            "shipping_cost": pricing.get("shipping_cost", 0.0),
            "customs_duty": pricing.get("customs_duty", 0.0),
            "packaging_cost": pricing.get("packaging_cost", 0.0),
            "fba_fee": pricing.get("fba_fee", 0.0),
            "referral_fee": pricing.get("referral_fee", 0.0),
            "total_landed_cost": pricing.get("total_landed_cost", 0.0),
            "current_market_price": pricing.get("current_market_price", 0.0),
            "suggested_price": pricing.get("suggested_price", 0.0),
            "min_price": pricing.get("min_price", 0.0),
            "max_price": pricing.get("max_price", 0.0),
            "profit_per_unit": pricing.get("profit_per_unit", 0.0),
            "margin_pct": pricing.get("margin_pct", 0.0),
            "roi_pct": pricing.get("roi_pct", 0.0),
            "break_even_units": pricing.get("break_even_units", 0),
            "target_margin": pricing.get("target_margin", 0.0),
            "notes": pricing.get("notes", ""),
        }, fetch="one")
        return row["id"] if row else None

    def get_pricing(self, asin: str) -> Optional[Dict]:
        return self._execute(
            "SELECT * FROM product_pricing WHERE asin = %s", (asin,), fetch="one"
        )

    # ════════════════════════════════════════════════════════════
    # PRODUCT CACHE
    # ════════════════════════════════════════════════════════════

    def cache_product(self, asin: str, data: Dict[str, Any]):
        self._execute("""
            INSERT INTO product_cache (asin, product_data, last_updated)
            VALUES (%s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (asin) DO UPDATE SET
                product_data=EXCLUDED.product_data, last_updated=CURRENT_TIMESTAMP
        """, (asin, json.dumps(data, default=str)))

    def get_cached_product(self, asin: str, max_age_hours: int = 24) -> Optional[Dict]:
        return self._execute("""
            SELECT product_data FROM product_cache
            WHERE asin = %s AND last_updated > NOW() - INTERVAL '%s hours'
        """, (asin, max_age_hours), fetch="one")

    # ════════════════════════════════════════════════════════════
    # PRICE HISTORY
    # ════════════════════════════════════════════════════════════

    def record_price(self, asin: str, product_name: str, source: str,
                     price: float, old_price: float = 0, in_stock: bool = True,
                     rating: float = 0, review_count: int = 0):
        self._execute("""
            INSERT INTO price_history (asin, product_name, source, price, old_price,
                in_stock, rating, review_count)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (asin, product_name, source, price, old_price, int(in_stock), rating, review_count))

    def get_price_history(self, asin: str, limit: int = 100) -> list:
        return self._execute(
            "SELECT * FROM price_history WHERE asin=%s ORDER BY recorded_at DESC LIMIT %s",
            (asin, limit), fetch="all"
        )

    # ════════════════════════════════════════════════════════════
    # REVIEW SENTIMENT
    # ════════════════════════════════════════════════════════════

    def save_review_sentiment(self, asin: str, product_name: str, data: dict):
        self._execute("""
            INSERT INTO review_sentiment (asin, product_name, total_reviews, positive_pct,
                negative_pct, neutral_pct, top_complaints, top_praises,
                recurring_issues, improvement_ideas, summary)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            asin, product_name, data.get("total_reviews", 0),
            data.get("positive_pct", 0), data.get("negative_pct", 0),
            data.get("neutral_pct", 0),
            json.dumps(data.get("top_complaints", [])),
            json.dumps(data.get("top_praises", [])),
            json.dumps(data.get("recurring_issues", [])),
            json.dumps(data.get("improvement_ideas", [])),
            data.get("summary", ""),
        ))

    def get_review_sentiment(self, asin: str) -> Optional[dict]:
        return self._execute(
            "SELECT * FROM review_sentiment WHERE asin=%s ORDER BY analyzed_at DESC LIMIT 1",
            (asin,), fetch="one"
        )

    # ════════════════════════════════════════════════════════════
    # SEASONALITY
    # ════════════════════════════════════════════════════════════

    def save_seasonality(self, asin: str, product_name: str, data: dict):
        self._execute("""
            INSERT INTO seasonality_data (asin, product_name, month, demand_level,
                search_volume, sales_estimate, peak_months, low_months, season_pattern)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            asin, product_name, data.get("month", 0),
            data.get("demand_level", "medium"), data.get("search_volume", 0),
            data.get("sales_estimate", 0), data.get("peak_months", ""),
            data.get("low_months", ""), data.get("season_pattern", ""),
        ))

    def get_seasonality(self, asin: str) -> list:
        return self._execute(
            "SELECT * FROM seasonality_data WHERE asin=%s ORDER BY recorded_at DESC LIMIT 12",
            (asin,), fetch="all"
        )

    # ════════════════════════════════════════════════════════════
    # COMPETITOR TRACKING
    # ════════════════════════════════════════════════════════════

    def record_competitor(self, asin: str, product_name: str, comp: dict):
        self._execute("""
            INSERT INTO competitor_tracking (asin, product_name, competitor_asin,
                competitor_name, competitor_price, competitor_rating,
                competitor_reviews, competitor_rank, in_stock)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            asin, product_name, comp.get("competitor_asin", ""),
            comp.get("competitor_name", ""), comp.get("competitor_price", 0),
            comp.get("competitor_rating", 0), comp.get("competitor_reviews", 0),
            comp.get("competitor_rank", 0), comp.get("in_stock", 1),
        ))

    def get_competitors(self, asin: str, limit: int = 50) -> list:
        return self._execute(
            "SELECT * FROM competitor_tracking WHERE asin=%s ORDER BY recorded_at DESC LIMIT %s",
            (asin, limit), fetch="all"
        )

    # ════════════════════════════════════════════════════════════
    # INVENTORY
    # ════════════════════════════════════════════════════════════

    def save_inventory(self, asin: str, product_name: str, data: dict):
        self._execute("""
            INSERT INTO inventory (asin, product_name, sku, current_stock, reorder_point,
                reorder_quantity, unit_cost, fba_shipment_id, fba_status, warehouse,
                last_restock_date, days_of_stock, monthly_velocity, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (asin) DO UPDATE SET
                product_name=EXCLUDED.product_name, sku=EXCLUDED.sku,
                current_stock=EXCLUDED.current_stock, reorder_point=EXCLUDED.reorder_point,
                reorder_quantity=EXCLUDED.reorder_quantity, unit_cost=EXCLUDED.unit_cost,
                fba_shipment_id=EXCLUDED.fba_shipment_id, fba_status=EXCLUDED.fba_status,
                warehouse=EXCLUDED.warehouse, last_restock_date=EXCLUDED.last_restock_date,
                days_of_stock=EXCLUDED.days_of_stock, monthly_velocity=EXCLUDED.monthly_velocity,
                notes=EXCLUDED.notes, updated_at=CURRENT_TIMESTAMP
        """, (
            asin, product_name, data.get("sku", ""),
            data.get("current_stock", 0), data.get("reorder_point", 10),
            data.get("reorder_quantity", 100), data.get("unit_cost", 0),
            data.get("fba_shipment_id", ""), data.get("fba_status", ""),
            data.get("warehouse", ""), data.get("last_restock_date", ""),
            data.get("days_of_stock", 0), data.get("monthly_velocity", 0),
            data.get("notes", ""),
        ))

    def get_inventory(self, asin: Optional[str] = None) -> list:
        if asin:
            return self._execute(
                "SELECT * FROM inventory WHERE asin=%s", (asin,), fetch="all"
            )
        return self._execute("SELECT * FROM inventory ORDER BY product_name", fetch="all")

    # ════════════════════════════════════════════════════════════
    # COMMENTS & TASKS
    # ════════════════════════════════════════════════════════════

    def add_comment(self, asin: str, author: str, comment: str, comment_type: str = "note"):
        self._execute(
            "INSERT INTO product_comments (asin, author, comment, comment_type) VALUES (%s, %s, %s, %s)",
            (asin, author, comment, comment_type)
        )

    def get_comments(self, asin: str) -> list:
        return self._execute(
            "SELECT * FROM product_comments WHERE asin=%s ORDER BY created_at DESC",
            (asin,), fetch="all"
        )

    def add_task(self, asin: str, product_name: str, task: str, assignee: str = "Unassigned",
                 priority: str = "medium", due_date: str = "") -> Optional[int]:
        row = self._execute("""
            INSERT INTO product_tasks (asin, product_name, task, assignee, priority, due_date)
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
        """, (asin, product_name, task, assignee, priority, due_date), fetch="one")
        return row["id"] if row else None

    def get_tasks(self, asin: Optional[str] = None) -> list:
        if asin:
            return self._execute(
                "SELECT * FROM product_tasks WHERE asin=%s ORDER BY created_at DESC",
                (asin,), fetch="all"
            )
        return self._execute("SELECT * FROM product_tasks ORDER BY created_at DESC", fetch="all")

    def toggle_task(self, task_id: int) -> bool:
        row = self._execute(
            "UPDATE product_tasks SET status = CASE WHEN status='done' THEN 'todo' ELSE 'done' END WHERE id=%s RETURNING status",
            (task_id,), fetch="one"
        )
        return row["status"] == "done" if row else False

    # ════════════════════════════════════════════════════════════
    # LISTING VERSIONS
    # ════════════════════════════════════════════════════════════

    def save_listing_version(self, asin: str, user_id: int, listing: dict) -> Optional[int]:
        max_ver = self._execute(
            "SELECT COALESCE(MAX(version_number), 0) FROM listing_versions WHERE asin=%s",
            (asin,), fetch="scalar"
        ) or 0
        row = self._execute("""
            INSERT INTO listing_versions (asin, user_id, version_number, title, bullets,
                description, search_terms, backend_keywords, seo_score, compliance_data, keywords)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
        """, (
            asin, user_id, max_ver + 1,
            listing.get("title", ""),
            json.dumps(listing.get("bullets", [])),
            listing.get("description", ""),
            listing.get("search_terms", ""),
            listing.get("backend_keywords", ""),
            listing.get("seo_score", 0),
            json.dumps(listing.get("compliance_data", {})),
            json.dumps(listing.get("keywords", [])),
        ), fetch="one")
        return row["id"] if row else None

    def get_listing_versions(self, asin: str) -> list:
        return self._execute(
            "SELECT * FROM listing_versions WHERE asin=%s ORDER BY version_number DESC",
            (asin,), fetch="all"
        )

    # ════════════════════════════════════════════════════════════
    # STATISTICS
    # ════════════════════════════════════════════════════════════

    def get_stats(self) -> dict:
        stats = {}
        stats["products"] = self._execute("SELECT COUNT(*) FROM products", fetch="scalar") or 0
        stats["suppliers"] = self._execute("SELECT COUNT(*) FROM suppliers", fetch="scalar") or 0
        stats["users"] = self._execute("SELECT COUNT(*) FROM users", fetch="scalar") or 0
        stats["price_history"] = self._execute("SELECT COUNT(*) FROM price_history", fetch="scalar") or 0
        stats["listings"] = self._execute("SELECT COUNT(*) FROM listing_versions", fetch="scalar") or 0
        size = self._execute(
            "SELECT pg_size_pretty(pg_database_size(current_database()))",
            fetch="scalar"
        )
        stats["db_size"] = size or "N/A"
        return stats
