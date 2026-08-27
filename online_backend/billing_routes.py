"""MarketLens Billing API Routes.

All billing endpoints for user and admin operations.
"""

import json
import logging
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel

from online_backend.billing import BillingService

logger = logging.getLogger(__name__)

router = APIRouter()

# Will be set during app initialization
_billing: Optional[BillingService] = None


def get_billing():
    global _billing
    if not _billing:
        from online_db.unified import UnifiedDB
        from online_backend.config import BackendConfig
        config = BackendConfig()
        db_url = os.environ.get("DATABASE_URL", "") or config.database_url
        _billing = BillingService(db_url)
    return _billing


# ════════════════════════════════════════════════════════════
# PYDANTIC MODELS
# ════════════════════════════════════════════════════════════

class CheckoutRequest(BaseModel):
    plan_slug: str
    interval: str = "monthly"
    promo_code: str = None

class CancelRequest(BaseModel):
    reason: str = ""

class ChangePlanRequest(BaseModel):
    plan_slug: str
    interval: str = "monthly"

class PromoCodeRequest(BaseModel):
    code: str
    plan_slug: str = None


# ════════════════════════════════════════════════════════════
# USER BILLING ROUTES
# ════════════════════════════════════════════════════════════

def setup_billing_user_routes(app, get_current_user):
    """Add user billing routes to the app."""

    billing = get_billing()

    @app.get("/api/billing/plans")
    async def billing_plans(user: dict = Depends(get_current_user)):
        plans = billing.get_plans()
        return {"plans": plans, "test_mode": billing.test_mode}

    @app.post("/api/billing/checkout")
    async def billing_checkout(req: CheckoutRequest, request: Request, user: dict = Depends(get_current_user)):
        try:
            result = billing.create_checkout_session(
                user_id=user["id"],
                plan_slug=req.plan_slug,
                interval=req.interval,
                promo_code=req.promo_code
            )
            return result
        except ValueError as e:
            raise HTTPException(400, str(e))
        except Exception as e:
            logger.error("Checkout failed: %s", e)
            raise HTTPException(500, "Failed to create checkout session")

    @app.get("/api/billing/checkout/verify/{session_id}")
    async def billing_verify_checkout(session_id: str, user: dict = Depends(get_current_user)):
        try:
            result = billing.verify_checkout_session(session_id)
            return result
        except Exception as e:
            logger.error("Checkout verification failed: %s", e)
            raise HTTPException(500, "Failed to verify checkout")

    @app.get("/api/billing/subscription")
    async def billing_subscription(user: dict = Depends(get_current_user)):
        sub = billing.get_user_subscription(user["id"])
        usage = billing.get_user_usage(user["id"])
        return {"subscription": sub, "usage": usage}

    @app.post("/api/billing/subscription/cancel")
    async def billing_cancel_subscription(req: CancelRequest, user: dict = Depends(get_current_user)):
        try:
            result = billing.cancel_subscription(user["id"], req.reason)
            return result
        except ValueError as e:
            raise HTTPException(400, str(e))

    @app.post("/api/billing/subscription/reactivate")
    async def billing_reactivate_subscription(user: dict = Depends(get_current_user)):
        try:
            result = billing.reactivate_subscription(user["id"])
            return result
        except ValueError as e:
            raise HTTPException(400, str(e))

    @app.post("/api/billing/subscription/change")
    async def billing_change_plan(req: ChangePlanRequest, user: dict = Depends(get_current_user)):
        try:
            result = billing.change_plan(user["id"], req.plan_slug, req.interval)
            return result
        except ValueError as e:
            raise HTTPException(400, str(e))

    @app.get("/api/billing/invoices")
    async def billing_invoices(user: dict = Depends(get_current_user)):
        invoices = billing.get_invoices(user["id"])
        return {"invoices": invoices}

    @app.get("/api/billing/payments")
    async def billing_payments(user: dict = Depends(get_current_user)):
        payments = billing.get_payment_history(user["id"])
        return {"payments": payments}

    @app.post("/api/billing/promo/validate")
    async def billing_validate_promo(req: PromoCodeRequest, user: dict = Depends(get_current_user)):
        result = billing.validate_promo_code(req.code, req.plan_slug)
        if not result:
            raise HTTPException(404, "Invalid or expired promo code")
        return result

    @app.post("/api/billing/customer/portal")
    async def billing_customer_portal(user: dict = Depends(get_current_user)):
        try:
            result = billing.create_portal_session(user["id"])
            return result
        except ValueError as e:
            raise HTTPException(400, str(e))

    @app.get("/api/billing/usage")
    async def billing_usage(user: dict = Depends(get_current_user)):
        return billing.get_user_usage(user["id"])


