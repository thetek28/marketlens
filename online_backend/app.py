"""MarketLens Cloud Backend - Unified FastAPI application.

Single backend serving both User Portal and Admin Center.
Uses UnifiedDB as the single source of truth.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from fastapi import FastAPI, HTTPException, Request, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from online_db.unified import UnifiedDB
from online_backend.config import BackendConfig
from online_backend.billing_routes import (
    setup_billing_user_routes, setup_billing_webhook_route, setup_billing_admin_routes
)
from online_backend.services.identity_service import ProductIdentityService, ProductRecord
from online_backend.services.scoring_engine import OpportunityScoringEngine, ScoreInputs
from online_backend.services.intelligence_service import ProductIntelligenceService

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "")


# ════════════════════════════════════════════════════════════
# MODELS
# ════════════════════════════════════════════════════════════

class RegisterRequest(BaseModel):
    username: str
    password: str
    email: str = ""

class LoginRequest(BaseModel):
    username: str
    password: str


# ════════════════════════════════════════════════════════════
# JWT HELPERS
# ════════════════════════════════════════════════════════════

import hmac
import base64

def _b64enc(data):
    return base64.urlsafe_b64encode(data).decode().rstrip("=")

def _b64dec(s):
    s += "=" * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(s)

def create_token(username: str, secret: str, expires_hours: int = 24) -> str:
    payload = {"sub": username, "exp": (datetime.utcnow() + timedelta(hours=expires_hours)).isoformat(), "iat": datetime.utcnow().isoformat()}
    header = _b64enc(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = _b64enc(json.dumps(payload).encode())
    sig = _b64enc(hmac.new(secret.encode(), f"{header}.{body}".encode(), "sha256").digest())
    return f"{header}.{body}.{sig}"

def decode_token(token: str, secret: str) -> Optional[dict]:
    try:
        parts = token.split(".")
        if len(parts) != 3: return None
        header, body, sig = parts
        expected = hmac.new(secret.encode(), f"{header}.{body}".encode(), "sha256").digest()
        actual = _b64dec(sig)
        if not hmac.compare_digest(expected, actual): return None
        payload = json.loads(_b64dec(body))
        if datetime.fromisoformat(payload.get("exp", "2000-01-01")) < datetime.utcnow(): return None
        return payload
    except Exception:
        return None

def create_admin_token(admin_id: int, username: str, role: str, secret: str) -> str:
    payload = {"sub": username, "admin_id": admin_id, "role": role,
               "exp": (datetime.utcnow() + timedelta(hours=12)).isoformat(),
               "iat": datetime.utcnow().isoformat(), "is_admin": True}
    header = _b64enc(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = _b64enc(json.dumps(payload).encode())
    sig = _b64enc(hmac.new(secret.encode(), f"{header}.{body}".encode(), "sha256").digest())
    return f"{header}.{body}.{sig}"

def decode_admin_token(token: str, secret: str) -> Optional[dict]:
    try:
        parts = token.split(".")
        if len(parts) != 3: return None
        header, body, sig = parts
        expected = hmac.new(secret.encode(), f"{header}.{body}".encode(), "sha256").digest()
        actual = _b64dec(sig)
        if not hmac.compare_digest(expected, actual): return None
        payload = json.loads(_b64dec(body))
        if datetime.fromisoformat(payload.get("exp", "2000-01-01")) < datetime.utcnow(): return None
        if not payload.get("is_admin"): return None
        return payload
    except Exception:
        return None


# ════════════════════════════════════════════════════════════
# APP FACTORY
# ════════════════════════════════════════════════════════════

def create_app() -> FastAPI:
    config = BackendConfig()
    db_url = DATABASE_URL or config.database_url
    db = UnifiedDB(db_url)

    app = FastAPI(title="MarketLens Cloud", version="5.0.0")

    # Initialize Product Intelligence Services
    identity_service = ProductIdentityService(db)
    scoring_engine = OpportunityScoringEngine(db)
    intelligence_service = ProductIntelligenceService(db)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins + ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ════════════════════════════════════════════════════════
    # AUTH DEPENDENCIES
    # ════════════════════════════════════════════════════════

    async def get_current_user(request: Request) -> dict:
        token = None
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "): token = auth[7:]
        if not token: token = request.cookies.get("mjl_token")
        if not token: raise HTTPException(401, "Not authenticated")
        payload = decode_token(token, config.jwt_secret)
        if not payload: raise HTTPException(401, "Invalid or expired token")
        user = db.get_user_by_username(payload["sub"])
        if not user: raise HTTPException(401, "User not found")
        if not user.get("is_active"): raise HTTPException(403, "Account suspended")
        return user

    async def get_admin_user(request: Request) -> dict:
        token = None
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "): token = auth[7:]
        if not token: token = request.cookies.get("mjl_admin_token")
        if not token: raise HTTPException(401, "Not authenticated")
        payload = decode_admin_token(token, config.jwt_secret)
        if not payload: raise HTTPException(401, "Invalid admin token")
        return payload

    def require_admin_role(*roles):
        async def checker(admin: dict = Depends(get_admin_user)):
            if admin.get("role") not in roles and admin.get("role") != "super_admin":
                raise HTTPException(403, "Insufficient permissions")
            return admin
        return checker

    # ════════════════════════════════════════════════════════
    # HEALTH
    # ════════════════════════════════════════════════════════

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "version": "4.0.0", "database": "postgresql"}

    # ════════════════════════════════════════════════════════
    # USER AUTH
    # ════════════════════════════════════════════════════════

    @app.post("/api/auth/register")
    async def register(req: RegisterRequest):
        if len(req.username) < 3 or len(req.password) < 6:
            raise HTTPException(400, "Username min 3, password min 6 chars")
        existing = db.get_user_by_username(req.username)
        if existing:
            raise HTTPException(400, "Username already taken")
        pw_hash = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode()
        user_id = db.create_user(req.username, pw_hash, req.email)
        if not user_id:
            raise HTTPException(500, "Failed to create user")
        db.create_subscription(user_id, "free", 30)
        token = create_token(req.username, config.jwt_secret, config.jwt_expiry_hours)
        return {"token": token, "user": {"id": user_id, "username": req.username}, "subscription": {"tier": "free"}}

    @app.post("/api/auth/login")
    async def login(req: LoginRequest):
        user = db.get_user_by_username(req.username)
        if not user or not bcrypt.checkpw(req.password.encode(), user["password_hash"].encode()):
            raise HTTPException(401, "Invalid credentials")
        if not user.get("is_active"):
            raise HTTPException(403, "Account suspended")
        # Update last_login
        from psycopg2 import connect
        conn = connect(db_url, sslmode="require")
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s", (user["id"],))
            conn.commit()
        finally:
            conn.close()
        token = create_token(req.username, config.jwt_secret, config.jwt_expiry_hours)
        sub = db.get_subscription(user["id"])
        return {"token": token, "user": {"id": user["id"], "username": user["username"]}, "subscription": sub or {"tier": "free"}}

    @app.get("/api/auth/me")
    async def get_me(user: dict = Depends(get_current_user)):
        sub = db.get_subscription(user["id"])
        usage = db.get_user_usage(user["id"])
        return {"id": user["id"], "username": user["username"], "email": user.get("email", ""),
                "subscription": sub or {"tier": "free"}, "usage": usage,
                "notifications_unread": db.unread_count(user["id"])}

    # ════════════════════════════════════════════════════════
    # PRODUCTS (shared global + user ownership)
    # ════════════════════════════════════════════════════════

    @app.get("/api/products/all")
    async def get_products_all(user: dict = Depends(get_current_user)):
        return {"products": db.get_all_products_from_db()}

    @app.get("/api/products/top20")
    async def get_products_top20(user: dict = Depends(get_current_user)):
        return {"products": db.get_all_products_from_db()[:20]}

    @app.get("/api/products")
    async def get_products(page: int = 1, per_page: int = 20, user: dict = Depends(get_current_user)):
        all_products = db.get_all_products_from_db()
        start = (page - 1) * per_page
        return {"products": all_products[start:start+per_page], "total": len(all_products), "page": page}

    @app.get("/api/products/{asin}")
    async def get_product(asin: str, user: dict = Depends(get_current_user)):
        p = db._exec("SELECT * FROM products WHERE asin = %s", (asin,), "one")
        if not p: raise HTTPException(404, "Product not found")
        product_dict = dict(p) if not isinstance(p, dict) else p
        # Parse score_breakdown
        if isinstance(product_dict.get("score_breakdown"), str):
            try:
                product_dict["score_breakdown"] = json.loads(product_dict["score_breakdown"])
            except:
                product_dict["score_breakdown"] = {}
        # Add recommendation
        from online_backend.services.scoring_engine import get_recommendation
        rec_label, rec_color = get_recommendation(product_dict.get("opportunity_score", 0))
        product_dict["recommendation"] = rec_label
        product_dict["recommendation_color"] = rec_color
        return product_dict

    # ════════════════════════════════════════════════════════
    # USER WATCHLIST
    # ════════════════════════════════════════════════════════

    @app.get("/api/watchlist")
    async def get_watchlist(user: dict = Depends(get_current_user)):
        return {"watchlist": db.get_watchlist(user["id"])}

    @app.post("/api/watchlist/{asin}")
    async def add_watchlist(asin: str, request: Request, user: dict = Depends(get_current_user)):
        body = await request.json() if request.headers.get("content-type") == "application/json" else {}
        ok = db.add_to_watchlist(user["id"], asin, body)
        if not ok: raise HTTPException(400, "Failed to add")
        return {"message": "Added to watchlist"}

    @app.delete("/api/watchlist/{asin}")
    async def remove_watchlist(asin: str, user: dict = Depends(get_current_user)):
        db.remove_from_watchlist(user["id"], asin)
        return {"message": "Removed from watchlist"}

    @app.get("/api/watchlist/{asin}/check")
    async def check_watchlist(asin: str, user: dict = Depends(get_current_user)):
        return {"watchlisted": db.is_watchlisted(user["id"], asin)}

    # ════════════════════════════════════════════════════════
    # USER TRACKING
    # ════════════════════════════════════════════════════════

    @app.get("/api/tracking")
    async def get_tracking(user: dict = Depends(get_current_user)):
        usage = db.get_user_usage(user["id"])
        if usage["remaining"]["tracking"] <= 0:
            raise HTTPException(403, "Tracking limit reached. Upgrade your plan.")
        return {"tracking": db.get_tracking(user["id"])}

    @app.post("/api/tracking/{asin}")
    async def add_tracking(asin: str, request: Request, user: dict = Depends(get_current_user)):
        if not db.check_and_consume_usage(user["id"], "tracking", 1):
            raise HTTPException(403, "Tracking limit reached")
        body = await request.json() if request.headers.get("content-type") == "application/json" else {}
        ok = db.add_tracking(user["id"], asin, body)
        return {"message": "Tracking added"}

    @app.delete("/api/tracking/{asin}")
    async def remove_tracking(asin: str, user: dict = Depends(get_current_user)):
        db.remove_tracking(user["id"], asin)
        return {"message": "Tracking removed"}

    # ════════════════════════════════════════════════════════
    # RESEARCH
    # ════════════════════════════════════════════════════════

    @app.get("/api/research")
    async def get_research(user: dict = Depends(get_current_user)):
        return db.get_user_research(user["id"])

    @app.post("/api/research")
    async def create_research(request: Request, user: dict = Depends(get_current_user)):
        if not db.check_and_consume_usage(user["id"], "research", 1):
            raise HTTPException(403, "Research limit reached. Upgrade your plan.")
        body = await request.json()
        job_id = db.create_research_job(user["id"], body.get("query", ""), body.get("marketplace", "US"), body.get("category", ""))
        return {"id": job_id, "status": "queued"}

    # ════════════════════════════════════════════════════════
    # LISTINGS
    # ════════════════════════════════════════════════════════

    @app.get("/api/listing/{asin}")
    async def get_listing(asin: str, user: dict = Depends(get_current_user)):
        products = db.get_all_products_from_db()
        p = next((x for x in products if x.get("asin") == asin), None)
        if not p: raise HTTPException(404, "Product not found")
        name = p.get("name", "")
        category = p.get("category", "")
        core_kw = [w.lower() for w in name.split() if len(w) > 2][:10]
        title = f"{core_kw[0].title() if core_kw else ''} {name} - Premium {category}"
        bullets = [f"Premium {name} designed for everyday use", f"Premium materials ensure long-lasting durability",
                   f"Perfect for {category} enthusiasts of all levels", f"Compact and lightweight design for easy portability",
                   f"100% satisfaction guaranteed with full refund policy"]
        description = f"Introducing our premium {name}, crafted with the highest quality materials for exceptional performance in {category}."
        seo_score = min(100, 50 + len(core_kw) * 5 + (15 if len(title) > 50 else 0))
        return {"asin": asin, "name": name, "category": category, "brand": p.get("brand", ""),
                "price": p.get("amazon_price", 0), "rating": p.get("rating", 0), "reviews": p.get("review_count", 0),
                "title": title, "bullets": bullets, "description": description,
                "search_terms": " ".join(core_kw[:5]), "backend_keywords": " ".join(core_kw), "seo_score": seo_score}

    @app.post("/api/listing/{asin}/save")
    async def save_listing(asin: str, request: Request, user: dict = Depends(get_current_user)):
        if not db.check_and_consume_usage(user["id"], "listings", 1):
            raise HTTPException(403, "Listing generation limit reached")
        body = await request.json()
        vid = db.save_listing(asin, user["id"], body)
        return {"id": vid, "message": "Listing saved"}

    @app.get("/api/listing/{asin}/versions")
    async def get_listing_versions(asin: str, user: dict = Depends(get_current_user)):
        return {"versions": db.get_user_listings(user["id"])}

    # ════════════════════════════════════════════════════════
    # SUPPLIERS (shared, user-created ones are user-owned)
    # ════════════════════════════════════════════════════════

    @app.get("/api/suppliers")
    async def get_suppliers(user: dict = Depends(get_current_user)):
        return {"suppliers": db.get_all_suppliers()}

    @app.post("/api/suppliers")
    async def add_supplier(request: Request, user: dict = Depends(get_current_user)):
        body = await request.json()
        sid = db.add_supplier(body)
        return {"id": sid, "message": "Supplier added"}

    @app.delete("/api/suppliers/{supplier_id}")
    async def delete_supplier(supplier_id: int, user: dict = Depends(get_current_user)):
        db.delete_supplier(supplier_id)
        return {"message": "Supplier deleted"}

    # ════════════════════════════════════════════════════════
    # USER SETTINGS
    # ════════════════════════════════════════════════════════

    @app.get("/api/user/settings")
    async def get_user_settings(user: dict = Depends(get_current_user)):
        rows = db._exec("SELECT setting_key, setting_value FROM user_settings WHERE user_id = %s", (user["id"],), "all")
        return {"settings": {r["setting_key"]: r["setting_value"] for r in rows}}

    @app.post("/api/user/settings")
    async def save_user_settings(request: Request, user: dict = Depends(get_current_user)):
        body = await request.json()
        for k, v in body.get("settings", {}).items():
            db._exec(
                "INSERT INTO user_settings (user_id, setting_key, setting_value) VALUES (%s,%s,%s) ON CONFLICT (user_id, setting_key) DO UPDATE SET setting_value = EXCLUDED.setting_value, updated_at = CURRENT_TIMESTAMP",
                (user["id"], k, str(v))
            )
        return {"message": "Settings saved"}

    # ════════════════════════════════════════════════════════
    # USER CREDITS & USAGE
    # ════════════════════════════════════════════════════════

    @app.get("/api/user/usage")
    async def get_usage(user: dict = Depends(get_current_user)):
        return db.get_user_usage(user["id"])

    @app.get("/api/user/notifications")
    async def get_notifications(user: dict = Depends(get_current_user)):
        return {"notifications": db.get_notifications(user["id"])}

    @app.post("/api/user/notifications/{notif_id}/read")
    async def mark_read(notif_id: int, user: dict = Depends(get_current_user)):
        db.mark_notification_read(user["id"], notif_id)
        return {"status": "ok"}

    # ════════════════════════════════════════════════════════
    # SHARED: Price History, Inventory, Comments, Tasks
    # ════════════════════════════════════════════════════════

    @app.get("/api/price-history/{asin}")
    async def price_history(asin: str, user: dict = Depends(get_current_user)):
        return {"history": db.get_price_history(asin)}

    @app.post("/api/price-history/{asin}/record")
    async def record_price(asin: str, request: Request, user: dict = Depends(get_current_user)):
        body = await request.json()
        db.record_price(asin, body.get("product_name", ""), body.get("source", "manual"), body.get("price", 0), body.get("old_price", 0))
        return {"message": "Price recorded"}

    @app.get("/api/inventory/{asin}")
    async def get_inventory(asin: str, user: dict = Depends(get_current_user)):
        inv = db.get_inventory(asin)
        return {"inventory": inv[0] if inv else None}

    @app.post("/api/inventory/{asin}")
    async def save_inventory(asin: str, request: Request, user: dict = Depends(get_current_user)):
        body = await request.json()
        db.save_inventory(asin, body.get("product_name", ""), body)
        return {"message": "Inventory saved"}

    @app.get("/api/notes/{asin}")
    async def get_notes(asin: str, user: dict = Depends(get_current_user)):
        return {"notes": db.get_comments(asin)}

    @app.post("/api/notes/{asin}")
    async def save_notes(asin: str, request: Request, user: dict = Depends(get_current_user)):
        body = await request.json()
        db.add_comment(asin, user["username"], body.get("comment", ""), body.get("type", "note"), user["id"])
        return {"message": "Note saved"}

    @app.get("/api/team/tasks/{asin}")
    async def get_tasks(asin: str, user: dict = Depends(get_current_user)):
        return {"tasks": db.get_tasks(asin)}

    @app.post("/api/team/tasks/{asin}")
    async def add_task(asin: str, request: Request, user: dict = Depends(get_current_user)):
        body = await request.json()
        db.add_task(asin, body.get("product_name", ""), body.get("task", ""),
                    body.get("assignee", "Unassigned"), body.get("priority", "medium"), user["id"])
        return {"message": "Task added"}

    @app.post("/api/team/tasks/{task_id}/toggle")
    async def toggle_task(task_id: int, user: dict = Depends(get_current_user)):
        done = db.toggle_task(task_id)
        return {"status": "done" if done else "todo"}

    # ════════════════════════════════════════════════════════
    # DATABASE STATS
    # ════════════════════════════════════════════════════════

    @app.get("/api/database/stats")
    async def db_stats(user: dict = Depends(get_current_user)):
        return db.get_stats()

    @app.get("/api/config")
    async def get_config(user: dict = Depends(get_current_user)):
        return {"categories": [], "keywords": [], "config": {}}

    # ════════════════════════════════════════════════════════
    # CHARTS & STATUS
    # ════════════════════════════════════════════════════════

    @app.get("/api/status")
    async def get_status(user: dict = Depends(get_current_user)):
        return {"running": False, "cycle": 0, "total_products": len(db.get_all_products_from_db()),
                "hidden_gems": 0, "seen_asins": 0, "elapsed_seconds": 0,
                "categories": ["Kitchen", "Electronics", "Beauty"], "keywords": ["trending"]}

    @app.get("/api/charts/data")
    async def get_charts_data(user: dict = Depends(get_current_user)):
        products = db.get_all_products_from_db()[:20]
        categories = {}
        for p in products:
            cat = p.get("category", "Unknown")
            if cat not in categories: categories[cat] = {"count": 0, "margins": [], "ais": []}
            categories[cat]["count"] += 1
            categories[cat]["margins"].append(p.get("estimated_margin_pct", 0))
            categories[cat]["ais"].append(p.get("ai_score", 0))
        for cat in categories:
            m, a = categories[cat]["margins"], categories[cat]["ais"]
            categories[cat] = {"count": categories[cat]["count"], "avg_margin": round(sum(m)/len(m),1) if m else 0, "avg_ai": round(sum(a)/len(a)*100,1) if a else 0}
        traffic = {"GREEN": 0, "YELLOW": 0, "RED": 0}
        for p in products: traffic[p.get("traffic_light", "RED")] = traffic.get(p.get("traffic_light", "RED"), 0) + 1
        return {"categories": categories, "price_distribution": {"under_20":0,"20_50":0,"50_100":0,"over_100":0},
                "traffic_lights": traffic, "ai_distribution": {"low":0,"medium":0,"high":0,"very_high":0}, "total": len(products)}

    # ════════════════════════════════════════════════════════
    # ANALYSIS (background worker)
    # ════════════════════════════════════════════════════════

    import threading, random, string, time as _time

    _analysis_state = {"running": False, "cycle": 0}

    SAMPLE_PRODUCTS = [
        {"name": "Stanley Quencher H2.0 Tumbler 40oz", "category": "Kitchen", "price": 45.0, "rating": 4.7, "reviews": 12500, "ai": 92, "margin": 42, "tl": "GREEN"},
        {"name": "COSRX Snail Mucin 96 Essence", "category": "Beauty", "price": 13.57, "rating": 4.6, "reviews": 45000, "ai": 88, "margin": 55, "tl": "GREEN"},
        {"name": "Beckham Hotel Collection Gel Pillow", "category": "Home & Kitchen", "price": 49.99, "rating": 4.4, "reviews": 32000, "ai": 85, "margin": 48, "tl": "GREEN"},
        {"name": "Liquid I.V. Hydration Multiplier", "category": "Health", "price": 24.99, "rating": 4.5, "reviews": 28000, "ai": 82, "margin": 38, "tl": "GREEN"},
        {"name": "YETI Rambler 20oz Tumbler", "category": "Kitchen", "price": 35.0, "rating": 4.7, "reviews": 15000, "ai": 90, "margin": 40, "tl": "GREEN"},
        {"name": "Anker Nano II 65W USB-C Charger", "category": "Electronics", "price": 27.99, "rating": 4.7, "reviews": 22000, "ai": 87, "margin": 35, "tl": "GREEN"},
        {"name": "CeraVe Moisturizing Cream 19oz", "category": "Beauty", "price": 16.99, "rating": 4.8, "reviews": 67000, "ai": 91, "margin": 50, "tl": "GREEN"},
        {"name": "Fitbit Charge 6 Fitness Tracker", "category": "Sports", "price": 99.95, "rating": 4.2, "reviews": 8500, "ai": 78, "margin": 25, "tl": "YELLOW"},
        {"name": "Dr. Bronner's Pure Castile Soap", "category": "Beauty", "price": 17.99, "rating": 4.7, "reviews": 19000, "ai": 84, "margin": 45, "tl": "GREEN"},
        {"name": "KitchenAid Classic Stand Mixer", "category": "Kitchen", "price": 279.99, "rating": 4.8, "reviews": 41000, "ai": 94, "margin": 30, "tl": "GREEN"},
        {"name": "Dyson V8 Cordless Vacuum", "category": "Home & Kitchen", "price": 349.99, "rating": 4.5, "reviews": 18000, "ai": 89, "margin": 22, "tl": "YELLOW"},
        {"name": "Native Deodorant Natural", "category": "Beauty", "price": 12.99, "rating": 4.4, "reviews": 52000, "ai": 83, "margin": 52, "tl": "GREEN"},
        {"name": "Echo Dot 5th Gen Smart Speaker", "category": "Electronics", "price": 22.99, "rating": 4.6, "reviews": 95000, "ai": 86, "margin": 15, "tl": "YELLOW"},
        {"name": "Aqua Rights Vitamin C Serum", "category": "Beauty", "price": 19.99, "rating": 4.3, "reviews": 11000, "ai": 80, "margin": 60, "tl": "GREEN"},
        {"name": "Lodge Cast Iron Skillet 12in", "category": "Kitchen", "price": 29.99, "rating": 4.7, "reviews": 73000, "ai": 88, "margin": 40, "tl": "GREEN"},
    ]

    @app.get("/api/analysis/status")
    async def analysis_status(user: dict = Depends(get_current_user)):
        return {"running": _analysis_state["running"], "cycle": _analysis_state["cycle"],
                "total_products": len(db.get_all_products_from_db())}

    @app.post("/api/analysis/start")
    async def analysis_start(user: dict = Depends(get_current_user)):
        if _analysis_state["running"]: raise HTTPException(400, "Already running")
        _analysis_state["running"] = True
        def worker():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                while _analysis_state["running"]:
                    _analysis_state["cycle"] += 1
                    for sp in SAMPLE_PRODUCTS:
                        if not _analysis_state["running"]: break
                        try:
                            # Use identity service for proper upsert (no duplicate ASINs)
                            record = ProductRecord(
                                asin="B0" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8)),
                                name=sp["name"],
                                category=sp["category"],
                                marketplace="US",
                                price=sp["price"],
                                rating=sp["rating"],
                                review_count=sp["reviews"],
                                source_name="demo_worker",
                            )
                            # Upsert uses ON CONFLICT — same product name gets same canonical ASIN
                            identity_service.upsert_product(record)

                            # Calculate opportunity score using structured engine
                            score_inputs = ScoreInputs(
                                price=sp["price"],
                                rating=sp["rating"],
                                review_count=sp["reviews"],
                                category=sp["category"],
                                marketplace="US",
                            )
                            score_result = scoring_engine.calculate_score(score_inputs)
                        except Exception as e:
                            logger.error("Insert failed: %s", e)
                    for _ in range(60):
                        if not _analysis_state["running"]: break
                        _time.sleep(1)
            except Exception as e:
                logger.error("Worker error: %s", e)
            finally:
                _analysis_state["running"] = False
        threading.Thread(target=worker, daemon=True).start()
        return {"status": "started"}

    @app.post("/api/analysis/stop")
    async def analysis_stop(user: dict = Depends(get_current_user)):
        _analysis_state["running"] = False
        return {"status": "stopped"}

    @app.post("/api/analysis/cycle")
    async def analysis_cycle(user: dict = Depends(get_current_user)):
        return {"status": "ok", "products": len(db.get_all_products_from_db())}

    @app.post("/api/analysis/collect")
    async def analysis_collect(user: dict = Depends(get_current_user)):
        return {"status": "ok", "products": 0}

    # ════════════════════════════════════════════════════════
    # PRODUCT INTELLIGENCE — RESEARCH SEARCH
    # ════════════════════════════════════════════════════════

    @app.get("/api/research/search")
    async def research_search(
        q: str = "",
        category: str = "",
        marketplace: str = "",
        min_price: float = 0,
        max_price: float = 0,
        min_rating: float = 0,
        min_reviews: int = 0,
        min_opportunity: float = 0,
        sort: str = "opportunity",
        page: int = 1,
        per_page: int = 20,
        user: dict = Depends(get_current_user)
    ):
        """Server-side filtered search with dedup. Returns canonical products only."""
        where_clauses = ["1=1"]
        params = []

        if q:
            where_clauses.append("(p.name ILIKE %s OR p.asin ILIKE %s OR p.brand ILIKE %s)")
            params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
        if category:
            where_clauses.append("p.category = %s")
            params.append(category)
        if marketplace:
            where_clauses.append("p.marketplace = %s")
            params.append(marketplace)
        if min_price > 0:
            where_clauses.append("p.amazon_price >= %s")
            params.append(min_price)
        if max_price > 0:
            where_clauses.append("p.amazon_price <= %s")
            params.append(max_price)
        if min_rating > 0:
            where_clauses.append("p.rating >= %s")
            params.append(min_rating)
        if min_reviews > 0:
            where_clauses.append("p.review_count >= %s")
            params.append(min_reviews)
        if min_opportunity > 0:
            where_clauses.append("p.opportunity_score >= %s")
            params.append(min_opportunity)

        where_sql = " AND ".join(where_clauses)

        sort_map = {
            "opportunity": "p.opportunity_score DESC NULLS LAST",
            "demand": "p.review_count DESC NULLS LAST",
            "price_low": "p.amazon_price ASC NULLS LAST",
            "price_high": "p.amazon_price DESC NULLS LAST",
            "rating": "p.rating DESC NULLS LAST",
            "reviews": "p.review_count DESC NULLS LAST",
            "newest": "p.last_observed_at DESC NULLS LAST",
            "relevance": "p.opportunity_score DESC NULLS LAST",
        }
        order_sql = sort_map.get(sort, "p.opportunity_score DESC NULLS LAST")

        # Count total unique products
        count_sql = f"SELECT COUNT(*) as total FROM products p WHERE {where_sql}"
        total_result = db._exec(count_sql, tuple(params), "one")
        total = total_result["total"] if total_result else 0

        # Fetch page
        offset = (page - 1) * per_page
        query_sql = f"""
            SELECT p.asin, p.name, p.category, p.brand, p.marketplace,
                   p.amazon_price, p.rating, p.review_count,
                   p.opportunity_score, p.opportunity_confidence, p.data_quality_score,
                   p.score_breakdown, p.traffic_light, p.image_url, p.product_url,
                   p.normalized_title, p.source_count, p.observation_count,
                   p.last_observed_at, p.scoring_version, p.created_at, p.updated_at
            FROM products p
            WHERE {where_sql}
            ORDER BY {order_sql}
            LIMIT %s OFFSET %s
        """
        products = db._exec(query_sql, tuple(params + [per_page, offset]), "all") or []

        # Enrich products with intelligence data
        enriched = []
        for p in products:
            product_dict = dict(p) if not isinstance(p, dict) else p
            # Parse score_breakdown if it's a string
            if isinstance(product_dict.get("score_breakdown"), str):
                try:
                    product_dict["score_breakdown"] = json.loads(product_dict["score_breakdown"])
                except:
                    product_dict["score_breakdown"] = {}
            # Add recommendation
            from online_backend.services.scoring_engine import get_recommendation
            rec_label, rec_color = get_recommendation(product_dict.get("opportunity_score", 0))
            product_dict["recommendation"] = rec_label
            product_dict["recommendation_color"] = rec_color
            # Add freshness
            if product_dict.get("last_observed_at"):
                from datetime import datetime
                try:
                    obs_time = product_dict["last_observed_at"]
                    if isinstance(obs_time, str):
                        obs_time = datetime.fromisoformat(obs_time)
                    hours_ago = (datetime.utcnow() - obs_time).total_seconds() / 3600
                    product_dict["data_freshness_hours"] = round(hours_ago, 1)
                except:
                    product_dict["data_freshness_hours"] = None
            enriched.append(product_dict)

        return {
            "products": enriched,
            "total": total,
            "totalUnique": total,
            "page": page,
            "pageSize": per_page,
            "totalPages": (total + per_page - 1) // per_page if per_page > 0 else 0,
            "dataQuality": {
                "uniqueProducts": total,
                "searchQuery": q,
            }
        }

    @app.get("/api/research/categories")
    async def research_categories(user: dict = Depends(get_current_user)):
        """Get available categories for filtering."""
        cats = db._exec(
            "SELECT DISTINCT category, COUNT(*) as count FROM products WHERE category != '' GROUP BY category ORDER BY count DESC",
            fetch="all"
        ) or []
        return {"categories": [dict(c) for c in cats]}

    # ════════════════════════════════════════════════════════
    # PRODUCT INTELLIGENCE — OBSERVATIONS & HISTORY
    # ════════════════════════════════════════════════════════

    @app.get("/api/products/{asin}/observations")
    async def product_observations(asin: str, limit: int = 50, user: dict = Depends(get_current_user)):
        """Get historical market observations for a product."""
        history = identity_service.get_product_history(asin, limit)
        return {"observations": history, "asin": asin}

    @app.get("/api/products/{asin}/sources")
    async def product_sources(asin: str, user: dict = Depends(get_current_user)):
        """Get source provenance for a product."""
        sources = identity_service.get_product_sources(asin)
        return {"sources": sources, "asin": asin}

    @app.get("/api/products/{asin}/score-history")
    async def score_history(asin: str, user: dict = Depends(get_current_user)):
        """Get score history and trend for a product."""
        history = intelligence_service.score_history_summary(asin)
        return {"history": history, "asin": asin}

    @app.get("/api/products/{asin}/intelligence")
    async def product_intelligence(asin: str, user: dict = Depends(get_current_user)):
        """Get full intelligence package for a product: score, explanation, analysis."""
        product = db._exec("SELECT * FROM products WHERE asin = %s", (asin,), "one")
        if not product:
            raise HTTPException(404, "Product not found")

        product_dict = dict(product) if not isinstance(product, dict) else product
        if isinstance(product_dict.get("score_breakdown"), str):
            try:
                product_dict["score_breakdown"] = json.loads(product_dict["score_breakdown"])
            except:
                product_dict["score_breakdown"] = {}

        breakdown = product_dict.get("score_breakdown", {})
        explanation = intelligence_service.generate_explanation(product_dict, breakdown)
        components = intelligence_service.get_score_components_display(breakdown)
        analysis = intelligence_service.get_market_analysis(product_dict, breakdown)
        history = intelligence_service.score_history_summary(asin)
        observations = identity_service.get_product_history(asin, 30)
        sources = identity_service.get_product_sources(asin)

        return {
            "product": product_dict,
            "explanation": explanation,
            "score_components": components,
            "market_analysis": analysis,
            "score_history": history,
            "observations": observations,
            "sources": sources,
        }

    @app.post("/api/products/{asin}/recalculate")
    async def recalculate_score(asin: str, user: dict = Depends(get_current_user)):
        """Recalculate opportunity score for a product using current scoring version."""
        result = scoring_engine.recalculate_score(asin)
        if not result:
            raise HTTPException(404, "Product not found or scoring failed")
        return {"result": result.to_dict(), "asin": asin}

    @app.post("/api/research/import")
    async def import_products(request: Request, user: dict = Depends(get_current_user)):
        """Import products with identity resolution and dedup."""
        body = await request.json()
        raw_products = body.get("products", [])
        if not raw_products:
            raise HTTPException(400, "No products provided")

        imported = 0
        duplicates = 0
        for raw in raw_products:
            record = ProductRecord(
                asin=raw.get("asin", ""),
                name=raw.get("name", raw.get("title", "")),
                brand=raw.get("brand", ""),
                model_number=raw.get("model_number", ""),
                category=raw.get("category", ""),
                marketplace=raw.get("marketplace", "US"),
                price=raw.get("price", raw.get("amazon_price", 0)),
                rating=raw.get("rating", 0),
                review_count=raw.get("review_count", raw.get("reviews", 0)),
                product_url=raw.get("product_url", raw.get("url", "")),
                image_url=raw.get("image_url", raw.get("image", "")),
                source_name=raw.get("source", "import"),
                full_data=raw,
            )
            existing = identity_service.resolve_product(record)
            identity_service.upsert_product(record)
            if existing:
                duplicates += 1
            else:
                imported += 1

        return {
            "imported": imported,
            "duplicates": duplicates,
            "total": len(raw_products),
            "message": f"Imported {imported} new products, {duplicates} duplicates merged"
        }

    # ════════════════════════════════════════════════════════
    # ADMIN — DATA QUALITY
    # ════════════════════════════════════════════════════════

    @app.get("/api/admin/data-quality")
    async def admin_data_quality(admin: dict = Depends(get_admin_user)):
        """Get data quality dashboard stats."""
        stats = {}
        # Total products
        r = db._exec("SELECT COUNT(*) as total FROM products", fetch="one")
        stats["totalProducts"] = r["total"] if r else 0

        # Unique products (by ASIN - already unique by constraint)
        stats["uniqueProducts"] = stats["totalProducts"]

        # Duplicate records consolidated (from merge log)
        r = db._exec("SELECT COUNT(*) as total FROM product_merge_log", fetch="one")
        stats["duplicatesConsolidated"] = r["total"] if r else 0

        # Duplicate rate
        total_raw = stats["totalProducts"] + stats["duplicatesConsolidated"]
        stats["duplicateRate"] = round(stats["duplicatesConsolidated"] / max(total_raw, 1) * 100, 1)

        # Missing fields
        r = db._exec("SELECT COUNT(*) as total FROM products WHERE asin IS NULL OR asin = ''", fetch="one")
        stats["missingAsin"] = r["total"] if r else 0
        r = db._exec("SELECT COUNT(*) as total FROM products WHERE amazon_price IS NULL OR amazon_price = 0", fetch="one")
        stats["missingPrice"] = r["total"] if r else 0
        r = db._exec("SELECT COUNT(*) as total FROM products WHERE rating IS NULL OR rating = 0", fetch="one")
        stats["missingRating"] = r["total"] if r else 0
        r = db._exec("SELECT COUNT(*) as total FROM products WHERE category IS NULL OR category = ''", fetch="one")
        stats["missingCategory"] = r["total"] if r else 0

        # Stale data (not observed in 7 days)
        r = db._exec(
            "SELECT COUNT(*) as total FROM products WHERE last_observed_at IS NULL OR last_observed_at < CURRENT_TIMESTAMP - INTERVAL '7 days'",
            fetch="one"
        )
        stats["staleData"] = r["total"] if r else 0

        # Average data quality
        r = db._exec("SELECT AVG(data_quality_score) as avg FROM products WHERE data_quality_score > 0", fetch="one")
        stats["avgDataQuality"] = round(r["avg"], 1) if r and r["avg"] else 0

        # Average opportunity score
        r = db._exec("SELECT AVG(opportunity_score) as avg FROM products WHERE opportunity_score > 0", fetch="one")
        stats["avgOpportunityScore"] = round(r["avg"], 1) if r and r["avg"] else 0

        # Total observations
        r = db._exec("SELECT COUNT(*) as total FROM product_observations", fetch="one")
        stats["totalObservations"] = r["total"] if r else 0

        # Total sources
        r = db._exec("SELECT COUNT(DISTINCT source_name) as total FROM product_sources", fetch="one")
        stats["uniqueSources"] = r["total"] if r else 0

        # Pending duplicate reviews
        r = db._exec("SELECT COUNT(*) as total FROM duplicate_review_queue WHERE status = 'pending'", fetch="one")
        stats["pendingDuplicateReviews"] = r["total"] if r else 0

        return stats

    @app.get("/api/admin/duplicates")
    async def admin_duplicates(status: str = "pending", page: int = 1, per_page: int = 20, admin: dict = Depends(get_admin_user)):
        """Get duplicate review queue."""
        where = "WHERE status = %s" if status else ""
        params = [status] if status else []
        offset = (page - 1) * per_page

        count = db._exec(f"SELECT COUNT(*) as total FROM duplicate_review_queue {where}", tuple(params), "one")
        total = count["total"] if count else 0

        items = db._exec(
            f"""SELECT dq.*, 
                       pa.name as product_a_name, pa.amazon_price as product_a_price,
                       pb.name as product_b_name, pb.amazon_price as product_b_price
                FROM duplicate_review_queue dq
                LEFT JOIN products pa ON dq.product_a_asin = pa.asin
                LEFT JOIN products pb ON dq.product_b_asin = pb.asin
                {where}
                ORDER BY dq.created_at DESC LIMIT %s OFFSET %s""",
            tuple(params + [per_page, offset]), "all"
        ) or []

        return {"items": items, "total": total, "page": page, "per_page": per_page}

    @app.post("/api/admin/duplicates/{queue_id}/resolve")
    async def resolve_duplicate(queue_id: int, request: Request, admin: dict = Depends(get_admin_user)):
        """Resolve a duplicate review item (merge or keep separate)."""
        body = await request.json()
        resolution = body.get("resolution", "keep_separate")

        item = db._exec("SELECT * FROM duplicate_review_queue WHERE id = %s", (queue_id,), "one")
        if not item:
            raise HTTPException(404, "Queue item not found")

        if resolution == "merge":
            success = identity_service.merge_products(
                item["product_a_asin"], item["product_b_asin"],
                reason="admin_merge", confidence=item["match_confidence"],
                matched_fields=item.get("match_reasons", []),
                merged_by=f"admin_{admin.get('admin_id', 'unknown')}"
            )
            if not success:
                raise HTTPException(500, "Merge failed")

        db._exec(
            "UPDATE duplicate_review_queue SET status = %s, reviewed_by = %s, reviewed_at = CURRENT_TIMESTAMP, resolution = %s WHERE id = %s",
            (resolution, admin.get("admin_id"), resolution, queue_id)
        )
        return {"status": "resolved", "resolution": resolution}

    @app.post("/api/admin/score-debug")
    async def score_debug(request: Request, admin: dict = Depends(get_admin_user)):
        """Debug scoring for a product — shows full calculation breakdown."""
        body = await request.json()
        asin = body.get("asin", "")
        if not asin:
            raise HTTPException(400, "ASIN required")

        product = db._exec("SELECT * FROM products WHERE asin = %s", (asin,), "one")
        if not product:
            raise HTTPException(404, "Product not found")

        product_dict = dict(product) if not isinstance(product, dict) else product

        # Recalculate
        result = scoring_engine.recalculate_score(asin)
        if not result:
            raise HTTPException(500, "Scoring failed")

        return {
            "asin": asin,
            "product_name": product_dict.get("name", ""),
            "current_score": product_dict.get("opportunity_score", 0),
            "recalculated": result.to_dict(),
            "previous_breakdown": product_dict.get("score_breakdown", {}),
            "weights": scoring_engine.weights,
        }

    @app.post("/api/admin/recalculate-all")
    async def recalculate_all(admin: dict = Depends(get_admin_user)):
        """Recalculate scores for all products as a background task."""
        import threading
        _recalc_state = {"running": True, "updated": 0, "total": 0, "errors": 0}

        def _worker():
            import json as _json
            import hashlib
            import math
            try:
                products = db._exec("SELECT asin, amazon_price, rating, review_count, supplier_price, category FROM public.products ORDER BY id", fetch="all") or []
                _recalc_state["total"] = len(products)

                for i, p in enumerate(products):
                    try:
                        price = p.get("amazon_price")
                        rating = p.get("rating")
                        reviews = p.get("review_count")
                        supplier = p.get("supplier_price")
                        cat = p.get("category", "")
                        asin = p["asin"]

                        if reviews and reviews >= 10:
                            lr = math.log10(max(reviews/500, 0.01))
                            d = max(0, min(100, (lr+2)/5*100))
                        elif reviews and reviews > 0: d = 15
                        else: d = 50

                        if reviews and reviews > 50000: c = 20
                        elif reviews and reviews > 20000: c = 35
                        elif reviews and reviews > 5000: c = 50
                        elif reviews and reviews > 1000: c = 65
                        elif reviews and reviews > 100: c = 75
                        else: c = 85

                        if price and price > 0 and supplier:
                            ref = price*0.15; fba = 3+price*0.05
                            margin = (price-supplier-ref-fba)/price*100
                            pr = 95 if margin>=40 else (85 if margin>=30 else (70 if margin>=20 else (55 if margin>=15 else (40 if margin>=10 else (25 if margin>=5 else (15 if margin>0 else 5))))))
                        elif price and price > 0: pr = 40
                        else: pr = 50

                        t = 50
                        mg = 70 if rating and rating < 4.0 else (55 if rating and rating < 4.3 else 40)
                        ro = 75 if rating and rating < 4.0 else (60 if rating and rating < 4.3 else 45)
                        ps = 70

                        if price and price > 0 and supplier:
                            ratio = supplier/price
                            sp = 90 if ratio<=0.15 else (75 if ratio<=0.25 else (60 if ratio<=0.35 else (40 if ratio<=0.50 else 20)))
                        else: sp = 40

                        risk = 30
                        if reviews and reviews < 10: risk += 30
                        elif reviews and reviews < 50: risk += 15
                        if rating and rating < 3.5: risk += 30
                        elif rating and rating < 4.0: risk += 10
                        r = max(0, min(100, 100-risk))

                        sc = round(d*0.20 + c*0.20 + pr*0.20 + t*0.10 + mg*0.10 + ro*0.05 + ps*0.05 + sp*0.05 + r*0.05, 1)
                        sc = max(0, min(100, sc))

                        fields = [bool(price and price>0), bool(rating and rating>0), bool(reviews and reviews>0), bool(cat), bool(supplier)]
                        dq = round(sum(fields)/len(fields)*100, 1)
                        avail = sum(fields)
                        conf = "high" if avail>=4 else ("medium" if avail>=3 else "low")
                        bd = _json.dumps({"demand":round(d,1),"competition":round(c,1),"profitability":round(pr,1),"trend":t,"market_gap":round(mg,1),"review_opportunity":round(ro,1),"price_stability":ps,"supplier_potential":round(sp,1),"risk":round(r,1)})
                        fp = hashlib.sha256(f"{price}:{reviews}:{rating}:{supplier}".encode()).hexdigest()[:16]
                        tl = "GREEN" if sc>=90 else ("BLUE" if sc>=70 else ("YELLOW" if sc>=50 else "RED"))

                        db._exec(
                            "UPDATE public.products SET opportunity_score=%s, opportunity_confidence=%s, data_quality_score=%s, scoring_version=%s, score_breakdown=%s, score_fingerprint=%s, traffic_light=%s, updated_at=CURRENT_TIMESTAMP WHERE asin=%s",
                            (sc, conf, dq, "v2.4", bd, fp, tl, asin)
                        )
                        _recalc_state["updated"] += 1
                    except Exception as e:
                        _recalc_state["errors"] += 1
            except Exception as e:
                logger.error("Recalc worker error: %s", e)
            finally:
                _recalc_state["running"] = False

        threading.Thread(target=_worker, daemon=True).start()
        return {"status": "started", "message": "Score recalculation running in background"}

    @app.get("/api/admin/recalculate-status")
    async def recalculate_status(admin: dict = Depends(get_admin_user)):
        """Check recalculation progress."""
        try:
            updated = db._exec("SELECT COUNT(*) as cnt FROM public.products WHERE opportunity_score > 0", fetch="one")
            total = db._exec("SELECT COUNT(*) as cnt FROM public.products", fetch="one")
            return {
                "scored": updated["cnt"] if updated else 0,
                "total": total["cnt"] if total else 0,
            }
        except Exception as e:
            return {"error": str(e)}

    # ════════════════════════════════════════════════════════
    # WEBSOCKET
    # ════════════════════════════════════════════════════════

    ws_clients = set()

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await ws.accept()
        ws_clients.add(ws)
        try:
            await ws.send_text(json.dumps({"type": "connected", "data": {"products": len(db.get_all_products_from_db())}}))
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            ws_clients.discard(ws)
        except Exception:
            ws_clients.discard(ws)

    # ════════════════════════════════════════════════════════
    # ADMIN API
    # ════════════════════════════════════════════════════════

    @app.post("/api/admin/auth/login")
    async def admin_login(request: Request):
        body = await request.json()
        user = db._exec("SELECT * FROM admin_users WHERE username = %s AND is_active = TRUE", (body.get("username",""),), "one")
        if not user or not bcrypt.checkpw(body.get("password","").encode(), user["password_hash"].encode()):
            raise HTTPException(401, "Invalid credentials")
        db._exec("UPDATE admin_users SET last_login = CURRENT_TIMESTAMP WHERE id = %s", (user["id"],))
        token = create_admin_token(user["id"], user["username"], user["role"], config.jwt_secret)
        return {"token": token, "admin": {"id": user["id"], "username": user["username"],
                "email": user["email"], "role": user["role"], "display_name": user.get("display_name", "")}}

    @app.get("/api/admin/auth/me")
    async def admin_me(admin: dict = Depends(get_admin_user)):
        a = db._exec("SELECT id, username, email, role, display_name, is_active, last_login, created_at FROM admin_users WHERE id = %s", (admin["admin_id"],), "one")
        if not a: raise HTTPException(404, "Admin not found")
        return a

    @app.get("/api/admin/dashboard")
    async def admin_dashboard(admin: dict = Depends(get_admin_user)):
        return db.admin_dashboard_stats()

    @app.get("/api/admin/users")
    async def admin_list_users(page: int = 1, per_page: int = 25, search: str = "", status: str = "", admin: dict = Depends(get_admin_user)):
        return db.get_all_users(page, per_page, search, status)

    @app.get("/api/admin/users/{user_id}")
    async def admin_user_detail(user_id: int, admin: dict = Depends(get_admin_user)):
        return db.admin_user_detail(user_id)

    @app.post("/api/admin/users/{user_id}/action")
    async def admin_user_action(user_id: int, request: Request, admin: dict = Depends(require_admin_role("super_admin", "admin", "support"))):
        body = await request.json()
        action = body.get("action", "")
        target = db.get_user_by_id(user_id)
        if not target: raise HTTPException(404, "User not found")

        if action == "suspend":
            db.set_user_active(user_id, False)
            db.log_admin_action(admin["admin_id"], admin["username"], user_id, target["username"], "suspend", new_value={"is_active": False}, reason=body.get("reason", ""))
            db.add_notification(user_id, "account", "Account Suspended", "Your account has been suspended by an administrator.", "error")
        elif action == "activate":
            db.set_user_active(user_id, True)
            db.log_admin_action(admin["admin_id"], admin["username"], user_id, target["username"], "activate", new_value={"is_active": True}, reason=body.get("reason", ""))
            db.add_notification(user_id, "account", "Account Activated", "Your account has been reactivated.", "success")
        elif action == "upgrade_plan":
            new_tier = body.get("tier", "pro")
            old_sub = db.get_subscription(user_id)
            old_tier = old_sub["tier"] if old_sub else "free"
            db.change_plan(user_id, new_tier)
            db.log_admin_action(admin["admin_id"], admin["username"], user_id, target["username"], "upgrade_plan",
                              previous_value={"tier": old_tier}, new_value={"tier": new_tier}, reason=body.get("reason", ""))
            db.add_notification(user_id, "subscription", "Plan Upgraded", f"Your plan has been upgraded to {new_tier.upper()}.", "success")
        elif action == "downgrade_plan":
            new_tier = body.get("tier", "free")
            old_sub = db.get_subscription(user_id)
            old_tier = old_sub["tier"] if old_sub else "free"
            db.change_plan(user_id, new_tier)
            db.log_admin_action(admin["admin_id"], admin["username"], user_id, target["username"], "downgrade_plan",
                              previous_value={"tier": old_tier}, new_value={"tier": new_tier}, reason=body.get("reason", ""))
            db.add_notification(user_id, "subscription", "Plan Changed", f"Your plan has been changed to {new_tier.upper()}.", "warning")
        elif action == "add_credits":
            amount = body.get("amount", 0)
            result = db.adjust_credits(user_id, amount, body.get("reason", "Admin adjustment"))
            db.log_admin_action(admin["admin_id"], admin["username"], user_id, target["username"], "add_credits",
                              new_value={"amount": amount, "result": result}, reason=body.get("reason", ""))
            db.add_notification(user_id, "credits", "Credits Added", f"{amount} AI credits have been added to your account.", "success")
        elif action == "remove_credits":
            amount = body.get("amount", 0)
            result = db.adjust_credits(user_id, -amount, body.get("reason", "Admin adjustment"))
            db.log_admin_action(admin["admin_id"], admin["username"], user_id, target["username"], "remove_credits",
                              new_value={"amount": -amount, "result": result}, reason=body.get("reason", ""))
            db.add_notification(user_id, "credits", "Credits Removed", f"{amount} AI credits have been removed from your account.", "warning")
        else:
            raise HTTPException(400, f"Unknown action: {action}")

        return {"status": "ok", "action": action}

    @app.get("/api/admin/plans")
    async def admin_plans(admin: dict = Depends(get_admin_user)):
        return {"plans": db._exec("SELECT * FROM admin_plans ORDER BY price_monthly", (), "all")}

    @app.get("/api/admin/subscriptions")
    async def admin_subscriptions(page: int = 1, per_page: int = 25, status: str = "", admin: dict = Depends(get_admin_user)):
        where, params = [], []
        if status: where.append("bs.status = %s"); params.append(status)
        wc = " AND ".join(where) if where else "1=1"
        total = db._exec(f"SELECT COUNT(*) as c FROM billing_subscriptions bs WHERE {wc}", params, "one")["c"]
        offset = (page - 1) * per_page
        params.extend([per_page, offset])
        subs = db._exec(f"""
            SELECT bs.*, u.username, u.email, ap.name as plan_name, ap.slug as plan_slug
            FROM billing_subscriptions bs
            LEFT JOIN users u ON bs.user_id = u.id
            LEFT JOIN admin_plans ap ON bs.plan_id = ap.id
            WHERE {wc}
            ORDER BY bs.created_at DESC LIMIT %s OFFSET %s
        """, tuple(params), "all")
        return {"subscriptions": subs, "total": total, "page": page, "per_page": per_page}

    @app.get("/api/admin/products")
    async def admin_products(page: int = 1, per_page: int = 25, search: str = "", admin: dict = Depends(get_admin_user)):
        where, params = [], []
        if search: where.append("(asin ILIKE %s OR name ILIKE %s)"); params.extend([f"%{search}%", f"%{search}%"])
        wc = " AND ".join(where) if where else "1=1"
        total = db._exec(f"SELECT COUNT(*) as c FROM products WHERE {wc}", params, "one")["c"]
        offset = (page - 1) * per_page
        params.extend([per_page, offset])
        products = db._exec(f"SELECT id, asin, name, category, amazon_price, rating, review_count, ai_score, traffic_light, created_at FROM products WHERE {wc} ORDER BY created_at DESC LIMIT %s OFFSET %s", tuple(params), "all")
        return {"products": products, "total": total, "page": page, "per_page": per_page}

    @app.get("/api/admin/research")
    async def admin_research(page: int = 1, per_page: int = 25, status: str = "", admin: dict = Depends(get_admin_user)):
        return db.admin_get_all_research(page, per_page, status)

    @app.get("/api/admin/watchlist")
    async def admin_watchlist(page: int = 1, per_page: int = 25, admin: dict = Depends(get_admin_user)):
        return db.admin_get_all_watchlists(page, per_page)

    @app.get("/api/admin/features")
    async def admin_features(admin: dict = Depends(get_admin_user)):
        return {"features": db._exec("SELECT * FROM admin_feature_flags ORDER BY flag_name", fetch="all")}

    @app.post("/api/admin/features")
    async def admin_create_feature(request: Request, admin: dict = Depends(require_admin_role("super_admin"))):
        body = await request.json()
        fid = db._exec("INSERT INTO admin_feature_flags (flag_name, description, is_enabled, scope, rollout_percentage, created_by) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
                       (body.get("flag_name",""), body.get("description",""), body.get("is_enabled",False), body.get("scope","global"), body.get("rollout_percentage",100), admin["admin_id"]), "one")
        return {"id": fid["id"]}

    @app.post("/api/admin/features/{flag_id}/toggle")
    async def admin_toggle_feature(flag_id: int, admin: dict = Depends(require_admin_role("super_admin"))):
        f = db._exec("SELECT is_enabled FROM admin_feature_flags WHERE id = %s", (flag_id,), "one")
        if not f: raise HTTPException(404, "Not found")
        db._exec("UPDATE admin_feature_flags SET is_enabled=%s WHERE id=%s", (not f["is_enabled"], flag_id))
        return {"is_enabled": not f["is_enabled"]}

    @app.get("/api/admin/audit")
    async def admin_audit(page: int = 1, per_page: int = 25, admin: dict = Depends(get_admin_user)):
        return db.get_admin_actions(page, per_page)

    @app.get("/api/admin/jobs")
    async def admin_jobs(page: int = 1, per_page: int = 25, status: str = "", admin: dict = Depends(get_admin_user)):
        where, params = [], []
        if status: where.append("status = %s"); params.append(status)
        wc = " AND ".join(where) if where else "1=1"
        total = db._exec(f"SELECT COUNT(*) as c FROM research_jobs WHERE {wc}", params, "one")["c"]
        offset = (page - 1) * per_page
        params.extend([per_page, offset])
        jobs = db._exec(f"SELECT r.*, u.username FROM research_jobs r LEFT JOIN users u ON r.user_id = u.id WHERE {wc} ORDER BY r.created_at DESC LIMIT %s OFFSET %s", tuple(params), "all")
        return {"jobs": jobs, "total": total, "page": page, "per_page": per_page}

    @app.get("/api/admin/health")
    async def admin_health(admin: dict = Depends(get_admin_user)):
        import psutil
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        db_status = "connected"
        try: db._exec("SELECT 1", fetch="one")
        except Exception: db_status = "error"
        return {"cpu": cpu, "memory": {"total": mem.total, "used": mem.used, "percent": mem.percent},
                "disk": {"total": disk.total, "used": disk.used, "percent": disk.percent},
                "database": db_status, "timestamp": datetime.now().isoformat()}

    @app.get("/api/admin/settings")
    async def admin_settings(admin: dict = Depends(get_admin_user)):
        return {"settings": db._exec("SELECT * FROM admin_system_settings ORDER BY setting_type, setting_key", fetch="all")}

    @app.put("/api/admin/settings/{key}")
    async def admin_update_setting(key: str, request: Request, admin: dict = Depends(require_admin_role("super_admin"))):
        body = await request.json()
        db._exec("UPDATE admin_system_settings SET setting_value=%s, updated_at=CURRENT_TIMESTAMP WHERE setting_key=%s", (json.dumps(body.get("setting_value")), key))
        return {"message": "Updated"}

    @app.get("/api/admin/notifications")
    async def admin_notifications(admin: dict = Depends(get_admin_user)):
        return {"notifications": db._exec("SELECT * FROM admin_notifications WHERE admin_id=%s ORDER BY created_at DESC LIMIT 50", (admin["admin_id"],), "all")}

    @app.get("/api/admin/support")
    async def admin_support(page: int = 1, per_page: int = 25, admin: dict = Depends(get_admin_user)):
        total = db._exec("SELECT COUNT(*) as c FROM admin_support_tickets", (), "one")["c"]
        offset = (page - 1) * per_page
        tickets = db._exec("SELECT t.*, u.username FROM admin_support_tickets t LEFT JOIN users u ON t.user_id = u.id ORDER BY t.created_at DESC LIMIT %s OFFSET %s", (per_page, offset), "all")
        return {"tickets": tickets, "total": total, "page": page, "per_page": per_page}

    @app.get("/api/admin/backups")
    async def admin_backups(admin: dict = Depends(require_admin_role("super_admin"))):
        return {"backups": db._exec("SELECT * FROM admin_backups ORDER BY created_at DESC LIMIT 20", fetch="all")}

    # ════════════════════════════════════════════════════════
    # BILLING ROUTES (Stripe Integration)
    # ════════════════════════════════════════════════════════

    setup_billing_user_routes(app, get_current_user)
    setup_billing_webhook_route(app)
    setup_billing_admin_routes(app, get_admin_user, require_admin_role)

    # ════════════════════════════════════════════════════════
    # SEED ADMIN ON STARTUP
    # ════════════════════════════════════════════════════════

    @app.on_event("startup")
    async def seed_admin():
        try:
            admin_pw = os.environ.get("ADMIN_PASSWORD", "admin123")
            pw_hash = bcrypt.hashpw(admin_pw.encode(), bcrypt.gensalt()).decode()
            db._exec(
                """INSERT INTO admin_users (username, email, password_hash, role, display_name)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (username) DO UPDATE SET password_hash = EXCLUDED.password_hash, updated_at = CURRENT_TIMESTAMP""",
                ("admin", "admin@marketlens.com", pw_hash, "super_admin", "Super Admin")
            )
            logger.info("Admin user seeded")
        except Exception as e:
            logger.error("Admin seed failed: %s", e)

    # ════════════════════════════════════════════════════════
    # FRONTEND
    # ════════════════════════════════════════════════════════

    _web_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
    _index_html = os.path.join(_web_dir, "index.html")
    _admin_html = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "admin_backend", "admin", "index.html")

    @app.get("/", response_class=HTMLResponse)
    async def serve_frontend():
        try:
            with open(_index_html, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        except FileNotFoundError:
            return HTMLResponse(content="<h1>Frontend not found</h1>", status_code=404)

    @app.get("/admin", response_class=HTMLResponse)
    @app.get("/admin/", response_class=HTMLResponse)
    async def serve_admin():
        try:
            with open(_admin_html, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        except FileNotFoundError:
            return HTMLResponse(content="<h1>Admin not found</h1>", status_code=404)

    if os.path.isdir(os.path.join(_web_dir, "static")):
        app.mount("/static", StaticFiles(directory=os.path.join(_web_dir, "static")), name="static")

    # ════════════════════════════════════════════════════════
    # SHUTDOWN
    # ════════════════════════════════════════════════════════

    @app.on_event("shutdown")
    async def shutdown():
        pass

    return app


if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO)
    app = create_app()
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
