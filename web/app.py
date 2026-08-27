"""MarketLens Web Application - Full-featured FastAPI backend.

Supports two database backends:
  - SQLite (local development): default, no extra config needed
  - PostgreSQL (cloud deployment): set MLENS_DB_BACKEND=postgresql and provide DB credentials

Environment variables:
  MLENS_DB_BACKEND: sqlite (default) | postgresql
  DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, DB_SSL_MODE: PostgreSQL connection
  MLENS_JWT_SECRET: JWT signing secret (required)
  MLENS_CORS_ORIGINS: Comma-separated CORS origins
"""

import asyncio
import csv
import io
import json
import logging
import os
import random
import re
import sys
import time
import threading
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException, Request, Depends, Response
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.paths import DATA_DIR, PRODUCTS_FILE, NOTES_FILE, SEEN_ASINS_FILE, EXCLUDED_FILE, ensure_dirs
from services.collection_service import CollectionService
from services.analysis_service import AnalysisService
from services.export_service import ExportService
from analyzers.ai_analyzer import AIAnalyzer
from analyzers.consistency import ConsistencyAnalyzer
from analyzers.hidden_gems import HiddenGemsFinder
from analyzers.advanced_analytics import ProductComparator, CategoryAnalyzer, TrendAnalyzer
from data_collectors.supplier_intel import SupplierMatcher, SupplierDatabase
from utils.config import Config
from utils.gating import mark_gating, filter_ungated
from gui.common import AMAZON_FBA_FEES, AMAZON_REFERRAL_FEES
from web.auth import register_user, authenticate_user, create_token, get_current_user, get_user_subscription

logger = logging.getLogger(__name__)

ensure_dirs()

# ── Database Backend Selection ──────────────────────────────────────────────
_DB_BACKEND = os.environ.get("MLENS_DB_BACKEND", "sqlite").lower()

if _DB_BACKEND == "postgresql":
    try:
        from online_db import OnlineDatabaseManager
        from online_db.config import DatabaseConfig
        _db_config = DatabaseConfig()
        db = OnlineDatabaseManager(_db_config)
        logger.info("Using PostgreSQL database backend: %s:%d/%s",
                     _db_config.host, _db_config.port, _db_config.database)
    except ImportError as e:
        logger.error("PostgreSQL backend requested but online_db module not available: %s", e)
        logger.info("Falling back to SQLite")
        _DB_BACKEND = "sqlite"
        from database.manager import DatabaseManager
        db = DatabaseManager()
    except Exception as e:
        logger.error("Failed to connect to PostgreSQL: %s", e)
        logger.info("Falling back to SQLite")
        _DB_BACKEND = "sqlite"
        from database.manager import DatabaseManager
        db = DatabaseManager()
else:
    from database.manager import DatabaseManager
    db = DatabaseManager()
    logger.info("Using SQLite database backend")

