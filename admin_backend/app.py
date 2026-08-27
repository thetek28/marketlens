"""MarketLens Admin Backend API.

Provides administrative endpoints for managing users, subscriptions,
plans, credits, products, suppliers, data sources, jobs, and system health.

All endpoints require admin authentication and role-based authorization.
"""

import json
import logging
import os
import secrets
import sys
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import bcrypt
import psycopg2
import psycopg2.extras
from fastapi import FastAPI, HTTPException, Request, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════════════════════

DATABASE_URL = os.environ.get("DATABASE_URL", "")
JWT_SECRET = os.environ.get("MLENS_JWT_SECRET", "admin-secret-change-me")

if not DATABASE_URL:
    logger.error("DATABASE_URL not set")

# ════════════════════════════════════════════════════════════
# DATABASE
# ════════════════════════════════════════════════════════════

def get_db():
    """Get database connection."""
    conn = psycopg2.connect(DATABASE_URL, sslmode="require")
    with conn.cursor() as cur:
        cur.execute("SET search_path TO public, marketlens")
    conn.commit()
    return conn

def db_execute(query, params=(), fetch="none"):
    """Execute a query with connection management."""
    conn = get_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            if fetch == "one":
                row = cur.fetchone()
                conn.commit()
                return dict(row) if row else None
            elif fetch == "all":
                rows = cur.fetchall()
                conn.commit()
                return [dict(r) for r in rows]
            else:
                conn.commit()
                return cur.rowcount
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def db_execute_many(query, params_list):
    """Execute multiple queries."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.executemany(query, params_list)
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

# ════════════════════════════════════════════════════════════
# JWT
# ════════════════════════════════════════════════════════════

import hmac

def create_admin_token(admin_id: int, username: str, role: str) -> str:
    """Create admin JWT token."""
    import base64
    payload = {
        "sub": username,
        "admin_id": admin_id,
        "role": role,
        "exp": (datetime.utcnow() + timedelta(hours=12)).isoformat(),
        "iat": datetime.utcnow().isoformat(),
        "is_admin": True,
    }
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode().rstrip("=")
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig_input = f"{header}.{body}".encode()
    signature = hmac.new(JWT_SECRET.encode(), sig_input, "sha256").digest()
    sig = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    return f"{header}.{body}.{sig}"

def decode_admin_token(token: str) -> Optional[dict]:
    """Decode and verify admin JWT token."""
    import base64
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header, body, sig = parts
        sig_input = f"{header}.{body}".encode()
        expected = hmac.new(JWT_SECRET.encode(), sig_input, "sha256").digest()
        actual = base64.urlsafe_b64decode(sig + "==")
        if not hmac.compare_digest(expected, actual):
            return None
        padding = 4 - len(body) % 4
        body += "=" * padding
        payload = json.loads(base64.urlsafe_b64decode(body))
        if datetime.fromisoformat(payload.get("exp", "2000-01-01")) < datetime.utcnow():
            return None
        if not payload.get("is_admin"):
            return None
        return payload
    except Exception:
        return None

# ════════════════════════════════════════════════════════════
# MODELS
# ════════════════════════════════════════════════════════════

class AdminLoginRequest(BaseModel):
    username: str
    password: str

class AdminCreateRequest(BaseModel):
    username: str
    password: str
    email: str
    role: str = "support"
    display_name: str = ""

class PlanCreateRequest(BaseModel):
    name: str
    slug: str
    price_monthly: float = 0
    price_yearly: float = 0
    currency: str = "USD"
    ai_credits_monthly: int = 0
    research_limit: int = 0
    tracking_limit: int = 0
    supplier_search_limit: int = 0
    listing_gen_limit: int = 0
    export_limit: int = 0
    api_access: bool = False
    advanced_analytics: bool = False
    product_ideas_access: str = "limited"
    history_retention_days: int = 30
    team_members: int = 1
    features: dict = {}

class FeatureFlagRequest(BaseModel):
    flag_name: str
    description: str = ""
    is_enabled: bool = False
    scope: str = "global"
    scope_value: str = ""
    rollout_percentage: int = 100

class SubscriptionActionRequest(BaseModel):
    action: str  # change_plan, upgrade, downgrade, extend, cancel, reactivate, pause
    plan_id: Optional[int] = None
    days: Optional[int] = None
    reason: str = ""

class UserActionRequest(BaseModel):
    action: str  # suspend, activate, reset_password, force_password_reset, revoke_sessions
    reason: str = ""

class SettingUpdateRequest(BaseModel):
    setting_value: Any
    reason: str = ""

# ════════════════════════════════════════════════════════════
# AUTH DEPENDENCY
# ════════════════════════════════════════════════════════════

def get_admin(request: Request) -> dict:
    """Extract and verify admin from request."""
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    if not token:
        token = request.cookies.get("mjl_admin_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_admin_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload

def require_role(*roles):
    """Dependency that requires specific admin roles."""
    def checker(admin: dict = Depends(get_admin)):
        if admin.get("role") not in roles and admin.get("role") != "super_admin":
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return admin
    return checker

def log_audit(admin_email: str, action: str, target_type: str = "", target_id: str = "",
              previous_value=None, new_value=None, reason: str = "", ip: str = "", ua: str = ""):
    """Log an admin audit event."""
    try:
        db_execute(
            """INSERT INTO admin_audit_logs (admin_email, action, target_type, target_id, 
               previous_value, new_value, reason, ip_address, user_agent)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (admin_email, action, target_type, target_id,
             json.dumps(previous_value) if previous_value else None,
             json.dumps(new_value) if new_value else None,
             reason, ip, ua)
        )
    except Exception as e:
        logger.error("Audit log failed: %s", e)

