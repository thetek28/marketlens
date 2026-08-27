"""MarketLens Cloud Backend - FastAPI application for online deployment.

Uses PostgreSQL via online_db module instead of SQLite.
Supports concurrent multi-user access with connection pooling.
"""

import asyncio
import json
import logging
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
import psycopg2
import psycopg2.extras
from fastapi import FastAPI, HTTPException, Request, Depends, status, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from online_db import OnlineDatabaseManager
from online_db.config import DatabaseConfig
from online_backend.config import BackendConfig

logger = logging.getLogger(__name__)


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

class ConfigUpdate(BaseModel):
    categories: list = []
    keywords: list = []
    config: dict = {}


# ════════════════════════════════════════════════════════════
# JWT HELPERS
# ════════════════════════════════════════════════════════════

import hmac

def create_token(username: str, secret: str, expires_hours: int = 24) -> str:
    """Create a simple JWT token."""
    import base64
    payload = {
        "sub": username,
        "exp": (datetime.utcnow() + timedelta(hours=expires_hours)).isoformat(),
        "iat": datetime.utcnow().isoformat(),
    }
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode().rstrip("=")
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig_input = f"{header}.{body}".encode()
    signature = hmac.new(secret.encode(), sig_input, "sha256").digest()
    sig = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    return f"{header}.{body}.{sig}"

def decode_token(token: str, secret: str) -> Optional[dict]:
    """Decode and verify a JWT token."""
    import base64
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header, body, sig = parts
        sig_input = f"{header}.{body}".encode()
        expected = hmac.new(secret.encode(), sig_input, "sha256").digest()
        actual = base64.urlsafe_b64decode(sig + "==")
        if not hmac.compare_digest(expected, actual):
            return None
        padding = 4 - len(body) % 4
        body += "=" * padding
        payload = json.loads(base64.urlsafe_b64decode(body))
        if datetime.fromisoformat(payload.get("exp", "2000-01-01")) < datetime.utcnow():
            return None
        return payload
    except Exception:
        return None