_allowed_origins = os.environ.get("MLENS_CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",")

app = FastAPI(title="MarketLens", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _allowed_origins if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

_static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(_static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=_static_dir), name="static")

config = Config()
db = DatabaseManager()
ai_analyzer = AIAnalyzer(config)
collection_service = CollectionService(config)
analysis_service = AnalysisService(config, ai_analyzer)
export_service = ExportService(db)

STOPWORDS = set("a an the is are was were be been being have has had do does did will would shall should may might can could of in to for on with at by from as into through during before after above below between out off over under again further then once here there when where why how all both each few more most other some such no nor not only own same so than too very s and but or if while that this these those it its i me my we our you your he him his she her they them their what which who whom".split())

ASIN_RE = re.compile(r'^B0[A-Z0-9]{8}$')


def _validate_asin(asin: str) -> bool:
    return bool(asin) and ASIN_RE.match(asin.strip().upper()) is not None


class AppState:
    def __init__(self):
        self._lock = threading.Lock()
        self.ideas: List[Dict] = []
        self.hidden_gems: List[Dict] = []
        self.seen_asins: Set[str] = set()
        self.all_time_products: List[Dict] = []
        self.categories: List[str] = ["Home & Kitchen", "Sports & Outdoors", "Toys & Games", "Beauty & Personal Care", "Pet Supplies", "Office Products"]
        self.keywords: List[str] = ["trending", "best seller", "new arrival", "hot", "popular"]
        self.analysis_running = False
        self.analysis_cycle_count = 0
        self.analysis_start_time: Optional[datetime] = None
        self.portfolio_summary: Dict = {}
        self.websocket_clients: Set[WebSocket] = set()
        self.product_notes: Dict = {}
        self.forecast_summary: Dict = {}
        self.suppliers: List[Dict] = []
        self.excluded_asins: Set[str] = set()
        self._load_notes()
        self._load_saved_products()
        self._load_excluded()

    def _load_notes(self):
        if os.path.exists(NOTES_FILE):
            try:
                with open(NOTES_FILE) as f:
                    self.product_notes = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load product notes: %s", e)
                self.product_notes = {}

    def save_notes(self):
        try:
            with open(NOTES_FILE, "w") as f:
                json.dump(self.product_notes, f, indent=2)
        except OSError as e:
            logger.error("Failed to save product notes: %s", e)

    def _load_excluded(self):
        if os.path.exists(EXCLUDED_FILE):
            try:
                with open(EXCLUDED_FILE) as f:
                    data = json.load(f)
                    self.excluded_asins = set(data.get("excluded", []))
                logger.info("Loaded %d excluded ASINs", len(self.excluded_asins))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load excluded products: %s", e)
                self.excluded_asins = set()

    def save_excluded(self):
        try:
            with open(EXCLUDED_FILE, "w") as f:
                json.dump({"excluded": sorted(self.excluded_asins)}, f, indent=2)
        except OSError as e:
            logger.error("Failed to save excluded products: %s", e)

    def exclude_asin(self, asin: str):
        with self._lock:
            self.excluded_asins.add(asin)
            self.save_excluded()

    def unexclude_asin(self, asin: str):
        with self._lock:
            self.excluded_asins.discard(asin)
            self.save_excluded()

    def get_excluded_products(self) -> List[Dict]:
        excluded = []
        for p in self.all_time_products:
            if p.get("asin", "") in self.excluded_asins:
                excluded.append(p)
        return excluded

    def _load_saved_products(self):
        if os.path.exists(PRODUCTS_FILE):
            try:
                data = export_service.load_products(PRODUCTS_FILE)
                if data and data.get("ideas"):
                    self.ideas = data.get("ideas", [])
                    self.hidden_gems = data.get("hidden_gems", [])
                    if data.get("categories"):
                        self.categories = data["categories"]
                    if data.get("keywords"):
                        self.keywords = data["keywords"]
                    self.analysis_cycle_count = data.get("cycle", 0)
                    for p in self.ideas:
                        asin = p.get("asin", "")
                        if asin:
                            self.seen_asins.add(asin)
                            self.all_time_products.append(p)
                    if self.hidden_gems:
                        for g in self.hidden_gems:
                            asin = g.get("asin", "")
                            if asin:
                                self.seen_asins.add(asin)
                    logger.info("Loaded %d products from %s", len(self.ideas), PRODUCTS_FILE)
                    return
            except Exception as e:
                logger.error("Failed to load from %s: %s", PRODUCTS_FILE, e)
        try:
            db_products = db.get_all_products_from_db()
            if db_products:
                self.ideas = db_products
                for p in self.ideas:
                    asin = p.get("asin", "")
                    if asin:
                        self.seen_asins.add(asin)
                        self.all_time_products.append(p)
                logger.info("Loaded %d products from database", len(self.ideas))
        except Exception as e:
            logger.error("Failed to load from database: %s", e)

    def save_products(self):
        try:
            export_service.save_products(
                products=self.ideas,
                hidden_gems=self.hidden_gems,
                categories=self.categories,
                keywords=self.keywords,
                cycle=self.analysis_cycle_count,
                path=PRODUCTS_FILE,
            )
            if self.ideas:
                db.batch_upsert_products(self.ideas)
            with open(SEEN_ASINS_FILE, "w") as f:
                json.dump(list(self.seen_asins), f)
        except Exception as e:
            logger.error("Failed to save products: %s", e)

    def add_products(self, new_products: List[Dict]):
        with self._lock:
            for p in new_products:
                asin = p.get("asin", "")
                if asin and asin not in self.seen_asins:
                    self.seen_asins.add(asin)
                    self.all_time_products.append(p)

    def set_ideas(self, ideas: List[Dict]):
        with self._lock:
            self.ideas = ideas

    def get_ideas_snapshot(self) -> List[Dict]:
        with self._lock:
            return list(self.ideas)

    def get_hidden_gems_snapshot(self) -> List[Dict]:
        with self._lock:
            return list(self.hidden_gems)

    def set_hidden_gems(self, gems: List[Dict]):
        with self._lock:
            self.hidden_gems = gems

state = AppState()


class RateLimiter:
    def __init__(self, max_calls: int, period: float):
        self.max_calls = max_calls
        self.period = period
        self._calls: List[float] = []
        self._lock = threading.Lock()

    def allow(self) -> bool:
        now = time.monotonic()
        with self._lock:
            self._calls = [t for t in self._calls if now - t < self.period]
            if len(self._calls) < self.max_calls:
                self._calls.append(now)
                return True
            return False


_login_limiter = RateLimiter(max_calls=10, period=60)
_api_limiter = RateLimiter(max_calls=120, period=60)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        if not _api_limiter.allow():
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
    return await call_next(request)


async def broadcast(event_type: str, data: Any = None):
    msg = json.dumps({"type": event_type, "data": data, "timestamp": datetime.now().isoformat()})
    disconnected = set()
    for ws in state.websocket_clients:
        try:
            await ws.send_text(msg)
        except Exception:
            disconnected.add(ws)
    state.websocket_clients -= disconnected

def _valid_asin(asin: str) -> bool:
    return bool(asin) and ASIN_RE.match(asin.strip().upper()) is not None

def _valid_product(p: Dict) -> bool:
    asin = (p.get("asin") or "").strip().upper()
    if not _valid_asin(asin):
        return False
    if not (p.get("name") or p.get("title") or "").strip():
        return False
    if (p.get("amazon_price") or 0) <= 0:
        return False
    return True

def _clean_product(p: Dict) -> Dict:
    p["asin"] = (p.get("asin") or "").strip().upper()
    p["name"] = (p.get("name") or p.get("title") or "Unknown Product").strip()
    p["amazon_price"] = max(float(p.get("amazon_price") or 0), 0)
    p["rating"] = max(min(float(p.get("rating") or 0), 5), 0)
    p["review_count"] = max(int(p.get("review_count") or 0), 0)
    return p

def _get_top20():
    products = [_clean_product(p) for p in state.get_ideas_snapshot()
                if not p.get("gated", False)
                and _valid_product(p)
                and p.get("asin", "") not in state.excluded_asins]
    def composite_score(p):
        ai = p.get("ai_score", 0)
        margin = min(p.get("estimated_margin_pct", 0) / 100, 1.0)
        rating = p.get("rating", 0) / 5.0
        tl_bonus = {"GREEN": 0.15, "YELLOW": 0.05, "RED": -0.1}.get(p.get("traffic_light", "RED"), 0)
        return ai * 0.45 + margin * 0.30 + rating * 0.15 + tl_bonus
    products.sort(key=composite_score, reverse=True)
    return products[:20]

def _find_product(asin: str):
    for p in state.get_ideas_snapshot():
        if p.get("asin") == asin:
            return p
    return None

def _generate_seo_keywords(name: str, category: str):
    words = [w.lower() for w in re.split(r'[\s\-/,]+', name) if len(w) > 2 and w.lower() not in STOPWORDS]
    core = list(dict.fromkeys(words))[:15]
    modifiers = ["best", "premium", "professional", "high quality", "durable", "portable", "lightweight", "easy to use", "versatile"]
    qualifiers = ["for home", "for office", "professional grade", "top rated", "2024"]
    long_tail = []
    for kw in core[:8]:
        for mod in modifiers[:3]:
            long_tail.append(f"{mod} {kw}")
        for qual in qualifiers[:2]:
            long_tail.append(f"{kw} {qual}")
    long_tail = list(dict.fromkeys(long_tail))[:25]
    backend_terms = (", ".join(core[:10]) + ", " + ", ".join(long_tail[:8]))[:250]
    search_terms = ", ".join(core[:10] + long_tail[:5])[:500]
    return {"core": core, "long_tail": long_tail, "backend": backend_terms, "search_terms": search_terms}

def _generate_problems_solutions(name: str, category: str):
    cat_lower = category.lower() if category else ""
    templates = {
        "kitchen": [("Takes too long to prepare meals", "Speeds up cooking time by 50%"), ("Cluttered kitchen counters", "Compact design saves counter space"), ("Hard to clean after use", "Dishwasher-safe and non-stick surface"), ("Food doesn't taste fresh", "Preserves flavor and nutrients naturally")],
        "electronics": [("Slow performance frustrates users", "Ultra-fast processing speed"), ("Battery dies too quickly", "All-day battery life with fast charging"), ("Complex setup process", "Plug-and-play with one-touch setup"), ("Poor connectivity", "Latest wireless technology for stable connections")],
        "beauty": [("Skin feels dry after use", "Deep moisturizing formula"), ("Products cause irritation", "Hypoallergenic and dermatologist tested"), ("Results take too long", "Visible results within 7 days"), ("Too expensive for daily use", "Affordable luxury for everyday routine")],
        "fitness": [("Equipment is too bulky", "Foldable and space-saving design"), ("Hard to track progress", "Built-in progress tracking features"), ("Uncomfortable during use", "Ergonomic design for maximum comfort"), ("Breaks after few uses", "Commercial-grade durability")],
    }
    generic = [("Quality doesn't match description", "Verified quality with money-back guarantee"), ("Takes too long to arrive", "Fast shipping with tracking"), ("Hard to find the right product", "Expert-curated selection for your needs"), ("Worried about returns", "30-day hassle-free return policy"), ("Not sure if it's worth the price", "Best value for money with proven results"), ("Concerned about durability", "Tested to last 10x longer than competitors"), ("Don't know how to use it", "Included quick-start guide and video tutorials"), ("Afraid it won't fit", "Universal fit with adjustable sizing")]
    for key, tmpls in templates.items():
        if key in cat_lower:
            return [{"problem": p, "solution": s} for p, s in tmpls] + [{"problem": p, "solution": s} for p, s in random.sample(generic, 8)]
    return [{"problem": p, "solution": s} for p, s in random.sample(generic, min(12, len(generic)))]

# ── WebSocket ──────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    state.websocket_clients.add(ws)
    try:
        await ws.send_text(json.dumps({"type": "connected", "data": {"products": len(state.get_ideas_snapshot())}}))
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        pass
    finally:
        state.websocket_clients.discard(ws)

@app.get("/", response_class=HTMLResponse)
async def index():
    with open(os.path.join(os.path.dirname(__file__), "index.html"), "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

# ── Authentication ──────────────────────────────────────────
@app.post("/api/auth/register")
async def api_register(request: Request):
    body = await request.json()
    username = body.get("username", "").strip()
    password = body.get("password", "")
    email = body.get("email", "").strip()
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password required")
    if len(username) < 3 or len(password) < 8:
        raise HTTPException(status_code=400, detail="Username min 3 chars, password min 8 chars")
    if not any(c.isupper() for c in password) or not any(c.isdigit() for c in password):
        raise HTTPException(status_code=400, detail="Password must contain at least one uppercase letter and one digit")
    if not _login_limiter.allow():
        raise HTTPException(status_code=429, detail="Too many registration attempts")
    if not register_user(username, password, email):
        raise HTTPException(status_code=409, detail="Username already exists")
    token = create_token(username)
    return {"token": token, "username": username}

@app.post("/api/auth/login")
async def api_login(request: Request, response: Response):
    if not _login_limiter.allow():
        raise HTTPException(status_code=429, detail="Too many login attempts")
    body = await request.json()
    username = body.get("username", "").strip()
    password = body.get("password", "")
    if not authenticate_user(username, password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token(username)
    secure = os.environ.get("MLENS_COOKIE_SECURE", "false").lower() == "true"
    response.set_cookie("mjl_token", token, httponly=True, samesite="lax", max_age=86400, secure=secure)
    sub = get_user_subscription(username)
    return {
        "token": token,
        "username": username,
        "subscription": {
            "tier": sub["tier"] if sub else "free",
            "expires_at": sub.get("expires_at") if sub else None,
            "days_left": sub.get("days_left") if sub else None,
            "expired": sub.get("expired", False) if sub else False,
        }
    }

@app.post("/api/auth/logout")
async def api_logout(response: Response):
    response.delete_cookie("mjl_token")
    return {"ok": True}

@app.get("/api/auth/me")
async def api_me(user: str = Depends(get_current_user)):
    db_user = db.get_user_by_username(user)
    sub = get_user_subscription(user)
    return {
        "username": user,
        "email": db_user.get("email", "") if db_user else "",
        "is_admin": bool(db_user.get("is_admin", 0)) if db_user else False,
        "subscription": {
            "tier": sub["tier"] if sub else "free",
            "expires_at": sub.get("expires_at") if sub else None,
            "days_left": sub.get("days_left") if sub else None,
            "expired": sub.get("expired", False) if sub else False,
        }
    }

# ── Subscriptions ──────────────────────────────────────────
@app.get("/api/subscription")
async def get_subscription(user: str = Depends(get_current_user)):
    sub = get_user_subscription(user)
    return {"subscription": sub}

@app.get("/api/admin/users")
async def admin_list_users(user: str = Depends(get_current_user)):
    db_user = db.get_user_by_username(user)
    if not db_user or not db_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    users = db.get_all_users()
    for u in users:
        sub = db.get_active_subscription(u["id"])
        u["subscription"] = {
            "tier": sub["tier"] if sub else "free",
            "expires_at": sub.get("expires_at") if sub else None,
            "days_left": sub.get("days_left") if sub else None,
        }
    return {"users": users}

@app.post("/api/admin/upgrade")
async def admin_upgrade_user(request: Request, user: str = Depends(get_current_user)):
    db_user = db.get_user_by_username(user)
    if not db_user or not db_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    body = await request.json()
    target_username = body.get("username", "")
    tier = body.get("tier", "free")
    days = body.get("days", 0)
    target = db.get_user_by_username(target_username)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    db.upgrade_subscription(target["id"], tier, days)
    return {"ok": True, "username": target_username, "tier": tier, "days": days}

# ── Status ─────────────────────────────────────────────────
@app.get("/api/status")
async def get_status(user: str = Depends(get_current_user)):
    elapsed = (datetime.now() - state.analysis_start_time).total_seconds() if state.analysis_start_time else 0
    return {"running": state.analysis_running, "cycle": state.analysis_cycle_count, "total_products": len(state.get_ideas_snapshot()), "hidden_gems": len(state.get_hidden_gems_snapshot()), "seen_asins": len(state.seen_asins), "elapsed_seconds": elapsed, "categories": state.categories, "keywords": state.keywords}

# ── Products ───────────────────────────────────────────────
@app.get("/api/products/all")
async def get_all_products(user: str = Depends(get_current_user)):
    return {"products": [_clean_product(p) for p in state.get_ideas_snapshot() if not p.get("gated", False) and _valid_product(p) and p.get("asin", "") not in state.excluded_asins]}

@app.get("/api/products/top20")
async def get_top20(user: str = Depends(get_current_user)):
    return {"products": _get_top20()}

@app.get("/api/products")
async def get_products(page: int = 1, per_page: int = 20, category: Optional[str] = None, sort: str = "ai_score", min_margin: Optional[float] = None, min_price: Optional[float] = None, max_price: Optional[float] = None, min_reviews: Optional[int] = None, min_rating: Optional[float] = None, min_ai: Optional[float] = None, traffic_light: Optional[str] = None, search: Optional[str] = None, user: str = Depends(get_current_user)):
    products = [_clean_product(p) for p in state.get_ideas_snapshot() if not p.get("gated", False) and _valid_product(p) and p.get("asin", "") not in state.excluded_asins]
    if category: products = [p for p in products if p.get("category", "").lower() == category.lower()]
    if min_margin is not None: products = [p for p in products if p.get("estimated_margin_pct", 0) >= min_margin]
    if min_price is not None: products = [p for p in products if p.get("amazon_price", 0) >= min_price]
    if max_price is not None: products = [p for p in products if p.get("amazon_price", 0) <= max_price]
    if min_reviews is not None: products = [p for p in products if p.get("review_count", 0) >= min_reviews]
    if min_rating is not None: products = [p for p in products if p.get("rating", 0) >= min_rating]
    if min_ai is not None: products = [p for p in products if p.get("ai_score", 0) * 100 >= min_ai]
    if traffic_light: products = [p for p in products if p.get("traffic_light", "") == traffic_light]
    if search:
        s = search.lower()
        products = [p for p in products if s in p.get("name", "").lower() or s in p.get("asin", "").lower()]
    reverse = sort not in ("name", "asin", "category")
    products.sort(key=lambda x: x.get(sort, 0) if isinstance(x.get(sort, 0), (int, float)) else 0, reverse=reverse)
    total = len(products)
    start = (page - 1) * per_page
    return {"products": products[start:start + per_page], "total": total, "page": page, "per_page": per_page, "pages": (total + per_page - 1) // per_page}

@app.get("/api/products/excluded")
async def get_excluded_products(user: str = Depends(get_current_user)):
    return {"products": state.get_excluded_products(), "count": len(state.excluded_asins)}

@app.get("/api/products/{asin}")
async def get_product(asin: str, user: str = Depends(get_current_user)):
    if not _validate_asin(asin):
        raise HTTPException(status_code=400, detail="Invalid ASIN format")
    p = _find_product(asin)
    if not p: raise HTTPException(status_code=404, detail="Product not found")
    return p

@app.post("/api/products/filter-gated")
async def filter_gated(user: str = Depends(get_current_user)):
    with state._lock:
        before = len(state.ideas)
        state.ideas = [p for p in state.ideas if not p.get("is_gated")]
    return {"removed": before - len(state.get_ideas_snapshot()), "remaining": len(state.get_ideas_snapshot())}

@app.post("/api/products/exclude/{asin}")
async def exclude_product(asin: str, user: str = Depends(get_current_user)):
    if not _validate_asin(asin):
        raise HTTPException(status_code=400, detail="Invalid ASIN format")
    state.exclude_asin(asin)
    return {"excluded": True, "asin": asin, "total_excluded": len(state.excluded_asins)}

@app.delete("/api/products/exclude/{asin}")
async def unexclude_product(asin: str, user: str = Depends(get_current_user)):
    state.unexclude_asin(asin)
    return {"excluded": False, "asin": asin, "total_excluded": len(state.excluded_asins)}

# ── Analysis ───────────────────────────────────────────────
@app.post("/api/analysis/start")
async def start_analysis(user: str = Depends(get_current_user)):
    if state.analysis_running: raise HTTPException(status_code=400, detail="Already running")
    state.analysis_running = True
    state.analysis_start_time = datetime.now()
    asyncio.get_event_loop().run_in_executor(None, _analysis_worker)
    return {"status": "started", "products": len(state.get_ideas_snapshot()), "cycle": state.analysis_cycle_count}

@app.post("/api/analysis/stop")
async def stop_analysis(user: str = Depends(get_current_user)):
    state.analysis_running = False
    state.save_products()
    return {"status": "stopped", "products": len(state.get_ideas_snapshot())}

# ── ASIN Lookup ────────────────────────────────────────────
@app.post("/api/asin-lookup")
async def asin_lookup(request: Request, user: str = Depends(get_current_user)):
    body = await request.json()
    asin = body.get("asin", "").strip().upper()
    if not _validate_asin(asin):
        raise HTTPException(status_code=400, detail="Invalid ASIN format (must be 10 alphanumeric characters)")
    from data_collectors.seller_info import get_seller_info
    loop = asyncio.get_event_loop()
    seller_data = await loop.run_in_executor(None, get_seller_info, asin)
    product = {"asin": asin, "name": seller_data.get("product_name", f"Product {asin}"), "category": seller_data.get("category", "Unknown"), "amazon_price": seller_data.get("price", 0), "rating": seller_data.get("rating", 0), "review_count": seller_data.get("review_count", 0), "brand_name": seller_data.get("brand", ""), "seller_info": seller_data}
    mark_gating(product)
    existing = [p for p in state.get_ideas_snapshot() if p.get("asin") == asin]
    if existing: existing[0].update(product)
    else:
        with state._lock:
            state.ideas.append(product)
    await broadcast("product_found", {"asin": asin, "name": product["name"]})
    return product

@app.post("/api/batch-lookup")
async def batch_lookup(request: Request, user: str = Depends(get_current_user)):
    body = await request.json()
    raw_asins = body.get("asins", [])
    asins = []
    for a in raw_asins:
        a = a.strip().upper()
        if _validate_asin(a):
            asins.append(a)
    if len(asins) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 ASINs per batch")
    from data_collectors.seller_info import get_seller_info
    results = []
    loop = asyncio.get_event_loop()
    for asin in asins:
        existing = _find_product(asin)
        if existing:
            results.append({"asin": asin, "status": "found", "product": existing})
            continue
        try:
            seller_data = await loop.run_in_executor(None, get_seller_info, asin)
            product = {"asin": asin, "name": seller_data.get("product_name", f"Product {asin}"), "category": seller_data.get("category", "Unknown"), "amazon_price": seller_data.get("price", 0), "rating": seller_data.get("rating", 0), "review_count": seller_data.get("review_count", 0), "brand_name": seller_data.get("brand", ""), "seller_info": seller_data}
            mark_gating(product)
            with state._lock:
                state.ideas.append(product)
            results.append({"asin": asin, "status": "new", "product": product})
        except Exception as e:
            logger.warning("Batch lookup failed for %s: %s", asin, e)
            results.append({"asin": asin, "status": "error"})
    return {"results": results}

# ── Categories / Keywords ──────────────────────────────────
@app.post("/api/categories")
async def update_categories(request: Request, user: str = Depends(get_current_user)):
    body = await request.json()
    if body.get("categories"): state.categories = body["categories"]
    return {"categories": state.categories}

@app.post("/api/keywords")
async def update_keywords(request: Request, user: str = Depends(get_current_user)):
    body = await request.json()
    if body.get("keywords"): state.keywords = body["keywords"]
    return {"keywords": state.keywords}

# ── Keywords / SEO ─────────────────────────────────────────
@app.get("/api/seo/all")
async def get_seo_all(user: str = Depends(get_current_user)):
    results = []
    for p in _get_top20():
        name = p.get("name", "")
        category = p.get("category", "")
        seo = _generate_seo_keywords(name, category)
        problems = _generate_problems_solutions(name, category)
        results.append({"asin": p.get("asin", ""), "name": name, "category": category, "price": p.get("amazon_price", 0), "rating": p.get("rating", 0), "reviews": p.get("review_count", 0), "core_keywords": seo["core"], "long_tail": seo["long_tail"], "backend": seo["backend"], "search_terms": seo["search_terms"], "problems": problems})
    return {"results": results}

@app.get("/api/seo/{asin}")
async def get_seo(asin: str, user: str = Depends(get_current_user)):
    if not _validate_asin(asin):
        raise HTTPException(status_code=400, detail="Invalid ASIN format")
    p = _find_product(asin)
    if not p: raise HTTPException(status_code=404, detail="Product not found")
    name = p.get("name", "")
    category = p.get("category", "")
    seo = _generate_seo_keywords(name, category)
    problems = _generate_problems_solutions(name, category)
    return {"asin": asin, "name": name, "category": category, "price": p.get("amazon_price", 0), "rating": p.get("rating", 0), "reviews": p.get("review_count", 0), "core_keywords": seo["core"], "long_tail": seo["long_tail"], "backend": seo["backend"], "search_terms": seo["search_terms"], "problems": problems}

# ── Listing Builder ────────────────────────────────────────
@app.get("/api/listing/{asin}")
async def get_listing(asin: str, user: str = Depends(get_current_user)):
    if not _validate_asin(asin):
        raise HTTPException(status_code=400, detail="Invalid ASIN format")
    p = _find_product(asin)
    if not p: raise HTTPException(status_code=404, detail="Product not found")
    seller = p.get("seller_info", {}) if isinstance(p.get("seller_info"), dict) else {}
    name = p.get("name", "")
    category = p.get("category", "")
    seo = _generate_seo_keywords(name, category)
    bullets = [f"High-quality {name} designed for everyday use", f"Premium materials ensure long-lasting durability", f"Perfect for {category} enthusiasts of all levels", f"Compact and lightweight design for easy portability", f"100% satisfaction guaranteed with full refund policy"]
    description = f"Introducing our premium {name}, crafted with the highest quality materials for exceptional performance in {category}. Whether you're a beginner or expert, this product delivers outstanding results. Order now and experience the difference."
    title = f"{seo['core'][0].title() if seo['core'] else ''} - {name}"
    title_words = len(title.split())
    seo_score = 0
    if 50 <= len(title) <= 200: seo_score += 30
    elif 20 <= len(title) < 50: seo_score += 15
    if seo['core'] and seo['core'][0].lower() in title.lower(): seo_score += 15
    if len(bullets) >= 5: seo_score += 25
    elif len(bullets) >= 3: seo_score += 15
    kw_in_bullets = sum(1 for kw in seo['core'][:5] if any(kw in b.lower() for b in bullets))
    if kw_in_bullets >= 3: seo_score += 15
    elif kw_in_bullets >= 1: seo_score += 8
    if any(w[0].isupper() for w in title.split()): seo_score += 5
    if any(w in title.lower() for w in ["best", "top", "premium", "professional"]): seo_score += 10
    return {"asin": asin, "name": name, "category": category, "brand": seller.get("brand", ""), "manufacturer": seller.get("manufacturer", ""), "price": p.get("amazon_price", 0), "weight": seller.get("product_weight", ""), "dimensions": seller.get("dimensions", ""), "title": title, "bullets": bullets, "description": description, "search_terms": seo["search_terms"], "backend_keywords": seo["backend"], "seo_score": min(seo_score, 100), "model_number": "", "style": "", "material": "", "colour": "", "size": "", "unit_count": "1", "sku": "", "condition": "New", "fulfillment": "FBA", "country_of_origin": ""}

@app.post("/api/listing/{asin}/optimize")
async def optimize_listing(asin: str, user: str = Depends(get_current_user)):
    if not _validate_asin(asin):
        raise HTTPException(status_code=400, detail="Invalid ASIN format")
    p = _find_product(asin)
    if not p: raise HTTPException(status_code=404, detail="Product not found")
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, ai_analyzer.optimize_listing, p.get("name", ""), p.get("category", ""), state.keywords)
        return result
    except Exception as e:
        logger.error("Listing optimization failed for %s: %s", asin, e)
        raise HTTPException(status_code=500, detail="Optimization failed")

# ── Profits ────────────────────────────────────────────────
@app.post("/api/profits/calculate")
async def calculate_profits(request: Request, user: str = Depends(get_current_user)):
    body = await request.json()
    try:
        price = float(body.get("price", 0))
        supplier_cost = float(body.get("supplier_cost", 0))
        shipping = float(body.get("shipping", 2.50))
        weight_oz = float(body.get("weight_oz", 16))
        size_tier = body.get("size_tier", "small_standard")
        category = body.get("category", "default")
        monthly_units = int(body.get("monthly_units", 500))
        ppc_pct = float(body.get("ppc_pct", 15))
        refund_pct = float(body.get("refund_pct", 3))
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid numeric values")
    referral_pct = AMAZON_REFERRAL_FEES.get(category, 0.15)
    referral_fee = price * referral_pct
    size_data = AMAZON_FBA_FEES.get(size_tier, {"fulfillment": 3.22, "storage_per_unit": 0.75})
    fulfillment_fee = size_data.get("fulfillment", 3.22)
    storage_fee = size_data.get("storage_per_unit", 0.75)
    total_fba = referral_fee + fulfillment_fee + storage_fee
    landed_cost = supplier_cost + shipping
    ppc_cost = price * (ppc_pct / 100)
    refund_cost = price * (refund_pct / 100)
    total_cost = landed_cost + total_fba + ppc_cost + refund_cost
    profit = price - total_cost
    margin = (profit / price * 100) if price else 0
    roi = (profit / landed_cost * 100) if landed_cost else 0
    return {"referral_fee": round(referral_fee, 2), "fulfillment_fee": round(fulfillment_fee, 2), "storage_fee": round(storage_fee, 2), "total_fba": round(total_fba, 2), "landed_cost": round(landed_cost, 2), "ppc_cost": round(ppc_cost, 2), "refund_cost": round(refund_cost, 2), "total_cost": round(total_cost, 2), "profit": round(profit, 2), "margin": round(margin, 1), "roi": round(roi, 1), "monthly_revenue": round(price * monthly_units, 2), "monthly_profit": round(profit * monthly_units, 2), "monthly_fba_fees": round(total_fba * monthly_units, 2)}

@app.get("/api/profits/calc-all")
async def calc_all_profits(user: str = Depends(get_current_user)):
    results = []
    for p in _get_top20():
        price = p.get("amazon_price", 0)
        cost = p.get("estimated_supplier_cost", price * 0.3)
        fba = p.get("fba_fees", 3.5)
        profit = p.get("estimated_profit", price - cost - fba)
        margin = p.get("estimated_margin_pct", 0)
        results.append({"asin": p.get("asin", ""), "name": p.get("name", "")[:40], "price": price, "cost": round(cost, 2), "fba_fees": round(fba, 2), "profit": round(profit, 2), "margin": round(margin, 1), "viable": p.get("viable", False)})
    profitable = [r for r in results if r["profit"] > 0]
    return {"products": results, "summary": {"total": len(results), "profitable": len(profitable), "total_revenue": round(sum(r["price"] for r in results), 2), "total_profit": round(sum(r["profit"] for r in results), 2), "avg_margin": round(sum(r["margin"] for r in results) / max(len(results), 1), 1)}}

@app.get("/api/price-history/{asin}")
async def price_history(asin: str, user: str = Depends(get_current_user)):
    if not _validate_asin(asin):
        raise HTTPException(status_code=400, detail="Invalid ASIN format")
    try:
        history = db.get_price_history(asin, limit=50)
        return {"history": history}
    except Exception as e:
        logger.error("Failed to get price history for %s: %s", asin, e)
        return {"history": []}

@app.post("/api/price-history/{asin}/record")
async def record_price(asin: str, request: Request, user: str = Depends(get_current_user)):
    if not _validate_asin(asin):
        raise HTTPException(status_code=400, detail="Invalid ASIN format")
    body = await request.json()
    p = _find_product(asin)
    name = p.get("name", "") if p else ""
    try:
        db.record_price(asin, name, "amazon", float(body.get("price", 0)), rating=float(body.get("rating", 0)), review_count=int(body.get("reviews", 0)))
        return {"status": "recorded"}
    except Exception as e:
        logger.error("Failed to record price for %s: %s", asin, e)
        raise HTTPException(status_code=500, detail="Failed to record price")

@app.get("/api/inventory/{asin}")
async def get_inventory(asin: str, user: str = Depends(get_current_user)):
    if not _validate_asin(asin):
        raise HTTPException(status_code=400, detail="Invalid ASIN format")
    try:
        inv = db.get_inventory(asin)
        return {"inventory": inv if inv else {}}
    except Exception as e:
        logger.error("Failed to get inventory for %s: %s", asin, e)
        return {"inventory": {}}

@app.post("/api/inventory/{asin}")
async def save_inventory(asin: str, request: Request, user: str = Depends(get_current_user)):
    if not _validate_asin(asin):
        raise HTTPException(status_code=400, detail="Invalid ASIN format")
    body = await request.json()
    p = _find_product(asin)
    name = p.get("name", "") if p else ""
    try:
        db.save_inventory(asin, name, body)
        return {"status": "saved"}
    except Exception as e:
        logger.error("Failed to save inventory for %s: %s", asin, e)
        raise HTTPException(status_code=500, detail="Failed to save inventory")

# ── Suppliers ──────────────────────────────────────────────
@app.get("/api/suppliers")
async def get_suppliers(user: str = Depends(get_current_user)):
    db_suppliers = db.get_all_suppliers()
    return {"suppliers": db_suppliers if db_suppliers else SupplierDatabase.get_all_suppliers()}

@app.post("/api/suppliers")
async def add_supplier(request: Request, user: str = Depends(get_current_user)):
    body = await request.json()
    if not body.get("name", "").strip():
        raise HTTPException(status_code=400, detail="Supplier name is required")
    try:
        sid = db.add_supplier(body)
        return {"id": sid, "status": "added"}
    except Exception as e:
        logger.error("Failed to add supplier: %s", e)
        raise HTTPException(status_code=500, detail="Failed to add supplier")

@app.delete("/api/suppliers/{supplier_id}")
async def delete_supplier(supplier_id: int, user: str = Depends(get_current_user)):
    try:
        db.delete_supplier(supplier_id)
        return {"status": "deleted"}
    except Exception as e:
        logger.error("Failed to delete supplier %d: %s", supplier_id, e)
        raise HTTPException(status_code=500, detail="Failed to delete supplier")

@app.get("/api/suppliers/match")
async def match_suppliers(user: str = Depends(get_current_user)):
    top20 = _get_top20()
    if not top20: return {"matches": []}
    matcher = SupplierMatcher()
    db_suppliers = db.get_all_suppliers()
    suppliers = db_suppliers if db_suppliers else SupplierDatabase.get_all_suppliers()
    results = []
    for p in top20[:20]:
        try:
            result = matcher.match_product(p, suppliers)
            matches = result.get("matches", [])[:3]
            for m in matches:
                s = m.get("supplier", {})
                m["supplier_name"] = s.get("name", "")
                m["supplier_location"] = s.get("location", "")
                m["supplier_email"] = s.get("contact_email", "")
                m["supplier_phone"] = s.get("contact_phone", "")
                m["supplier_whatsapp"] = s.get("contact_whatsapp", "")
                m["moq"] = s.get("moq", "")
                m["lead_time"] = s.get("lead_time_days", "")
            results.append({"product": {"name": p.get("name", ""), "asin": p.get("asin", ""), "price": p.get("amazon_price", 0)}, "matches": matches})
        except Exception as e:
            logger.warning("Supplier matching failed for %s: %s", p.get("asin", ""), e)
    return {"matches": results}

@app.post("/api/suppliers/{supplier_id}/quote")
async def generate_quote(supplier_id: int, request: Request, user: str = Depends(get_current_user)):
    body = await request.json()
    product_name = body.get("product_name", "")
    asin = body.get("asin", "")
    try:
        suppliers = db.get_all_suppliers()
        supplier = next((s for s in suppliers if s.get("id") == supplier_id), None)
        if not supplier: raise HTTPException(status_code=404, detail="Supplier not found")
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, ai_analyzer.generate_supplier_quote, {"name": product_name, "asin": asin}, supplier)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Quote generation failed: %s", e)
        raise HTTPException(status_code=500, detail="Quote generation failed")

@app.get("/api/suppliers/export")
async def export_suppliers_csv(user: str = Depends(get_current_user)):
    suppliers = db.get_all_suppliers()
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["name", "location", "country", "website", "contact_person", "contact_email", "contact_phone", "moq", "lead_time_days", "payment_terms", "certifications", "rating", "notes"])
    writer.writeheader()
    for s in suppliers:
        writer.writerow({k: s.get(k, "") for k in ["name", "location", "country", "website", "contact_person", "contact_email", "contact_phone", "moq", "lead_time_days", "payment_terms", "certifications", "rating", "notes"]})
    return StreamingResponse(io.BytesIO(output.getvalue().encode()), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=suppliers.csv"})

@app.post("/api/suppliers/import")
async def import_suppliers_csv(file: UploadFile = File(...), user: str = Depends(get_current_user)):
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")
    reader = csv.DictReader(io.StringIO(content.decode()))
    count = 0
    for row in reader:
        try:
            db.add_supplier(dict(row))
            count += 1
        except Exception as e:
            logger.warning("Failed to import supplier row: %s", e)
    return {"imported": count}

# ── Portfolio ──────────────────────────────────────────────
@app.get("/api/portfolio")
async def get_portfolio(user: str = Depends(get_current_user)):
    top20 = _get_top20()
    traffic = {"GREEN": 0, "YELLOW": 0, "RED": 0}
    portfolio_types = {"ANCHOR": 0, "GROWTH": 0, "BALANCED": 0, "WATCHLIST": 0}
    for p in top20:
        tl = p.get("traffic_light", "RED")
        traffic[tl] = traffic.get(tl, 0) + 1
        pt = p.get("portfolio_type", "WATCHLIST")
        portfolio_types[pt] = portfolio_types.get(pt, 0) + 1
    avg_consistency = sum(p.get("consistency_score", 0) for p in top20) / max(len(top20), 1)
    avg_margin = sum(p.get("estimated_margin_pct", 0) for p in top20) / max(len(top20), 1)
    yearly_totals = [0, 0, 0, 0, 0]
    for p in top20:
        forecast = p.get("forecast", {}) if isinstance(p.get("forecast"), dict) else {}
        yearly = forecast.get("yearly_forecast", [])
        for i in range(min(5, len(yearly))):
            yearly_totals[i] += yearly[i].get("yearly_total", 0)
    return {"summary": {"total": len(top20), "traffic": traffic, "portfolio_types": portfolio_types, "avg_consistency": round(avg_consistency * 100, 1), "avg_margin": round(avg_margin, 1)}, "yearly_forecast": [{"year": i + 1, "total": round(v, 2)} for i, v in enumerate(yearly_totals)], "products": [{"name": p.get("name", "")[:50], "asin": p.get("asin", ""), "traffic_light": p.get("traffic_light", "RED"), "portfolio_type": p.get("portfolio_type", "WATCHLIST"), "consistency": round(p.get("consistency_score", 0) * 100, 1), "ai": round(p.get("ai_score", 0) * 100, 1), "margin": round(p.get("estimated_margin_pct", 0), 1), "price": p.get("amazon_price", 0), "reviews": p.get("review_count", 0), "cagr": round((p.get("forecast", {}) if isinstance(p.get("forecast"), dict) else {}).get("cagr_pct", 0), 1), "yearly": [y.get("yearly_total", 0) for y in (p.get("forecast", {}) if isinstance(p.get("forecast"), dict) else {}).get("yearly_forecast", [])]} for p in sorted(top20, key=lambda x: x.get("consistency_score", 0), reverse=True)]}

# ── Tools: Compare ─────────────────────────────────────────
@app.post("/api/tools/compare")
async def compare_products(request: Request, user: str = Depends(get_current_user)):
    body = await request.json()
    asins = body.get("asins", [])
    products = [p for p in state.get_ideas_snapshot() if p.get("asin") in asins]
    if len(products) < 2: raise HTTPException(status_code=400, detail="Select at least 2 products")
    try:
        comparator = ProductComparator()
        result = comparator.compare(products)
        return result
    except Exception as e:
        logger.error("Product comparison failed: %s", e)
        return {"error": "Comparison failed", "products": [{"name": p.get("name", ""), "asin": p.get("asin", ""), "price": p.get("amazon_price", 0), "rating": p.get("rating", 0), "reviews": p.get("review_count", 0), "margin": p.get("estimated_margin_pct", 0), "ai_score": p.get("ai_score", 0)} for p in products]}

# ── Tools: Analytics ───────────────────────────────────────
@app.get("/api/tools/analytics")
async def get_analytics(user: str = Depends(get_current_user)):
    top20 = _get_top20()
    cat_data = defaultdict(list)
    for p in top20:
        cat_data[p.get("category", "Unknown")].append(p)
    rankings = []
    for cat, items in sorted(cat_data.items(), key=lambda x: -len(x[1])):
        avg_price = sum(i.get("amazon_price", 0) for i in items) / len(items)
        avg_margin = sum(i.get("estimated_margin_pct", 0) for i in items) / len(items)
        avg_ai = sum(i.get("ai_score", 0) for i in items) / len(items)
        rankings.append({"category": cat, "count": len(items), "avg_price": round(avg_price, 2), "avg_margin": round(avg_margin, 1), "avg_ai": round(avg_ai * 100, 1), "opportunity": "High" if avg_margin >= 40 else "Medium" if avg_margin >= 25 else "Low"})
    prices = [p.get("amazon_price", 0) for p in top20 if p.get("amazon_price", 0) > 0]
    sweet_spot = {"min": min(prices) if prices else 0, "max": max(prices) if prices else 0, "avg": round(sum(prices) / len(prices), 2) if prices else 0}
    return {"rankings": rankings, "sweet_spot": sweet_spot, "total_products": len(top20)}

# ── Tools: Notes ───────────────────────────────────────────
@app.get("/api/notes/{asin}")
async def get_notes(asin: str, user: str = Depends(get_current_user)):
    return {"notes": state.product_notes.get(asin, {"tags": [], "text": "", "updated": ""})}

@app.post("/api/notes/{asin}")
async def save_notes(asin: str, request: Request, user: str = Depends(get_current_user)):
    body = await request.json()
    state.product_notes[asin] = {"tags": body.get("tags", []), "text": body.get("text", ""), "updated": datetime.now().isoformat()}
    state.save_notes()
    return {"status": "saved"}

# ── Tools: Team (Comments & Tasks) ─────────────────────────
@app.get("/api/team/comments/{asin}")
async def get_comments(asin: str, user: str = Depends(get_current_user)):
    try:
        return {"comments": db.get_comments(asin)}
    except Exception as e:
        logger.error("Failed to get comments for %s: %s", asin, e)
        return {"comments": []}

@app.post("/api/team/comments/{asin}")
async def add_comment(asin: str, request: Request, user: str = Depends(get_current_user)):
    body = await request.json()
    try:
        db.add_comment(asin, body.get("author", "User"), body.get("comment", ""))
        return {"status": "posted"}
    except Exception as e:
        logger.error("Failed to add comment for %s: %s", asin, e)
        raise HTTPException(status_code=500, detail="Failed to add comment")

@app.get("/api/team/tasks/{asin}")
async def get_tasks(asin: str, user: str = Depends(get_current_user)):
    try:
        return {"tasks": db.get_tasks(asin)}
    except Exception as e:
        logger.error("Failed to get tasks for %s: %s", asin, e)
        return {"tasks": []}

@app.post("/api/team/tasks/{asin}")
async def add_task(asin: str, request: Request, user: str = Depends(get_current_user)):
    body = await request.json()
    p = _find_product(asin)
    name = p.get("name", "") if p else ""
    try:
        db.add_task(asin, name, body.get("task", ""))
        return {"status": "added"}
    except Exception as e:
        logger.error("Failed to add task for %s: %s", asin, e)
        raise HTTPException(status_code=500, detail="Failed to add task")

@app.post("/api/team/tasks/{task_id}/toggle")
async def toggle_task(task_id: int, user: str = Depends(get_current_user)):
    try:
        db.update_task_status(task_id, "done")
        return {"status": "toggled"}
    except Exception as e:
        logger.error("Failed to toggle task %d: %s", task_id, e)
        raise HTTPException(status_code=500, detail="Failed to toggle task")

# ── Tools: Report ──────────────────────────────────────────
@app.post("/api/tools/report")
async def generate_report(request: Request, user: str = Depends(get_current_user)):
    body = await request.json()
    sections = body.get("sections", [])
    company = body.get("company", "MarketLens Analysis")
    top20 = _get_top20()
    lines = [f"{'=' * 60}", f"  {company}", f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", f"{'=' * 60}", ""]
    if "executive" in sections:
        lines.extend(["EXECUTIVE SUMMARY", f"-" * 40, f"Total Products: {len(top20)}", f"High AI (70%+): {len([p for p in top20 if p.get('ai_score', 0) >= 0.7])}", f"High Margin (40%+): {len([p for p in top20 if p.get('estimated_margin_pct', 0) >= 40])}", f"Green Traffic: {len([p for p in top20 if p.get('traffic_light') == 'GREEN'])}", ""])
    if "top_products" in sections:
        lines.extend(["TOP 20 PRODUCTS", f"-" * 40])
        for i, p in enumerate(top20, 1):
            lines.append(f"#{i} {p.get('name', '')[:50]} - £{p.get('amazon_price', 0):.2f} | AI: {p.get('ai_score', 0):.0%} | {p.get('traffic_light', 'N/A')}")
        lines.append("")
    if "profit" in sections:
        lines.extend(["PROFIT ANALYSIS", f"-" * 40])
        for i, p in enumerate(top20, 1):
            lines.append(f"#{i} {p.get('name', '')[:40]} - Margin: {p.get('estimated_margin_pct', 0):.1f}% | Profit: £{p.get('estimated_profit', 0):.2f}")
        lines.append("")
    if "suppliers" in sections:
        lines.extend(["SUPPLIER INFORMATION", f"-" * 40])
        for i, p in enumerate(top20, 1):
            lines.append(f"#{i} {p.get('name', '')[:40]} - Supplier: {p.get('supplier_name', 'N/A')} | Cost: £{p.get('supplier_price', 0):.2f}")
        lines.append("")
    return {"report": "\n".join(lines)}

# ── Charts ─────────────────────────────────────────────────
@app.get("/api/charts/data")
async def get_charts_data(user: str = Depends(get_current_user)):
    products = _get_top20()
    categories = {}
    for p in products:
        cat = p.get("category", "Unknown")
        if cat not in categories: categories[cat] = {"count": 0, "margins": [], "ais": []}
        categories[cat]["count"] += 1
        categories[cat]["margins"].append(p.get("estimated_margin_pct", 0))
        categories[cat]["ais"].append(p.get("ai_score", 0))
    for cat in categories:
        m, a = categories[cat]["margins"], categories[cat]["ais"]
        categories[cat] = {"count": categories[cat]["count"], "avg_margin": round(sum(m) / len(m), 1) if m else 0, "avg_ai": round(sum(a) / len(a) * 100, 1) if a else 0}
    price_dist = {"under_20": 0, "20_50": 0, "50_100": 0, "over_100": 0}
    for p in products:
        pr = p.get("amazon_price", 0)
        if pr < 20: price_dist["under_20"] += 1
        elif pr < 50: price_dist["20_50"] += 1
        elif pr < 100: price_dist["50_100"] += 1
        else: price_dist["over_100"] += 1
    traffic = {"GREEN": 0, "YELLOW": 0, "RED": 0}
    for p in products: traffic[p.get("traffic_light", "RED")] = traffic.get(p.get("traffic_light", "RED"), 0) + 1
    ai_dist = {"low": 0, "medium": 0, "high": 0, "very_high": 0}
    for p in products:
        ai = p.get("ai_score", 0)
        if ai >= 0.7: ai_dist["very_high"] += 1
        elif ai >= 0.5: ai_dist["high"] += 1
        elif ai >= 0.3: ai_dist["medium"] += 1
        else: ai_dist["low"] += 1
    return {"categories": categories, "price_distribution": price_dist, "traffic_lights": traffic, "ai_distribution": ai_dist, "total": len(products)}

@app.post("/api/charts/seasonality")
async def ai_seasonality(request: Request, user: str = Depends(get_current_user)):
    body = await request.json()
    asin = body.get("asin", "")
    p = _find_product(asin)
    if not p: raise HTTPException(status_code=404, detail="Product not found")
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, ai_analyzer.analyze_seasonality, p.get("name", ""), p.get("category", ""), [])
        return result
    except Exception as e:
        logger.error("Seasonality analysis failed for %s: %s", asin, e)
        return {"error": "Analysis failed"}

@app.post("/api/charts/competitors")
async def ai_competitors(request: Request, user: str = Depends(get_current_user)):
    body = await request.json()
    asin = body.get("asin", "")
    p = _find_product(asin)
    if not p: raise HTTPException(status_code=404, detail="Product not found")
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, ai_analyzer.analyze_competitors, p.get("name", ""), p.get("category", ""), [])
        return result
    except Exception as e:
        logger.error("Competitor analysis failed for %s: %s", asin, e)
        return {"error": "Analysis failed"}

@app.post("/api/sentiment/{asin}")
async def run_sentiment(asin: str, user: str = Depends(get_current_user)):
    p = _find_product(asin)
    if not p: raise HTTPException(status_code=404, detail="Product not found")
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, ai_analyzer.analyze_sentiment, p)
        return result
    except Exception as e:
        logger.error("Sentiment analysis failed for %s: %s", asin, e)
        return {"error": "Analysis failed"}