# ════════════════════════════════════════════════════════════
# WEBHOOK ROUTE
# ════════════════════════════════════════════════════════════

def setup_billing_webhook_route(app):
    """Add webhook receiver route."""

    billing = get_billing()

    @app.post("/api/billing/webhook")
    async def billing_webhook(request: Request):
        payload = await request.body()
        sig_header = request.headers.get("stripe-signature", "")

        event = billing.verify_webhook(payload, sig_header)
        if not event:
            raise HTTPException(400, "Invalid webhook signature")

        billing.process_webhook_event(event)
        return {"received": True}


# ════════════════════════════════════════════════════════════
# ADMIN BILLING ROUTES
# ════════════════════════════════════════════════════════════

def setup_billing_admin_routes(app, get_admin_user, require_admin_role):
    """Add admin billing routes to the app."""

    billing = get_billing()

    @app.get("/api/billing/admin/plans")
    async def admin_billing_plans(admin: dict = Depends(get_admin_user)):
        return {"plans": billing.get_all_plans()}

    @app.put("/api/billing/admin/plans/{plan_id}")
    async def admin_update_plan(plan_id: int, request: Request, admin: dict = Depends(require_admin_role("super_admin", "billing"))):
        body = await request.json()
        try:
            return billing.admin_update_plan(plan_id, body, admin["admin_id"])
        except ValueError as e:
            raise HTTPException(400, str(e))

    @app.get("/api/billing/admin/subscriptions")
    async def admin_billing_subscriptions(page: int = 1, per_page: int = 25, status: str = "",
                                           admin: dict = Depends(get_admin_user)):
        return billing.admin_get_all_subscriptions(page, per_page, status)

    @app.get("/api/billing/admin/payments")
    async def admin_billing_payments(page: int = 1, per_page: int = 25, status: str = "",
                                      admin: dict = Depends(get_admin_user)):
        return billing.admin_get_all_payments(page, per_page, status)

    @app.get("/api/billing/admin/invoices")
    async def admin_billing_invoices(page: int = 1, per_page: int = 25, status: str = "",
                                      admin: dict = Depends(get_admin_user)):
        return billing.admin_get_all_invoices(page, per_page, status)

    @app.get("/api/billing/admin/revenue")
    async def admin_billing_revenue(admin: dict = Depends(get_admin_user)):
        return billing.admin_revenue_stats()

    @app.get("/api/billing/admin/webhook-events")
    async def admin_billing_webhooks(page: int = 1, per_page: int = 25,
                                      admin: dict = Depends(get_admin_user)):
        return billing.admin_get_webhook_events(page, per_page)

    @app.post("/api/billing/admin/override")
    async def admin_grant_override(request: Request, admin: dict = Depends(require_admin_role("super_admin", "billing"))):
        body = await request.json()
        try:
            return billing.admin_grant_override(
                user_id=body.get("user_id"),
                plan_slug=body.get("plan_slug", "pro"),
                admin_id=admin["admin_id"],
                days=body.get("days", 14),
                reason=body.get("reason", "")
            )
        except ValueError as e:
            raise HTTPException(400, str(e))

    @app.post("/api/billing/admin/refund/{payment_id}")
    async def admin_refund_payment(payment_id: int, request: Request,
                                    admin: dict = Depends(require_admin_role("super_admin", "billing"))):
        body = await request.json()
        try:
            return billing.admin_refund_payment(
                payment_id=payment_id,
                admin_id=admin["admin_id"],
                amount=body.get("amount", 0),
                reason=body.get("reason", "")
            )
        except ValueError as e:
            raise HTTPException(400, str(e))

    @app.post("/api/billing/admin/promo")
    async def admin_manage_promo(request: Request, admin: dict = Depends(require_admin_role("super_admin", "billing"))):
        body = await request.json()
        return billing.admin_manage_promo_code(body, admin["admin_id"])