# ════════════════════════════════════════════════════════════
# APP FACTORY
# ════════════════════════════════════════════════════════════

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    config = BackendConfig()
    db = OnlineDatabaseManager(DatabaseConfig())

    app = FastAPI(title="MarketLens Cloud", version=config.version)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins + ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ════════════════════════════════════════════════════════
    # AUTH DEPENDENCY
    # ════════════════════════════════════════════════════════

    async def get_current_user(request: Request) -> str:
        token = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        if not token:
            token = request.cookies.get("mjl_token")
        if not token:
            raise HTTPException(status_code=401, detail="Not authenticated")
        payload = decode_token(token, config.jwt_secret)
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return payload["sub"]

    # ════════════════════════════════════════════════════════
    # HEALTH
    # ════════════════════════════════════════════════════════

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "version": config.version, "database": "postgresql"}

    # ════════════════════════════════════════════════════════
    # AUTH ENDPOINTS
    # ════════════════════════════════════════════════════════

    @app.post("/api/auth/register")
    async def register(req: RegisterRequest):
        if len(req.username) < 3 or len(req.password) < 6:
            raise HTTPException(400, "Username min 3, password min 6 chars")
        existing = db.get_user(req.username)
        if existing:
            raise HTTPException(400, "Username already taken")
        password_hash = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode()
        user_id = db.create_user(req.username, password_hash, req.email)
        if not user_id:
            raise HTTPException(500, "Failed to create user")
        db.create_subscription(user_id, "free", 30)
        token = create_token(req.username, config.jwt_secret, config.jwt_expiry_hours)
        return {"token": token, "user": {"id": user_id, "username": req.username}, "subscription": {"tier": "free"}}

    @app.post("/api/auth/login")
    async def login(req: LoginRequest, response_class=None):
        user = db.get_user(req.username)
        if not user or not bcrypt.checkpw(req.password.encode(), user["password_hash"].encode()):
            raise HTTPException(401, "Invalid credentials")
        token = create_token(req.username, config.jwt_secret, config.jwt_expiry_hours)
        sub = db.get_subscription(user["id"])
        return {"token": token, "user": {"id": user["id"], "username": user["username"]}, "subscription": sub or {"tier": "free"}}

    @app.get("/api/auth/me")
    async def get_me(user: str = Depends(get_current_user)):
        u = db.get_user(user)
        if not u:
            raise HTTPException(404, "User not found")
        sub = db.get_subscription(u["id"])
        return {"id": u["id"], "username": u["username"], "email": u["email"], "subscription": sub or {"tier": "free"}}

    # ════════════════════════════════════════════════════════
    # PRODUCTS
    # ════════════════════════════════════════════════════════

    @app.get("/api/products/all")
    async def get_products_all(user: str = Depends(get_current_user)):
        return {"products": db.get_all_products_from_db()}

    @app.get("/api/products/top20")
    async def get_products_top20(user: str = Depends(get_current_user)):
        products = db.get_all_products_from_db()[:20]
        return {"products": products}

    @app.get("/api/products")
    async def get_products(page: int = 1, per_page: int = 20, user: str = Depends(get_current_user)):
        all_products = db.get_all_products_from_db()
        start = (page - 1) * per_page
        return {"products": all_products[start:start+per_page], "total": len(all_products), "page": page}

    @app.get("/api/products/{asin}")
    async def get_product(asin: str, user: str = Depends(get_current_user)):
        products = db.get_all_products_from_db()
        p = next((x for x in products if x.get("asin") == asin), None)
        if not p:
            raise HTTPException(404, "Product not found")
        return p

    # ════════════════════════════════════════════════════════
    # SUPPLIERS
    # ════════════════════════════════════════════════════════

    @app.get("/api/suppliers")
    async def get_suppliers(user: str = Depends(get_current_user)):
        return {"suppliers": db.get_all_suppliers()}

    @app.post("/api/suppliers")
    async def add_supplier(request: Request, user: str = Depends(get_current_user)):
        body = await request.json()
        sid = db.add_supplier(body)
        return {"id": sid, "message": "Supplier added"}

    @app.delete("/api/suppliers/{supplier_id}")
    async def delete_supplier(supplier_id: int, user: str = Depends(get_current_user)):
        db.delete_supplier(supplier_id)
        return {"message": "Supplier deleted"}

    # ════════════════════════════════════════════════════════
    # LISTING VERSIONS
    # ════════════════════════════════════════════════════════

    @app.get("/api/listing/{asin}")
    async def get_listing(asin: str, user: str = Depends(get_current_user)):
        products = db.get_all_products_from_db()
        p = next((x for x in products if x.get("asin") == asin), None)
        if not p:
            raise HTTPException(404, "Product not found")

        name = p.get("name", "")
        category = p.get("category", "")
        core_kw = [w.lower() for w in name.split() if len(w) > 2][:10]
        title = f"{core_kw[0].title() if core_kw else ''} {name} - Premium {category}"
        bullets = [
            f"Premium {name} designed for everyday use",
            f"Premium materials ensure long-lasting durability",
            f"Perfect for {category} enthusiasts of all levels",
            f"Compact and lightweight design for easy portability",
            f"100% satisfaction guaranteed with full refund policy"
        ]
        description = f"Introducing our premium {name}, crafted with the highest quality materials for exceptional performance in {category}."
        seo_score = min(100, 50 + len(core_kw) * 5 + (15 if len(title) > 50 else 0))

        return {
            "asin": asin, "name": name, "category": category,
            "brand": p.get("brand", ""), "price": p.get("amazon_price", 0),
            "rating": p.get("rating", 0), "reviews": p.get("review_count", 0),
            "title": title, "bullets": bullets, "description": description,
            "search_terms": " ".join(core_kw[:5]),
            "backend_keywords": " ".join(core_kw),
            "seo_score": seo_score,
        }

    @app.post("/api/listing/{asin}/save")
    async def save_listing(asin: str, request: Request, user: str = Depends(get_current_user)):
        body = await request.json()
        u = db.get_user(user)
        user_id = u["id"] if u else 0
        version_id = db.save_listing_version(asin, user_id, body)
        return {"id": version_id, "message": "Listing saved"}

    @app.get("/api/listing/{asin}/versions")
    async def get_listing_versions(asin: str, user: str = Depends(get_current_user)):
        return {"versions": db.get_listing_versions(asin)}

    # ════════════════════════════════════════════════════════
    # DATABASE STATS
    # ════════════════════════════════════════════════════════

    @app.get("/api/database/stats")
    async def db_stats(user: str = Depends(get_current_user)):
        return db.get_stats()

    # ════════════════════════════════════════════════════════
    # PRICE HISTORY
    # ════════════════════════════════════════════════════════

    @app.get("/api/price-history/{asin}")
    async def price_history(asin: str, user: str = Depends(get_current_user)):
        return {"history": db.get_price_history(asin)}

    @app.post("/api/price-history/{asin}/record")
    async def record_price(asin: str, request: Request, user: str = Depends(get_current_user)):
        body = await request.json()
        db.record_price(asin, body.get("product_name", ""), body.get("source", "manual"),
                        body.get("price", 0), body.get("old_price", 0))
        return {"message": "Price recorded"}

    # ════════════════════════════════════════════════════════
    # INVENTORY
    # ════════════════════════════════════════════════════════

    @app.get("/api/inventory/{asin}")
    async def get_inventory(asin: str, user: str = Depends(get_current_user)):
        inv = db.get_inventory(asin)
        return {"inventory": inv[0] if inv else None}

    @app.post("/api/inventory/{asin}")
    async def save_inventory(asin: str, request: Request, user: str = Depends(get_current_user)):
        body = await request.json()
        db.save_inventory(asin, body.get("product_name", ""), body)
        return {"message": "Inventory saved"}

    # ════════════════════════════════════════════════════════
    # NOTES & TEAM
    # ════════════════════════════════════════════════════════

    @app.get("/api/notes/{asin}")
    async def get_notes(asin: str, user: str = Depends(get_current_user)):
        return {"notes": db.get_comments(asin)}

    @app.post("/api/notes/{asin}")
    async def save_notes(asin: str, request: Request, user: str = Depends(get_current_user)):
        body = await request.json()
        db.add_comment(asin, user, body.get("comment", ""), body.get("type", "note"))
        return {"message": "Note saved"}

    @app.get("/api/team/tasks/{asin}")
    async def get_tasks(asin: str, user: str = Depends(get_current_user)):
        return {"tasks": db.get_tasks(asin)}

    @app.post("/api/team/tasks/{asin}")
    async def add_task(asin: str, request: Request, user: str = Depends(get_current_user)):
        body = await request.json()
        db.add_task(asin, body.get("product_name", ""), body.get("task", ""),
                    body.get("assignee", "Unassigned"), body.get("priority", "medium"))
        return {"message": "Task added"}

    @app.post("/api/team/tasks/{task_id}/toggle")
    async def toggle_task(task_id: int, user: str = Depends(get_current_user)):
        done = db.toggle_task(task_id)
        return {"status": "done" if done else "todo"}

    # ════════════════════════════════════════════════════════
    # CONFIG
    # ════════════════════════════════════════════════════════

    @app.get("/api/config")
    async def get_config(user: str = Depends(get_current_user)):
        return {"categories": [], "keywords": [], "config": {}}

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
    # ANALYSIS - uses CollectionService sample catalog
    # ════════════════════════════════════════════════════════

    import threading
    import random
    import sys
    import string
    import time

    _analysis_state = {"running": False, "cycle": 0, "products": [], "ws_clients": ws_clients}

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
        {"name": "JBL Tune 510BT Headphones", "category": "Electronics", "price": 24.95, "rating": 4.5, "reviews": 34000, "ai": 81, "margin": 28, "tl": "GREEN"},
        {"name": "Philips Sonicare Toothbrush", "category": "Health", "price": 34.99, "rating": 4.6, "reviews": 29000, "ai": 85, "margin": 35, "tl": "GREEN"},
        {"name": "Ring Video Doorbell", "category": "Electronics", "price": 59.99, "rating": 4.4, "reviews": 42000, "ai": 82, "margin": 20, "tl": "YELLOW"},
        {"name": "Hydro Flask Water Bottle 32oz", "category": "Sports", "price": 44.95, "rating": 4.7, "reviews": 26000, "ai": 89, "margin": 38, "tl": "GREEN"},
        {"name": "Crock-Pot 7Qt Slow Cooker", "category": "Kitchen", "price": 39.99, "rating": 4.5, "reviews": 55000, "ai": 86, "margin": 33, "tl": "GREEN"},
    ]

    async def _broadcast(event_type: str, data=None):
        msg = json.dumps({"type": event_type, "data": data, "timestamp": datetime.now().isoformat()})
        clients = _analysis_state["ws_clients"]
        dead = set()
        for ws in clients:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.add(ws)
        clients -= dead

    def _analysis_worker():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            while _analysis_state["running"]:
                _analysis_state["cycle"] += 1
                cycle = _analysis_state["cycle"]
                loop.run_until_complete(_broadcast("status", {"message": f"Cycle {cycle}: Generating products..."}))

                import string
                inserted = 0
                for sp in SAMPLE_PRODUCTS:
                    if not _analysis_state["running"]:
                        break
                    chars = string.ascii_uppercase + string.digits
                    asin = "B0" + "".join(random.choices(chars, k=8))
                    try:
                        db._execute(
                            """INSERT INTO products (asin, name, category, amazon_price, rating, review_count, ai_score, estimated_margin_pct, traffic_light)
                               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                               ON CONFLICT (asin) DO NOTHING""",
                            (asin, sp["name"], sp["category"], sp["price"], sp["rating"], sp["reviews"], sp["ai"]/100.0, sp["margin"], sp["tl"])
                        )
                        inserted += 1
                    except Exception as e:
                        logger.error("Insert failed: %s", e)

                loop.run_until_complete(_broadcast("status", {"message": f"Cycle {cycle}: {inserted} new products"}))
                total = len(db.get_all_products_from_db())
                loop.run_until_complete(_broadcast("cycle_complete", {"cycle": cycle, "products": total, "hidden_gems": 0}))
                loop.run_until_complete(_broadcast("status", {"message": f"Cycle {cycle} complete: {total} total products"}))

                for _ in range(60):
                    if not _analysis_state["running"]:
                        break
                    time.sleep(1)

            loop.run_until_complete(_broadcast("analysis_complete", {"total": len(db.get_all_products_from_db())}))
        except Exception as e:
            logger.error("Analysis worker error: %s", e)
            loop.run_until_complete(_broadcast("status", {"message": f"Error: {e}"}))
        finally:
            _analysis_state["running"] = False

    @app.get("/api/analysis/status")
    async def analysis_status(user: str = Depends(get_current_user)):
        return {"running": _analysis_state["running"], "cycle": _analysis_state["cycle"],
                "total_products": len(db.get_all_products_from_db()), "hidden_gems": 0,
                "seen_asins": 0, "elapsed_seconds": 0,
                "categories": ["Kitchen", "Electronics", "Beauty"], "keywords": ["trending"]}

    @app.post("/api/analysis/start")
    async def analysis_start(user: str = Depends(get_current_user)):
        if _analysis_state["running"]:
            raise HTTPException(400, "Already running")
        _analysis_state["running"] = True
        t = threading.Thread(target=_analysis_worker, daemon=True)
        t.start()
        return {"status": "started"}

    @app.post("/api/analysis/stop")
    async def analysis_stop(user: str = Depends(get_current_user)):
        _analysis_state["running"] = False
        return {"status": "stopped"}

    @app.post("/api/analysis/cycle")
    async def analysis_cycle(user: str = Depends(get_current_user)):
        return {"status": "ok", "products": len(db.get_all_products_from_db())}

    @app.post("/api/analysis/collect")
    async def analysis_collect(user: str = Depends(get_current_user)):
        return {"status": "ok", "products": 0}

    # ════════════════════════════════════════════════════════
    # STATUS & CHARTS (frontend expects these)
    # ════════════════════════════════════════════════════════

    _categories = ["Kitchen", "Electronics", "Beauty", "Home & Kitchen", "Sports", "Health"]
    _keywords = ["trending", "best seller", "new arrival", "hot", "popular"]

    @app.get("/api/status")
    async def get_status(user: str = Depends(get_current_user)):
        return {"running": _analysis_state["running"], "cycle": _analysis_state["cycle"],
                "total_products": len(db.get_all_products_from_db()), "hidden_gems": 0,
                "seen_asins": 0, "elapsed_seconds": 0,
                "categories": _categories, "keywords": _keywords}

    @app.get("/api/charts/data")
    async def get_charts_data(user: str = Depends(get_current_user)):
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
        price_dist = {"under_20": 0, "20_50": 0, "50_100": 0, "over_100": 0}
        for p in products:
            pr = p.get("amazon_price", 0)
            if pr < 20: price_dist["under_20"] += 1
            elif pr < 50: price_dist["20_50"] += 1
            elif pr < 100: price_dist["50_100"] += 1
            else: price_dist["over_100"] += 1
        traffic = {"GREEN": 0, "YELLOW": 0, "RED": 0}
        for p in products: traffic[p.get("traffic_light", "RED")] = traffic.get(p.get("traffic_light", "RED"), 0) + 1
        return {"categories": categories, "price_distribution": price_dist, "traffic_lights": traffic, "ai_distribution": {"low":0,"medium":0,"high":0,"very_high":0}, "total": len(products)}

    @app.post("/api/categories")
    async def update_categories(request: Request, user: str = Depends(get_current_user)):
        body = await request.json()
        global _categories
        _categories = body.get("categories", _categories)
        return {"categories": _categories}

    @app.post("/api/keywords")
    async def update_keywords(request: Request, user: str = Depends(get_current_user)):
        body = await request.json()
        global _keywords
        _keywords = body.get("keywords", _keywords)
        return {"keywords": _keywords}

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
            return HTMLResponse(content="<h1>Admin frontend not found</h1>", status_code=404)

    if os.path.isdir(os.path.join(_web_dir, "static")):
        app.mount("/static", StaticFiles(directory=os.path.join(_web_dir, "static")), name="static")

    # ════════════════════════════════════════════════════════
    # ADMIN API (inline)
    # ════════════════════════════════════════════════════════

    import hmac as _hmac
    import base64 as _base64

    ADMIN_JWT_SECRET = os.environ.get("MLENS_JWT_SECRET", config.jwt_secret)

    def create_admin_token(admin_id, username, role):
        payload = {"sub": username, "admin_id": admin_id, "role": role,
                    "exp": (datetime.utcnow() + timedelta(hours=12)).isoformat(),
                    "iat": datetime.utcnow().isoformat(), "is_admin": True}
        header = _base64.urlsafe_b64encode(json.dumps({"alg":"HS256","typ":"JWT"}).encode()).decode().rstrip("=")
        body = _base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        sig = _base64.urlsafe_b64encode(_hmac.new(ADMIN_JWT_SECRET.encode(), f"{header}.{body}".encode(), "sha256").digest()).decode().rstrip("=")
        return f"{header}.{body}.{sig}"

    def decode_admin_token(token):
        try:
            parts = token.split(".")
            if len(parts) != 3: return None
            header, body, sig = parts
            expected = _hmac.new(ADMIN_JWT_SECRET.encode(), f"{header}.{body}".encode(), "sha256").digest()
            actual = _base64.urlsafe_b64decode(sig + "==")
            if not _hmac.compare_digest(expected, actual): return None
            body_padded = body + "=" * (4 - len(body) % 4)
            payload = json.loads(_base64.urlsafe_b64decode(body_padded))
            if datetime.fromisoformat(payload.get("exp", "2000-01-01")) < datetime.utcnow(): return None
            if not payload.get("is_admin"): return None
            return payload
        except Exception:
            return None

    _admin_db_url = os.environ.get("DATABASE_URL", config.database_url)

    def admin_db_exec(query, params=(), fetch="none"):
        conn = psycopg2.connect(_admin_db_url, sslmode="require")
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, params)
                if fetch == "one":
                    row = cur.fetchone(); conn.commit(); return dict(row) if row else None
                elif fetch == "all":
                    rows = cur.fetchall(); conn.commit(); return [dict(r) for r in rows]
                else:
                    conn.commit(); return cur.rowcount
        except Exception:
            conn.rollback(); raise
        finally:
            conn.close()

    async def get_admin_user(request: Request):
        token = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "): token = auth_header[7:]
        if not token: token = request.cookies.get("mjl_admin_token")
        if not token: raise HTTPException(401, "Not authenticated")
        payload = decode_admin_token(token)
        if not payload: raise HTTPException(401, "Invalid or expired token")
        return payload

    def require_admin_role(*roles):
        async def checker(admin: dict = Depends(get_admin_user)):
            if admin.get("role") not in roles and admin.get("role") != "super_admin":
                raise HTTPException(403, "Insufficient permissions")
            return admin
        return checker

    # Admin Auth
    @app.post("/api/admin/auth/login")
    async def admin_login(request: Request):
        body = await request.json()
        username = body.get("username", "")
        password = body.get("password", "")
        admin = admin_db_exec("SELECT * FROM admin_users WHERE username = %s AND is_active = TRUE", (username,), "one")
        if not admin or not bcrypt.checkpw(password.encode(), admin["password_hash"].encode()):
            raise HTTPException(401, "Invalid credentials")
        admin_db_exec("UPDATE admin_users SET last_login = CURRENT_TIMESTAMP WHERE id = %s", (admin["id"],))
        token = create_admin_token(admin["id"], admin["username"], admin["role"])
        return {"token": token, "admin": {"id": admin["id"], "username": admin["username"],
                "email": admin["email"], "role": admin["role"], "display_name": admin["display_name"]}}

    @app.get("/api/admin/auth/me")
    async def admin_me(admin: dict = Depends(get_admin_user)):
        a = admin_db_exec("SELECT id, username, email, role, display_name, is_active, last_login, created_at FROM admin_users WHERE id = %s", (admin["admin_id"],), "one")
        if not a: raise HTTPException(404, "Admin not found")
        return a

    @app.post("/api/admin/auth/logout")
    async def admin_logout(admin: dict = Depends(get_admin_user)):
        return {"status": "ok"}

    # Admin Dashboard
    @app.get("/api/admin/dashboard")
    async def admin_dashboard(admin: dict = Depends(get_admin_user)):
        users = admin_db_exec("SELECT COUNT(*) as total FROM users", fetch="one")
        active_users = admin_db_exec("SELECT COUNT(*) as total FROM users WHERE is_active = 1", fetch="one")
        products = admin_db_exec("SELECT COUNT(*) as total FROM products", fetch="one")
        subscriptions = admin_db_exec("SELECT COUNT(*) as total FROM admin_subscriptions WHERE status = 'active'", fetch="one")
        jobs_running = admin_db_exec("SELECT COUNT(*) as total FROM admin_jobs WHERE status = 'running'", fetch="one")
        jobs_total = admin_db_exec("SELECT COUNT(*) as total FROM admin_jobs", fetch="one")
        revenue = admin_db_exec("""SELECT COALESCE(SUM(CASE WHEN s.billing_cycle='monthly' THEN p.price_monthly
            WHEN s.billing_cycle='yearly' THEN p.price_yearly/12 ELSE 0 END), 0) as mrr
            FROM admin_subscriptions s JOIN admin_plans p ON s.plan_id = p.id WHERE s.status = 'active'""", fetch="one")
        credits = admin_db_exec("""SELECT COALESCE(SUM(ai_credits_used), 0) as total_used,
            COALESCE(SUM(ai_credits_limit), 0) as total_limit FROM admin_subscriptions WHERE status = 'active'""", fetch="one")
        recent_jobs = admin_db_exec("SELECT id, job_type, status, created_at, duration_ms FROM admin_jobs ORDER BY created_at DESC LIMIT 5", fetch="all")
        return {"users": {"total": users["total"], "active": active_users["total"]},
                "products": {"total": products["total"]},
                "subscriptions": {"total": subscriptions["total"]},
                "revenue": {"mrr": revenue["mrr"]},
                "credits": {"used": credits["total_used"], "limit": credits["total_limit"]},
                "jobs": {"running": jobs_running["total"], "total": jobs_total["total"]},
                "recent_jobs": recent_jobs}

    # Admin Users
    @app.get("/api/admin/users")
    async def admin_list_users(page: int = 1, per_page: int = 25, search: str = "", status: str = "", admin: dict = Depends(get_admin_user)):
        where, params = [], []
        if search:
            where.append("(u.username ILIKE %s OR u.email ILIKE %s)")
            params.extend([f"%{search}%", f"%{search}%"])
        if status:
            where.append("u.is_active = %s")
            params.append(1 if status == "active" else 0)
        where_clause = " AND ".join(where) if where else "1=1"
        total = admin_db_exec(f"SELECT COUNT(*) as total FROM users u WHERE {where_clause}", params, "one")["total"]
        offset = (page - 1) * per_page
        params.extend([per_page, offset])
        users = admin_db_exec(f"""SELECT u.id, u.username, u.email, u.is_active, u.created_at,
            s.status as sub_status, s.ai_credits_used, s.ai_credits_limit, p.name as plan_name
            FROM users u LEFT JOIN admin_subscriptions s ON u.id = s.user_id AND s.status = 'active'
            LEFT JOIN admin_plans p ON s.plan_id = p.id WHERE {where_clause}
            ORDER BY u.id DESC LIMIT %s OFFSET %s""", params, "all")
        return {"users": users, "total": total, "page": page, "per_page": per_page}

    @app.post("/api/admin/users/{user_id}/action")
    async def admin_user_action(user_id: int, request: Request, admin: dict = Depends(require_admin_role("super_admin", "admin", "support"))):
        body = await request.json()
        action = body.get("action", "")
        if action == "suspend":
            admin_db_exec("UPDATE users SET is_active = 0 WHERE id = %s", (user_id,))
        elif action == "activate":
            admin_db_exec("UPDATE users SET is_active = 1 WHERE id = %s", (user_id,))
        else:
            raise HTTPException(400, f"Unknown action: {action}")
        return {"status": "ok", "action": action}

    # Admin Plans
    @app.get("/api/admin/plans")
    async def admin_list_plans(admin: dict = Depends(get_admin_user)):
        return {"plans": admin_db_exec("SELECT * FROM admin_plans ORDER BY price_monthly", fetch="all")}

    @app.post("/api/admin/plans")
    async def admin_create_plan(request: Request, admin: dict = Depends(require_admin_role("super_admin"))):
        body = await request.json()
        plan_id = admin_db_exec("""INSERT INTO admin_plans (name, slug, price_monthly, price_yearly, currency, ai_credits_monthly,
            research_limit, tracking_limit, team_members) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (body.get("name",""), body.get("slug",""), body.get("price_monthly",0), body.get("price_yearly",0),
             body.get("currency","USD"), body.get("ai_credits_monthly",50), body.get("research_limit",10),
             body.get("tracking_limit",5), body.get("team_members",1)), "one")
        return {"id": plan_id["id"]}

    @app.put("/api/admin/plans/{plan_id}")
    async def admin_update_plan(plan_id: int, request: Request, admin: dict = Depends(require_admin_role("super_admin"))):
        body = await request.json()
        admin_db_exec("""UPDATE admin_plans SET name=%s, slug=%s, price_monthly=%s, price_yearly=%s,
            ai_credits_monthly=%s, research_limit=%s, tracking_limit=%s, team_members=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s""",
            (body.get("name",""), body.get("slug",""), body.get("price_monthly",0), body.get("price_yearly",0),
             body.get("ai_credits_monthly",50), body.get("research_limit",10), body.get("tracking_limit",5),
             body.get("team_members",1), plan_id))
        return {"message": "Plan updated"}

    # Admin Subscriptions
    @app.get("/api/admin/subscriptions")
    async def admin_list_subs(page: int = 1, per_page: int = 25, status: str = "", admin: dict = Depends(get_admin_user)):
        where, params = [], []
        if status:
            where.append("s.status = %s"); params.append(status)
        where_clause = " AND ".join(where) if where else "1=1"
        total = admin_db_exec(f"SELECT COUNT(*) as total FROM admin_subscriptions s WHERE {where_clause}", params, "one")["total"]
        offset = (page - 1) * per_page
        params.extend([per_page, offset])
        subs = admin_db_exec(f"""SELECT s.*, p.name as plan_name, p.price_monthly, p.price_yearly, u.username, u.email
            FROM admin_subscriptions s JOIN admin_plans p ON s.plan_id = p.id
            LEFT JOIN users u ON s.user_id = u.id WHERE {where_clause}
            ORDER BY s.created_at DESC LIMIT %s OFFSET %s""", params, "all")
        return {"subscriptions": subs, "total": total, "page": page, "per_page": per_page}

    @app.post("/api/admin/subscriptions/{sub_id}/action")
    async def admin_sub_action(sub_id: int, request: Request, admin: dict = Depends(require_admin_role("super_admin"))):
        body = await request.json()
        action = body.get("action", "")
        if action == "cancel":
            admin_db_exec("UPDATE admin_subscriptions SET status='cancelled', cancelled_at=CURRENT_TIMESTAMP WHERE id=%s", (sub_id,))
        elif action == "reactivate":
            admin_db_exec("UPDATE admin_subscriptions SET status='active', cancelled_at=NULL WHERE id=%s", (sub_id,))
        else:
            raise HTTPException(400, f"Unknown action: {action}")
        return {"status": "ok", "action": action}

    # Admin Products
    @app.get("/api/admin/products")
    async def admin_list_products(page: int = 1, per_page: int = 25, search: str = "", admin: dict = Depends(get_admin_user)):
        where, params = [], []
        if search:
            where.append("(asin ILIKE %s OR name ILIKE %s OR category ILIKE %s)")
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
        where_clause = " AND ".join(where) if where else "1=1"
        total = admin_db_exec(f"SELECT COUNT(*) as total FROM products WHERE {where_clause}", params, "one")["total"]
        offset = (page - 1) * per_page
        params.extend([per_page, offset])
        products = admin_db_exec(f"""SELECT id, asin, name, category, amazon_price, rating, review_count,
            ai_score, traffic_light, created_at FROM products WHERE {where_clause}
            ORDER BY created_at DESC LIMIT %s OFFSET %s""", params, "all")
        return {"products": products, "total": total, "page": page, "per_page": per_page}

    # Admin Features
    @app.get("/api/admin/features")
    async def admin_list_features(admin: dict = Depends(get_admin_user)):
        return {"features": admin_db_exec("SELECT * FROM admin_feature_flags ORDER BY flag_name", fetch="all")}

    @app.post("/api/admin/features")
    async def admin_create_feature(request: Request, admin: dict = Depends(require_admin_role("super_admin"))):
        body = await request.json()
        fid = admin_db_exec("""INSERT INTO admin_feature_flags (flag_name, description, is_enabled, scope, scope_value, rollout_percentage, created_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (body.get("flag_name",""), body.get("description",""), body.get("is_enabled",False),
             body.get("scope","global"), body.get("scope_value",""), body.get("rollout_percentage",100), admin["admin_id"]), "one")
        return {"id": fid["id"]}

    @app.post("/api/admin/features/{flag_id}/toggle")
    async def admin_toggle_feature(flag_id: int, admin: dict = Depends(require_admin_role("super_admin"))):
        f = admin_db_exec("SELECT is_enabled FROM admin_feature_flags WHERE id = %s", (flag_id,), "one")
        if not f: raise HTTPException(404, "Not found")
        admin_db_exec("UPDATE admin_feature_flags SET is_enabled=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s", (not f["is_enabled"], flag_id))
        return {"is_enabled": not f["is_enabled"]}

    # Admin Health
    @app.get("/api/admin/health")
    async def admin_health(admin: dict = Depends(get_admin_user)):
        import psutil
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        db_status = "connected"
        try:
            admin_db_exec("SELECT 1", fetch="one")
        except Exception:
            db_status = "error"
        return {"cpu": cpu, "memory": {"total": mem.total, "used": mem.used, "percent": mem.percent},
                "disk": {"total": disk.total, "used": disk.used, "percent": disk.percent},
                "database": db_status, "timestamp": datetime.now().isoformat()}

    # Admin Jobs
    @app.get("/api/admin/jobs")
    async def admin_list_jobs(page: int = 1, per_page: int = 25, status: str = "", admin: dict = Depends(get_admin_user)):
        where, params = [], []
        if status:
            where.append("status = %s"); params.append(status)
        where_clause = " AND ".join(where) if where else "1=1"
        total = admin_db_exec(f"SELECT COUNT(*) as total FROM admin_jobs WHERE {where_clause}", params, "one")["total"]
        offset = (page - 1) * per_page
        params.extend([per_page, offset])
        jobs = admin_db_exec(f"""SELECT id, job_type, status, user_id, error, started_at, completed_at, duration_ms, created_at
            FROM admin_jobs WHERE {where_clause} ORDER BY created_at DESC LIMIT %s OFFSET %s""", params, "all")
        return {"jobs": jobs, "total": total, "page": page, "per_page": per_page}

    # Admin Audit
    @app.get("/api/admin/audit")
    async def admin_list_audit(page: int = 1, per_page: int = 25, action: str = "", admin_email: str = "", admin: dict = Depends(get_admin_user)):
        where, params = [], []
        if action:
            where.append("action ILIKE %s"); params.append(f"%{action}%")
        if admin_email:
            where.append("admin_email ILIKE %s"); params.append(f"%{admin_email}%")
        where_clause = " AND ".join(where) if where else "1=1"
        total = admin_db_exec(f"SELECT COUNT(*) as total FROM admin_audit_logs WHERE {where_clause}", params, "one")["total"]
        offset = (page - 1) * per_page
        params.extend([per_page, offset])
        logs = admin_db_exec(f"""SELECT id, admin_email, action, target_type, target_id, reason, created_at
            FROM admin_audit_logs WHERE {where_clause} ORDER BY created_at DESC LIMIT %s OFFSET %s""", params, "all")
        return {"logs": logs, "total": total, "page": page, "per_page": per_page}

    # Admin Settings
    @app.get("/api/admin/settings")
    async def admin_list_settings(admin: dict = Depends(get_admin_user)):
        return {"settings": admin_db_exec("SELECT * FROM admin_system_settings ORDER BY setting_type, setting_key", fetch="all")}

    @app.put("/api/admin/settings/{setting_key}")
    async def admin_update_setting(setting_key: str, request: Request, admin: dict = Depends(require_admin_role("super_admin"))):
        body = await request.json()
        admin_db_exec("UPDATE admin_system_settings SET setting_value=%s, updated_by=%s, updated_at=CURRENT_TIMESTAMP WHERE setting_key=%s",
                      (json.dumps(body.get("setting_value")), admin["admin_id"], setting_key))
        return {"message": "Setting updated"}

    # Admin Notifications
    @app.get("/api/admin/notifications")
    async def admin_list_notifications(admin: dict = Depends(get_admin_user)):
        return {"notifications": admin_db_exec("SELECT * FROM admin_notifications WHERE admin_id=%s ORDER BY created_at DESC LIMIT 50", (admin["admin_id"],), "all")}

    # Admin Support
    @app.get("/api/admin/support")
    async def admin_list_support(page: int = 1, per_page: int = 25, status: str = "", admin: dict = Depends(get_admin_user)):
        where, params = [], []
        if status:
            where.append("status = %s"); params.append(status)
        where_clause = " AND ".join(where) if where else "1=1"
        total = admin_db_exec(f"SELECT COUNT(*) as total FROM admin_support_tickets WHERE {where_clause}", params, "one")["total"]
        offset = (page - 1) * per_page
        params.extend([per_page, offset])
        tickets = admin_db_exec(f"""SELECT t.*, u.username, u.email FROM admin_support_tickets t
            LEFT JOIN users u ON t.user_id = u.id WHERE {where_clause}
            ORDER BY created_at DESC LIMIT %s OFFSET %s""", params, "all")
        return {"tickets": tickets, "total": total, "page": page, "per_page": per_page}

    # Admin Backups
    @app.get("/api/admin/backups")
    async def admin_list_backups(admin: dict = Depends(require_admin_role("super_admin"))):
        return {"backups": admin_db_exec("SELECT * FROM admin_backups ORDER BY created_at DESC LIMIT 20", fetch="all")}

    # ════════════════════════════════════════════════════════
    # STARTUP - Ensure admin user exists
    # ════════════════════════════════════════════════════════

    @app.on_event("startup")
    async def seed_admin():
        try:
            admin_pw = os.environ.get("ADMIN_PASSWORD", "admin123")
            pw_hash = bcrypt.hashpw(admin_pw.encode(), bcrypt.gensalt()).decode()
            admin_db_exec(
                """INSERT INTO admin_users (username, email, password_hash, role, display_name)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (username) DO UPDATE SET
                     password_hash = EXCLUDED.password_hash,
                     updated_at = CURRENT_TIMESTAMP""",
                ("admin", "admin@marketlens.com", pw_hash, "super_admin", "Super Admin")
            )
            logger.info("Admin user seeded successfully")
        except Exception as e:
            logger.error("Failed to seed admin user: %s", e)

    # ════════════════════════════════════════════════════════
    # SHUTDOWN
    # ════════════════════════════════════════════════════════

    @app.on_event("shutdown")
    async def shutdown():
        db.close()

    return app


# ════════════════════════════════════════════════════════════
# STANDALONE RUNNER
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO)
    app = create_app()
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