# ── Hidden Gems ────────────────────────────────────────────
@app.get("/api/hidden-gems")
async def get_hidden_gems(user: str = Depends(get_current_user)):
    return {"gems": state.get_hidden_gems_snapshot()}

# ── Export ─────────────────────────────────────────────────
@app.get("/api/export/excel")
async def export_excel(user: str = Depends(get_current_user)):
    top20 = _get_top20()
    if not top20: raise HTTPException(status_code=400, detail="No products to export")
    path = os.path.join(DATA_DIR, "marketlens_report.xlsx")
    try:
        from utils.export_engine import ExcelExporter
        ExcelExporter().export_products(top20, path, hidden_gems=state.get_hidden_gems_snapshot(), portfolio_summary=state.portfolio_summary)
        return FileResponse(path, filename="marketlens_report.xlsx", media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception as e:
        logger.error("Excel export failed: %s", e)
        raise HTTPException(status_code=500, detail="Export failed")

@app.get("/api/export/pdf")
async def export_pdf(user: str = Depends(get_current_user)):
    top20 = _get_top20()
    if not top20: raise HTTPException(status_code=400, detail="No products to export")
    path = os.path.join(DATA_DIR, "marketlens_report.pdf")
    try:
        from utils.export_engine import PDFExporter
        PDFExporter().export_report(top20, path, hidden_gems=state.get_hidden_gems_snapshot(), portfolio_summary=state.portfolio_summary)
        return FileResponse(path, filename="marketlens_report.pdf", media_type="application/pdf")
    except Exception as e:
        logger.error("PDF export failed: %s", e)
        raise HTTPException(status_code=500, detail="Export failed")

@app.get("/api/export/json")
async def export_json(user: str = Depends(get_current_user)):
    top20 = _get_top20()
    payload = {"exported_at": datetime.now().isoformat(), "count": len(top20), "products": top20}
    gems = state.get_hidden_gems_snapshot()
    if gems: payload["hidden_gems"] = gems
    if state.portfolio_summary: payload["portfolio_summary"] = state.portfolio_summary
    return JSONResponse(content=payload)

# ── Config ─────────────────────────────────────────────────
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")

def _load_config():
    import yaml
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}

