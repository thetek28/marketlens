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

    app = FastAPI(title="MarketLens Cloud", version="4.0.0")

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
        products = db.get_all_products_from_db()
        p = next((x for x in products if x.get("asin") == asin), None)
        if not p: raise HTTPException(404, "Product not found")
        return p

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
                    chars = string.ascii_uppercase + string.digits
                    for sp in SAMPLE_PRODUCTS:
                        if not _analysis_state["running"]: break
                        asin = "B0" + "".join(random.choices(chars, k=8))
                        try:
                            db._exec(
                                """INSERT INTO products (asin, name, category, amazon_price, rating, review_count, ai_score, estimated_margin_pct, traffic_light)
                                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (asin) DO NOTHING""",
                                (asin, sp["name"], sp["category"], sp["price"], sp["rating"], sp["reviews"], sp["ai"]/100.0, sp["margin"], sp["tl"])
                            )
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
        return {"plans": db._exec("SELECT * FROM admin_plans ORDER BY price_monthly", fetch="all")}

    @app.get("/api/admin/subscriptions")
    async def admin_subscriptions(page: int = 1, per_page: int = 25, status: str = "", admin: dict = Depends(get_admin_user)):
        where, params = [], []
        if status: where.append("s.is_active = %s"); params.append(1 if status == "active" else 0)
        wc = " AND ".join(where) if where else "1=1"
        total = db._exec(f"SELECT COUNT(*) as c FROM subscriptions s WHERE {wc}", params, "one")["c"]
        offset = (page - 1) * per_page
        params.extend([per_page, offset])
        subs = db._exec(f"""
            SELECT s.*, u.username, u.email FROM subscriptions s
            LEFT JOIN users u ON s.user_id = u.id WHERE {wc}
            ORDER BY s.created_at DESC LIMIT %s OFFSET %s
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