# ════════════════════════════════════════════════════════════
# APP
# ════════════════════════════════════════════════════════════

app = FastAPI(title="MarketLens Admin", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ════════════════════════════════════════════════════════════
# ADMIN AUTH
# ════════════════════════════════════════════════════════════

@app.post("/api/admin/auth/login")
async def admin_login(req: AdminLoginRequest):
    admin = db_execute("SELECT * FROM admin_users WHERE username = %s AND is_active = TRUE", (req.username,), "one")
    if not admin or not bcrypt.checkpw(req.password.encode(), admin["password_hash"].encode()):
        raise HTTPException(401, "Invalid credentials")

    db_execute("UPDATE admin_users SET last_login = CURRENT_TIMESTAMP WHERE id = %s", (admin["id"],))
    log_audit(admin["email"], "admin_login", "admin_user", str(admin["id"]),
              ip="", ua="")

    token = create_admin_token(admin["id"], admin["username"], admin["role"])
    return {
        "token": token,
        "admin": {
            "id": admin["id"],
            "username": admin["username"],
            "email": admin["email"],
            "role": admin["role"],
            "display_name": admin["display_name"],
        }
    }

@app.get("/api/admin/auth/me")
async def admin_me(admin: dict = Depends(get_admin)):
    a = db_execute("SELECT id, username, email, role, display_name, is_active, mfa_enabled, last_login, created_at FROM admin_users WHERE id = %s", (admin["admin_id"],), "one")
    if not a:
        raise HTTPException(404, "Admin not found")
    return a

@app.post("/api/admin/auth/logout")
async def admin_logout(admin: dict = Depends(get_admin)):
    log_audit(admin.get("email", ""), "admin_logout", "admin_user", str(admin.get("admin_id", "")))
    return {"status": "ok"}

# ════════════════════════════════════════════════════════════
# ADMIN MANAGEMENT
# ════════════════════════════════════════════════════════════

@app.get("/api/admin/admins")
async def list_admins(admin: dict = Depends(require_role("super_admin"))):
    return {"admins": db_execute("SELECT id, username, email, role, display_name, is_active, last_login, created_at FROM admin_users ORDER BY id", fetch="all")}

@app.post("/api/admin/admins")
async def create_admin(req: AdminCreateRequest, admin: dict = Depends(require_role("super_admin"))):
    existing = db_execute("SELECT id FROM admin_users WHERE username = %s OR email = %s", (req.username, req.email), "one")
    if existing:
        raise HTTPException(400, "Username or email already exists")
    pw_hash = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode()
    new_id = db_execute(
        "INSERT INTO admin_users (username, email, password_hash, role, display_name) VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (req.username, req.email, pw_hash, req.role, req.display_name), "one"
    )
    log_audit(admin.get("email", ""), "create_admin", "admin_user", str(new_id["id"]),
              new_value={"username": req.username, "role": req.role})
    return {"id": new_id["id"], "message": "Admin created"}

@app.post("/api/admin/admins/{admin_id}/toggle")
async def toggle_admin(admin_id: int, admin: dict = Depends(require_role("super_admin"))):
    a = db_execute("SELECT is_active FROM admin_users WHERE id = %s", (admin_id,), "one")
    if not a:
        raise HTTPException(404, "Admin not found")
    new_status = not a["is_active"]
    db_execute("UPDATE admin_users SET is_active = %s WHERE id = %s", (new_status, admin_id))
    log_audit(admin.get("email", ""), "toggle_admin", "admin_user", str(admin_id),
              new_value={"is_active": new_status})
    return {"is_active": new_status}

# ════════════════════════════════════════════════════════════
# DASHBOARD
# ════════════════════════════════════════════════════════════

@app.get("/api/admin/dashboard")
async def admin_dashboard(admin: dict = Depends(get_admin)):
    users = db_execute("SELECT COUNT(*) as total FROM users", fetch="one")
    active_users = db_execute("SELECT COUNT(*) as total FROM users WHERE is_active = 1", fetch="one")
    products = db_execute("SELECT COUNT(*) as total FROM products", fetch="one")
    subscriptions = db_execute("SELECT COUNT(*) as total FROM admin_subscriptions WHERE status = 'active'", fetch="one")
    jobs_running = db_execute("SELECT COUNT(*) as total FROM admin_jobs WHERE status = 'running'", fetch="one")
    jobs_total = db_execute("SELECT COUNT(*) as total FROM admin_jobs", fetch="one")

    # Revenue from active subscriptions
    revenue = db_execute("""
        SELECT COALESCE(SUM(CASE WHEN s.billing_cycle = 'monthly' THEN p.price_monthly 
                                  WHEN s.billing_cycle = 'yearly' THEN p.price_yearly/12 
                                  ELSE 0 END), 0) as mrr
        FROM admin_subscriptions s 
        JOIN admin_plans p ON s.plan_id = p.id 
        WHERE s.status = 'active'
    """, fetch="one")

    # Credits usage
    credits = db_execute("""
        SELECT COALESCE(SUM(ai_credits_used), 0) as total_used,
               COALESCE(SUM(ai_credits_limit), 0) as total_limit
        FROM admin_subscriptions WHERE status = 'active'
    """, fetch="one")

    # Data sources health
    sources = db_execute("SELECT COUNT(*) as total FROM admin_feature_flags WHERE is_enabled = TRUE", fetch="one")

    # Recent jobs
    recent_jobs = db_execute("""
        SELECT id, job_type, status, created_at, duration_ms 
        FROM admin_jobs ORDER BY created_at DESC LIMIT 5
    """, fetch="all")

    return {
        "users": {"total": users["total"], "active": active_users["total"]},
        "products": {"total": products["total"]},
        "subscriptions": {"total": subscriptions["total"]},
        "revenue": {"mrr": revenue["mrr"]},
        "credits": {"used": credits["total_used"], "limit": credits["total_limit"]},
        "jobs": {"running": jobs_running["total"], "total": jobs_total["total"]},
        "recent_jobs": recent_jobs,
    }

# ════════════════════════════════════════════════════════════
# USER MANAGEMENT
# ════════════════════════════════════════════════════════════

@app.get("/api/admin/users")
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    search: str = "",
    status: str = "",
    plan: str = "",
    sort: str = "id",
    admin: dict = Depends(get_admin)
):
    where = []
    params = []

    if search:
        where.append("(u.username ILIKE %s OR u.email ILIKE %s)")
        params.extend([f"%{search}%", f"%{search}%"])
    if status:
        where.append("u.is_active = %s")
        params.append(1 if status == "active" else 0)

    where_clause = " AND ".join(where) if where else "1=1"

    count_q = f"SELECT COUNT(*) as total FROM users u WHERE {where_clause}"
    total = db_execute(count_q, params, "one")["total"]

    offset = (page - 1) * per_page
    valid_sorts = {"id", "username", "email", "created_at"}
    sort_col = sort if sort in valid_sorts else "id"

    users_q = f"""
        SELECT u.id, u.username, u.email, u.is_active, u.created_at,
               s.status as sub_status, s.ai_credits_used, s.ai_credits_limit,
               p.name as plan_name
        FROM users u
        LEFT JOIN admin_subscriptions s ON u.id = s.user_id AND s.status = 'active'
        LEFT JOIN admin_plans p ON s.plan_id = p.id
        WHERE {where_clause}
        ORDER BY u.{sort_col} DESC
        LIMIT %s OFFSET %s
    """
    params.extend([per_page, offset])
    users = db_execute(users_q, params, "all")

    return {"users": users, "total": total, "page": page, "per_page": per_page}