def _save_config(cfg):
    import yaml
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)

@app.get("/api/config")
async def get_config(user: str = Depends(get_current_user)):
    return _load_config()

@app.put("/api/config")
async def update_config(request: Request, user: str = Depends(get_current_user)):
    body = await request.json()
    cfg = _load_config()
    for key in ("min_profit_margin", "max_competition", "min_demand_score", "min_review_count", "ungated_only", "output_dir", "log_level"):
        if key in body:
            cfg[key] = body[key]
    if "data_sources" in body:
        cfg.setdefault("data_sources", {}).update(body["data_sources"])
    _save_config(cfg)
    return {"ok": True}

# ── Products Clear ─────────────────────────────────────────
@app.delete("/api/products/clear")
async def clear_products(user: str = Depends(get_current_user)):
    with state._lock:
        state.ideas = []
        state.all_time_products = []
        state.seen_asins.clear()
        state.excluded_asins.clear()
    return {"ok": True, "message": "All products cleared"}

# ── Database ───────────────────────────────────────────────
@app.get("/api/database/stats")
async def get_db_stats(user: str = Depends(get_current_user)):
    db_size = "N/A"
    try:
        db_file = db.db_path if hasattr(db, 'db_path') else "marketlens.db"
        if os.path.exists(db_file):
            size_bytes = os.path.getsize(db_file)
            if size_bytes > 1024 * 1024:
                db_size = f"{size_bytes / (1024*1024):.1f} MB"
            else:
                db_size = f"{size_bytes / 1024:.1f} KB"
    except Exception:
        pass
    return {
        "total_products": db.get_products_count(),
        "total_suppliers": len(db.get_all_suppliers()),
        "total_users": len(db.get_all_users()),
        "db_size": db_size,
    }

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": "2.0.0", "database": _DB_BACKEND}

