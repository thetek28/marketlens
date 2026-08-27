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

    @app.get("/", response_class=HTMLResponse)
    async def serve_frontend():
        try:
            with open(_index_html, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        except FileNotFoundError:
            return HTMLResponse(content="<h1>Frontend not found</h1>", status_code=404)

    if os.path.isdir(os.path.join(_web_dir, "static")):
        app.mount("/static", StaticFiles(directory=os.path.join(_web_dir, "static")), name="static")

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