@app.get("/api/admin/users/{user_id}")
async def get_user(user_id: int, admin: dict = Depends(get_admin)):
    user = db_execute("SELECT id, username, email, is_active, created_at FROM users WHERE id = %s", (user_id,), "one")
    if not user:
        raise HTTPException(404, "User not found")

    subscription = db_execute("""
        SELECT s.*, p.name as plan_name, p.price_monthly, p.price_yearly
        FROM admin_subscriptions s
        JOIN admin_plans p ON s.plan_id = p.id
        WHERE s.user_id = %s ORDER BY s.created_at DESC LIMIT 1
    """, (user_id,), "one")

    products_count = db_execute("SELECT COUNT(*) as total FROM products", fetch="one")
    research_count = db_execute("SELECT COUNT(*) as total FROM admin_jobs WHERE user_id = %s", (user_id,), "one")

    return {
        "user": user,
        "subscription": subscription,
        "stats": {
            "products_count": products_count["total"],
            "research_count": research_count["total"],
        }
    }

@app.post("/api/admin/users/{user_id}/action")
async def user_action(user_id: int, req: UserActionRequest, admin: dict = Depends(require_role("super_admin", "admin", "support"))):
    user = db_execute("SELECT * FROM users WHERE id = %s", (user_id,), "one")
    if not user:
        raise HTTPException(404, "User not found")

    if req.action == "suspend":
        db_execute("UPDATE users SET is_active = 0 WHERE id = %s", (user_id,))
        log_audit(admin.get("email", ""), "suspend_user", "user", str(user_id), reason=req.reason)
    elif req.action == "activate":
        db_execute("UPDATE users SET is_active = 1 WHERE id = %s", (user_id,))
        log_audit(admin.get("email", ""), "activate_user", "user", str(user_id), reason=req.reason)
    else:
        raise HTTPException(400, f"Unknown action: {req.action}")

    return {"status": "ok", "action": req.action}