@app.get("/api/backend/info")
async def backend_info(user: str = Depends(get_current_user)):
    """Return current backend configuration."""
    info = {
        "database_backend": _DB_BACKEND,
        "version": "2.0.0",
    }
    if _DB_BACKEND == "postgresql":
        try:
            stats = db.get_stats()
            info["postgresql"] = {
                "status": "connected",
                "total_products": stats.get("total_products", 0),
                "total_suppliers": stats.get("total_suppliers", 0),
            }
        except Exception as e:
            info["postgresql"] = {"status": "error", "error": str(e)}
    else:
        try:
            stats = db.get_stats()
            info["sqlite"] = {
                "status": "connected",
                "total_products": stats.get("total_products", 0),
                "db_path": str(db.db_path) if hasattr(db, "db_path") else "unknown",
            }
        except Exception as e:
            info["sqlite"] = {"status": "error", "error": str(e)}
    return info

# ── Analysis Worker ────────────────────────────────────────
def _analysis_worker():
    loop = None
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        while state.analysis_running:
            state.analysis_cycle_count += 1
            cycle = state.analysis_cycle_count
            loop.run_until_complete(broadcast("status", {"message": f"Cycle {cycle}: Collecting..."}))
            cycle_products = collection_service.collect_cycle(categories=state.categories, keywords=state.keywords, sources=["Amazon", "Google Trends"], status_callback=lambda msg: loop.run_until_complete(broadcast("status", {"message": msg})), progress_callback=lambda p: loop.run_until_complete(broadcast("progress", {"value": p})))
            state.add_products(cycle_products)
            loop.run_until_complete(broadcast("status", {"message": f"Cycle {cycle}: Analyzing {len(state.all_time_products)} products..."}))
            raw_data = {"amazon": state.all_time_products, "trends": [], "social": []}
            ideas = analysis_service.analyze(products=state.all_time_products, raw_data=raw_data, status_callback=lambda msg: loop.run_until_complete(broadcast("status", {"message": msg})))
            state.set_ideas(ideas)
            try:
                consistency = ConsistencyAnalyzer(config)
                state.portfolio_summary = consistency.get_portfolio_summary(state.get_ideas_snapshot())
            except Exception as e:
                logger.warning("Consistency analysis failed: %s", e)
                state.portfolio_summary = {}
            try:
                hg = HiddenGemsFinder(config)
                gems = hg.find_hidden_gems(state.get_ideas_snapshot(), raw_data)
                state.set_hidden_gems(gems)
            except Exception as e:
                logger.warning("Hidden gems search failed: %s", e)
                state.set_hidden_gems([])
            state.save_products()
            loop.run_until_complete(broadcast("cycle_complete", {"cycle": cycle, "products": len(state.get_ideas_snapshot()), "hidden_gems": len(state.get_hidden_gems_snapshot())}))
            if not state.analysis_running: break
            for _ in range(300):
                if not state.analysis_running: break
                time.sleep(1)
        loop.run_until_complete(broadcast("analysis_complete", {"total": len(state.get_ideas_snapshot())}))
        state.save_products()
    except Exception as e:
        logger.error("Analysis worker error: %s", e)
    finally:
        state.analysis_running = False
        if loop:
            loop.close()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