# ════════════════════════════════════════════════════════════
# PLANS
# ════════════════════════════════════════════════════════════

@app.get("/api/admin/plans")
async def list_plans(admin: dict = Depends(get_admin)):
    return {"plans": db_execute("SELECT * FROM admin_plans ORDER BY price_monthly", fetch="all")}

@app.post("/api/admin/plans")
async def create_plan(req: PlanCreateRequest, admin: dict = Depends(require_role("super_admin", "billing"))):
    existing = db_execute("SELECT id FROM admin_plans WHERE name = %s OR slug = %s", (req.name, req.slug), "one")
    if existing:
        raise HTTPException(400, "Plan name or slug already exists")
    plan_id = db_execute(
        """INSERT INTO admin_plans (name, slug, price_monthly, price_yearly, currency, ai_credits_monthly,
           research_limit, tracking_limit, supplier_search_limit, listing_gen_limit, export_limit,
           api_access, advanced_analytics, product_ideas_access, history_retention_days, team_members, features)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
        (req.name, req.slug, req.price_monthly, req.price_yearly, req.currency, req.ai_credits_monthly,
         req.research_limit, req.tracking_limit, req.supplier_search_limit, req.listing_gen_limit,
         req.export_limit, req.api_access, req.advanced_analytics, req.product_ideas_access,
         req.history_retention_days, req.team_members, json.dumps(req.features)),
        "one"
    )
    log_audit(admin.get("email", ""), "create_plan", "plan", str(plan_id["id"]),
              new_value={"name": req.name, "price": req.price_monthly})
    return {"id": plan_id["id"], "message": "Plan created"}

@app.put("/api/admin/plans/{plan_id}")
async def update_plan(plan_id: int, req: PlanCreateRequest, admin: dict = Depends(require_role("super_admin", "billing"))):
    old = db_execute("SELECT * FROM admin_plans WHERE id = %s", (plan_id,), "one")
    if not old:
        raise HTTPException(404, "Plan not found")
    db_execute(
        """UPDATE admin_plans SET name=%s, slug=%s, price_monthly=%s, price_yearly=%s, currency=%s,
           ai_credits_monthly=%s, research_limit=%s, tracking_limit=%s, supplier_search_limit=%s,
           listing_gen_limit=%s, export_limit=%s, api_access=%s, advanced_analytics=%s,
           product_ideas_access=%s, history_retention_days=%s, team_members=%s, features=%s,
           updated_at=CURRENT_TIMESTAMP WHERE id=%s""",
        (req.name, req.slug, req.price_monthly, req.price_yearly, req.currency, req.ai_credits_monthly,
         req.research_limit, req.tracking_limit, req.supplier_search_limit, req.listing_gen_limit,
         req.export_limit, req.api_access, req.advanced_analytics, req.product_ideas_access,
         req.history_retention_days, req.team_members, json.dumps(req.features), plan_id)
    )
    log_audit(admin.get("email", ""), "update_plan", "plan", str(plan_id),
              previous_value={"name": old["name"]}, new_value={"name": req.name})
    return {"message": "Plan updated"}

# ════════════════════════════════════════════════════════════
# SUBSCRIPTIONS
# ════════════════════════════════════════════════════════════

@app.get("/api/admin/subscriptions")
async def list_subscriptions(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    status: str = "",
    admin: dict = Depends(get_admin)
):
    where = []
    params = []
    if status:
        where.append("s.status = %s")
        params.append(status)
    where_clause = " AND ".join(where) if where else "1=1"

    total = db_execute(f"SELECT COUNT(*) as total FROM admin_subscriptions s WHERE {where_clause}", params, "one")["total"]
    offset = (page - 1) * per_page
    params.extend([per_page, offset])

    subs = db_execute(f"""
        SELECT s.*, p.name as plan_name, p.price_monthly, p.price_yearly, u.username, u.email
        FROM admin_subscriptions s
        JOIN admin_plans p ON s.plan_id = p.id
        LEFT JOIN users u ON s.user_id = u.id
        WHERE {where_clause}
        ORDER BY s.created_at DESC LIMIT %s OFFSET %s
    """, params, "all")

    return {"subscriptions": subs, "total": total, "page": page, "per_page": per_page}

@app.post("/api/admin/subscriptions/{sub_id}/action")
async def subscription_action(sub_id: int, req: SubscriptionActionRequest, admin: dict = Depends(require_role("super_admin", "billing"))):
    sub = db_execute("SELECT * FROM admin_subscriptions WHERE id = %s", (sub_id,), "one")
    if not sub:
        raise HTTPException(404, "Subscription not found")

    if req.action == "cancel":
        db_execute("UPDATE admin_subscriptions SET status = 'cancelled', cancelled_at = CURRENT_TIMESTAMP, cancel_reason = %s WHERE id = %s", (req.reason, sub_id))
    elif req.action == "reactivate":
        db_execute("UPDATE admin_subscriptions SET status = 'active', cancelled_at = NULL WHERE id = %s", (sub_id,))
    elif req.action == "change_plan" and req.plan_id:
        plan = db_execute("SELECT * FROM admin_plans WHERE id = %s", (req.plan_id,), "one")
        if not plan:
            raise HTTPException(404, "Plan not found")
        db_execute("UPDATE admin_subscriptions SET plan_id = %s, ai_credits_limit = %s WHERE id = %s",
                   (req.plan_id, plan["ai_credits_monthly"], sub_id))
    elif req.action == "extend" and req.days:
        new_end = (datetime.now() + timedelta(days=req.days)).isoformat()
        db_execute("UPDATE admin_subscriptions SET end_date = %s, renewal_date = %s WHERE id = %s",
                   (new_end, new_end, sub_id))
    else:
        raise HTTPException(400, f"Unknown action: {req.action}")

    log_audit(admin.get("email", ""), f"subscription_{req.action}", "subscription", str(sub_id),
              previous_value={"status": sub["status"]}, new_value={"action": req.action}, reason=req.reason)
    return {"status": "ok", "action": req.action}

# ════════════════════════════════════════════════════════════
# PRODUCTS
# ════════════════════════════════════════════════════════════

@app.get("/api/admin/products")
async def list_products(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    search: str = "",
    admin: dict = Depends(get_admin)
):
    where = []
    params = []
    if search:
        where.append("(asin ILIKE %s OR name ILIKE %s OR category ILIKE %s)")
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    where_clause = " AND ".join(where) if where else "1=1"

    total = db_execute(f"SELECT COUNT(*) as total FROM products WHERE {where_clause}", params, "one")["total"]
    offset = (page - 1) * per_page
    params.extend([per_page, offset])

    products = db_execute(f"""
        SELECT id, asin, name, category, amazon_price, rating, review_count, 
               ai_score, traffic_light, created_at, updated_at
        FROM products WHERE {where_clause}
        ORDER BY created_at DESC LIMIT %s OFFSET %s
    """, params, "all")

    return {"products": products, "total": total, "page": page, "per_page": per_page}

# ════════════════════════════════════════════════════════════
# FEATURE FLAGS
# ════════════════════════════════════════════════════════════

@app.get("/api/admin/features")
async def list_features(admin: dict = Depends(get_admin)):
    return {"features": db_execute("SELECT * FROM admin_feature_flags ORDER BY flag_name", fetch="all")}

@app.post("/api/admin/features")
async def create_feature(req: FeatureFlagRequest, admin: dict = Depends(require_role("super_admin"))):
    fid = db_execute(
        "INSERT INTO admin_feature_flags (flag_name, description, is_enabled, scope, scope_value, rollout_percentage, created_by) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (req.flag_name, req.description, req.is_enabled, req.scope, req.scope_value, req.rollout_percentage, admin["admin_id"]),
        "one"
    )
    log_audit(admin.get("email", ""), "create_feature_flag", "feature_flag", str(fid["id"]),
              new_value={"flag_name": req.flag_name, "enabled": req.is_enabled})
    return {"id": fid["id"]}

@app.put("/api/admin/features/{flag_id}")
async def update_feature(flag_id: int, req: FeatureFlagRequest, admin: dict = Depends(require_role("super_admin"))):
    old = db_execute("SELECT * FROM admin_feature_flags WHERE id = %s", (flag_id,), "one")
    if not old:
        raise HTTPException(404, "Feature flag not found")
    db_execute(
        "UPDATE admin_feature_flags SET flag_name=%s, description=%s, is_enabled=%s, scope=%s, scope_value=%s, rollout_percentage=%s, updated_at=CURRENT_TIMESTAMP WHERE id=%s",
        (req.flag_name, req.description, req.is_enabled, req.scope, req.scope_value, req.rollout_percentage, flag_id)
    )
    log_audit(admin.get("email", ""), "update_feature_flag", "feature_flag", str(flag_id),
              previous_value={"enabled": old["is_enabled"]}, new_value={"enabled": req.is_enabled})
    return {"message": "Updated"}

@app.post("/api/admin/features/{flag_id}/toggle")
async def toggle_feature(flag_id: int, admin: dict = Depends(require_role("super_admin"))):
    f = db_execute("SELECT is_enabled FROM admin_feature_flags WHERE id = %s", (flag_id,), "one")
    if not f:
        raise HTTPException(404, "Feature flag not found")
    new_val = not f["is_enabled"]
    db_execute("UPDATE admin_feature_flags SET is_enabled = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (new_val, flag_id))
    log_audit(admin.get("email", ""), "toggle_feature_flag", "feature_flag", str(flag_id),
              new_value={"is_enabled": new_val})
    return {"is_enabled": new_val}

# ════════════════════════════════════════════════════════════
# AUDIT LOGS
# ════════════════════════════════════════════════════════════

@app.get("/api/admin/audit")
async def list_audit_logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    action: str = "",
    admin_email: str = "",
    admin: dict = Depends(get_admin)
):
    where = []
    params = []
    if action:
        where.append("action ILIKE %s")
        params.append(f"%{action}%")
    if admin_email:
        where.append("admin_email ILIKE %s")
        params.append(f"%{admin_email}%")
    where_clause = " AND ".join(where) if where else "1=1"

    total = db_execute(f"SELECT COUNT(*) as total FROM admin_audit_logs WHERE {where_clause}", params, "one")["total"]
    offset = (page - 1) * per_page
    params.extend([per_page, offset])

    logs = db_execute(f"""
        SELECT id, admin_email, action, target_type, target_id, reason, created_at
        FROM admin_audit_logs WHERE {where_clause}
        ORDER BY created_at DESC LIMIT %s OFFSET %s
    """, params, "all")

    return {"logs": logs, "total": total, "page": page, "per_page": per_page}

# ════════════════════════════════════════════════════════════
# SYSTEM SETTINGS
# ════════════════════════════════════════════════════════════

@app.get("/api/admin/settings")
async def list_settings(admin: dict = Depends(get_admin)):
    return {"settings": db_execute("SELECT * FROM admin_system_settings ORDER BY setting_type, setting_key", fetch="all")}

@app.put("/api/admin/settings/{setting_key}")
async def update_setting(setting_key: str, req: SettingUpdateRequest, admin: dict = Depends(require_role("super_admin"))):
    old = db_execute("SELECT * FROM admin_system_settings WHERE setting_key = %s", (setting_key,), "one")
    if not old:
        raise HTTPException(404, "Setting not found")
    db_execute(
        "UPDATE admin_system_settings SET setting_value = %s, updated_by = %s, updated_at = CURRENT_TIMESTAMP WHERE setting_key = %s",
        (json.dumps(req.setting_value), admin["admin_id"], setting_key)
    )
    log_audit(admin.get("email", ""), "update_setting", "system_setting", setting_key,
              previous_value=old["setting_value"], new_value=req.setting_value, reason=req.reason)
    return {"message": "Setting updated"}

# ════════════════════════════════════════════════════════════
# SERVER HEALTH
# ════════════════════════════════════════════════════════════

@app.get("/api/admin/health")
async def server_health(admin: dict = Depends(get_admin)):
    import psutil
    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    db_status = "connected"
    try:
        db_execute("SELECT 1", fetch="one")
    except Exception:
        db_status = "error"

    return {
        "cpu": cpu,
        "memory": {"total": mem.total, "used": mem.used, "percent": mem.percent},
        "disk": {"total": disk.total, "used": disk.used, "percent": disk.percent},
        "database": db_status,
        "timestamp": datetime.now().isoformat(),
    }

@app.get("/api/admin/health/history")
async def health_history(admin: dict = Depends(get_admin)):
    return {"snapshots": db_execute(
        "SELECT * FROM admin_health_snapshots ORDER BY created_at DESC LIMIT 50",
        fetch="all"
    )}

# ════════════════════════════════════════════════════════════
# JOBS
# ════════════════════════════════════════════════════════════

@app.get("/api/admin/jobs")
async def list_jobs(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    status: str = "",
    job_type: str = "",
    admin: dict = Depends(get_admin)
):
    where = []
    params = []
    if status:
        where.append("status = %s")
        params.append(status)
    if job_type:
        where.append("job_type = %s")
        params.append(job_type)
    where_clause = " AND ".join(where) if where else "1=1"

    total = db_execute(f"SELECT COUNT(*) as total FROM admin_jobs WHERE {where_clause}", params, "one")["total"]
    offset = (page - 1) * per_page
    params.extend([per_page, offset])

    jobs = db_execute(f"""
        SELECT id, job_type, status, user_id, error, started_at, completed_at, duration_ms, created_at
        FROM admin_jobs WHERE {where_clause}
        ORDER BY created_at DESC LIMIT %s OFFSET %s
    """, params, "all")

    return {"jobs": jobs, "total": total, "page": page, "per_page": per_page}

# ════════════════════════════════════════════════════════════
# BACKUPS
# ════════════════════════════════════════════════════════════

@app.get("/api/admin/backups")
async def list_backups(admin: dict = Depends(require_role("super_admin"))):
    return {"backups": db_execute("SELECT * FROM admin_backups ORDER BY created_at DESC LIMIT 20", fetch="all")}

# ════════════════════════════════════════════════════════════
# SUPPORT
# ════════════════════════════════════════════════════════════

@app.get("/api/admin/support")
async def list_support_tickets(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    status: str = "",
    admin: dict = Depends(get_admin)
):
    where = []
    params = []
    if status:
        where.append("status = %s")
        params.append(status)
    where_clause = " AND ".join(where) if where else "1=1"

    total = db_execute(f"SELECT COUNT(*) as total FROM admin_support_tickets WHERE {where_clause}", params, "one")["total"]
    offset = (page - 1) * per_page
    params.extend([per_page, offset])

    tickets = db_execute(f"""
        SELECT t.*, u.username, u.email
        FROM admin_support_tickets t
        LEFT JOIN users u ON t.user_id = u.id
        WHERE {where_clause}
        ORDER BY created_at DESC LIMIT %s OFFSET %s
    """, params, "all")

    return {"tickets": tickets, "total": total, "page": page, "per_page": per_page}

# ════════════════════════════════════════════════════════════
# NOTIFICATIONS
# ════════════════════════════════════════════════════════════

@app.get("/api/admin/notifications")
async def list_notifications(admin: dict = Depends(get_admin)):
    return {"notifications": db_execute(
        "SELECT * FROM admin_notifications WHERE admin_id = %s ORDER BY created_at DESC LIMIT 50",
        (admin["admin_id"],), "all"
    )}

@app.post("/api/admin/notifications/{notif_id}/read")
async def mark_notification_read(notif_id: int, admin: dict = Depends(get_admin)):
    db_execute("UPDATE admin_notifications SET is_read = TRUE WHERE id = %s AND admin_id = %s",
               (notif_id, admin["admin_id"]))
    return {"status": "ok"}

# ════════════════════════════════════════════════════════════
# STANDALONE
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO)
    port = int(os.environ.get("ADMIN_PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port)
