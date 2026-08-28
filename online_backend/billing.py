"""MarketLens Billing Service - Stripe Integration.

Handles all Stripe operations: customers, subscriptions, payments, webhooks.
Authoritative source for subscription state.
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import stripe
import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)


def _ts_to_dt(ts):
    """Convert a Unix timestamp to a timezone-aware datetime (UTC)."""
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)


class BillingService:
    """Stripe billing integration service."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.stripe_secret = os.environ.get("STRIPE_SECRET_KEY", "")
        self.stripe_webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
        self.test_mode = os.environ.get("BILLING_TEST_MODE", "true").lower() == "true"
        self.success_url = os.environ.get("BILLING_SUCCESS_URL", "http://localhost:8000/billing/success")
        self.cancel_url = os.environ.get("BILLING_CANCEL_URL", "http://localhost:8000/billing/cancel")

        if self.stripe_secret:
            stripe.api_key = self.stripe_secret

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
                    row = cur.fetchone(); conn.commit(); return row[0] if row else None
                else:
                    conn.commit(); return cur.rowcount
        except Exception:
            conn.rollback(); raise
        finally:
            conn.close()

    # ════════════════════════════════════════════════════════════
    # CUSTOMER MANAGEMENT
    # ════════════════════════════════════════════════════════════

    def get_or_create_customer(self, user_id: int, email: str, username: str) -> Dict:
        """Get or create Stripe customer for a user."""
        existing = self._exec(
            "SELECT * FROM billing_customers WHERE user_id = %s", (user_id,), "one"
        )
        if existing:
            return existing

        if not self.stripe_secret:
            raise ValueError("Stripe not configured")

        stripe_customer = stripe.Customer.create(
            email=email or f"{username}@marketlens.local",
            name=username,
            metadata={"user_id": str(user_id), "platform": "marketlens"}
        )

        row = self._exec(
            """INSERT INTO billing_customers (user_id, stripe_customer_id, email, name)
               VALUES (%s, %s, %s, %s) RETURNING *""",
            (user_id, stripe_customer.id, email or "", username), "one"
        )
        return row

    def get_customer(self, user_id: int) -> Optional[Dict]:
        return self._exec(
            "SELECT * FROM billing_customers WHERE user_id = %s", (user_id,), "one"
        )

    # ════════════════════════════════════════════════════════════
    # CHECKOUT SESSION
    # ════════════════════════════════════════════════════════════

    def create_checkout_session(self, user_id: int, plan_slug: str, interval: str = "monthly",
                                 promo_code: str = None) -> Dict:
        """Create a Stripe Checkout Session for subscription."""
        plan = self._exec(
            "SELECT * FROM admin_plans WHERE slug = %s AND is_active = TRUE",
            (plan_slug,), "one"
        )
        if not plan:
            raise ValueError(f"Plan '{plan_slug}' not found or inactive")

        if plan_slug == "free":
            raise ValueError("Free plan does not require checkout")

        customer = self.get_customer(user_id)
        if not customer:
            raise ValueError("Could not create billing customer")

        price_id = plan.get("stripe_price_id_yearly" if interval == "yearly" else "stripe_price_id_monthly", "")
        if not price_id:
            raise ValueError(f"Stripe price not configured for {plan_slug} {interval}")

        checkout_params = {
            "mode": "subscription",
            "customer": customer["stripe_customer_id"],
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": self.success_url + "?session_id={CHECKOUT_SESSION_ID}",
            "cancel_url": self.cancel_url,
            "metadata": {
                "user_id": str(user_id),
                "plan_slug": plan_slug,
                "interval": interval
            },
            "subscription_data": {
                "metadata": {
                    "user_id": str(user_id),
                    "plan_slug": plan_slug
                }
            },
            "allow_promotion_codes": True
        }

        if promo_code:
            promo = self._exec(
                "SELECT * FROM billing_promo_codes WHERE code = %s AND is_active = TRUE",
                (promo_code.upper(),), "one"
            )
            if promo and promo.get("stripe_promo_code_id"):
                checkout_params["discounts"] = [{"promo_code": promo["stripe_promo_code_id"]}]
                checkout_params.pop("allow_promotion_codes", None)

        session = stripe.checkout.Session.create(**checkout_params)

        self._log_audit(user_id=user_id, action="checkout_created",
                        entity_type="checkout", entity_id=0,
                        new_value={"session_id": session.id, "plan": plan_slug, "interval": interval})

        return {
            "session_id": session.id,
            "url": session.url,
            "expires_at": session.expires_at
        }

    def verify_checkout_session(self, session_id: str) -> Dict:
        """Verify a completed checkout session."""
        session = stripe.checkout.Session.retrieve(session_id, expand=["subscription", "customer"])
        return {
            "session_id": session.id,
            "status": session.status,
            "customer": session.customer,
            "subscription": session.subscription,
            "payment_status": session.payment_status,
            "metadata": session.metadata
        }

    # ════════════════════════════════════════════════════════════
    # SUBSCRIPTION MANAGEMENT
    # ════════════════════════════════════════════════════════════

    def get_user_subscription(self, user_id: int) -> Optional[Dict]:
        """Get active subscription for a user."""
        sub = self._exec(
            """SELECT bs.*, ap.name as plan_name, ap.slug as plan_slug,
                      ap.price_monthly, ap.price_yearly, ap.ai_credits_monthly,
                      ap.research_limit, ap.tracking_limit, ap.supplier_search_limit,
                      ap.listing_gen_limit, ap.export_limit, ap.features
               FROM billing_subscriptions bs
               LEFT JOIN admin_plans ap ON bs.plan_id = ap.id
               WHERE bs.user_id = %s AND bs.status IN ('active', 'trialing', 'past_due')
               ORDER BY bs.created_at DESC LIMIT 1""",
            (user_id,), "one"
        )
        if sub:
            return sub

        # Check for admin override
        override = self._exec(
            """SELECT bo.*, ap.name as plan_name, ap.slug as plan_slug
               FROM billing_overrides bo
               LEFT JOIN admin_plans ap ON bo.plan_id = ap.id
               WHERE bo.user_id = %s AND bo.is_active = TRUE
               AND (bo.end_date IS NULL OR bo.end_date > NOW())
               ORDER BY bo.created_at DESC LIMIT 1""",
            (user_id,), "one"
        )
        if override:
            return {
                "user_id": user_id,
                "plan_id": override["plan_id"],
                "plan_name": override["plan_name"],
                "plan_slug": override["plan_slug"],
                "status": "active",
                "billing_cycle": "monthly",
                "is_override": True,
                "override_reason": override["reason"],
                "override_end": override["end_date"],
                "ai_credits_used": 0,
                "research_used": 0,
                "tracking_used": 0,
                "supplier_search_used": 0,
                "listing_gen_used": 0,
                "export_used": 0,
                "current_period_end": override["end_date"],
                "cancel_at_period_end": False
            }

        # Default free plan
        free_plan = self._exec(
            "SELECT * FROM admin_plans WHERE slug = 'free' AND is_active = TRUE", (), "one"
        )
        if free_plan:
            return {
                "user_id": user_id,
                "plan_name": free_plan["name"],
                "plan_slug": "free",
                "status": "active",
                "billing_cycle": "monthly",
                "ai_credits_monthly": free_plan["ai_credits_monthly"],
                "research_limit": free_plan["research_limit"],
                "tracking_limit": free_plan["tracking_limit"],
                "supplier_search_limit": free_plan["supplier_search_limit"],
                "listing_gen_limit": free_plan["listing_gen_limit"],
                "export_limit": free_plan["export_limit"],
                "features": free_plan["features"]
            }
        return None

    def sync_subscription_from_stripe(self, stripe_sub_id: str) -> Optional[Dict]:
        """Sync subscription state from Stripe."""
        try:
            stripe_sub = stripe.Subscription.retrieve(stripe_sub_id, expand=["latest_invoice", "default_payment_method"])
        except Exception as e:
            logger.error("Failed to retrieve Stripe subscription %s: %s", stripe_sub_id, e)
            return None

        # Find or create local subscription
        local_sub = self._exec(
            "SELECT * FROM billing_subscriptions WHERE stripe_subscription_id = %s",
            (stripe_sub_id,), "one"
        )

        # Determine plan from price ID
        price_id = stripe_sub.items.data[0].price.id if stripe_sub.items.data else ""
        plan = self._exec(
            "SELECT * FROM admin_plans WHERE stripe_price_id_monthly = %s OR stripe_price_id_yearly = %s",
            (price_id, price_id), "one"
        )
        plan_id = plan["id"] if plan else None

        # Get user from metadata or customer
        user_id = int(stripe_sub.metadata.get("user_id", 0)) if stripe_sub.metadata else 0
        if not user_id:
            customer = self._exec(
                "SELECT user_id FROM billing_customers WHERE stripe_customer_id = %s",
                (stripe_sub.customer,), "one"
            )
            user_id = customer["user_id"] if customer else 0

        if not user_id:
            logger.error("Cannot sync subscription %s: no user_id found", stripe_sub_id)
            return None

        # Map Stripe status to our status
        status_map = {
            "active": "active",
            "past_due": "past_due",
            "unpaid": "past_due",
            "canceled": "cancelled",
            "incomplete": "incomplete",
            "incomplete_expired": "expired",
            "trialing": "trialing",
            "paused": "paused"
        }
        status = status_map.get(stripe_sub.status, "inactive")

        # Calculate usage limits from plan
        usage = {}
        if plan:
            usage = {
                "ai_credits_used": 0,
                "research_used": 0,
                "tracking_used": 0,
                "supplier_search_used": 0,
                "listing_gen_used": 0,
                "export_used": 0
            }

        if local_sub:
            # Preserve existing usage counts
            usage = {
                "ai_credits_used": local_sub.get("ai_credits_used", 0),
                "research_used": local_sub.get("research_used", 0),
                "tracking_used": local_sub.get("tracking_used", 0),
                "supplier_search_used": local_sub.get("supplier_search_used", 0),
                "listing_gen_used": local_sub.get("listing_gen_used", 0),
                "export_used": local_sub.get("export_used", 0)
            }

            # Reset usage on new billing period
            if local_sub.get("current_period_end") and stripe_sub.current_period_start:
                old_end = local_sub["current_period_end"]
                new_start = _ts_to_dt(stripe_sub.current_period_start)
                if new_start > old_end:
                    # New billing period - reset usage
                    usage = {k: 0 for k in usage}

            self._exec(
                """UPDATE billing_subscriptions SET
                   plan_id = %s, status = %s, stripe_price_id = %s,
                   current_period_start = %s, current_period_end = %s,
                   cancel_at_period_end = %s, cancelled_at = %s,
                   ai_credits_used = %s, research_used = %s,
                   tracking_used = %s, supplier_search_used = %s,
                   listing_gen_used = %s, export_used = %s,
                   updated_at = CURRENT_TIMESTAMP
                   WHERE id = %s""",
                (plan_id, status, price_id,
                 _ts_to_dt(stripe_sub.current_period_start) if stripe_sub.current_period_start else None,
                 _ts_to_dt(stripe_sub.current_period_end) if stripe_sub.current_period_end else None,
                 stripe_sub.cancel_at_period_end,
                 _ts_to_dt(stripe_sub.canceled_at) if stripe_sub.canceled_at else None,
                 usage["ai_credits_used"], usage["research_used"],
                 usage["tracking_used"], usage["supplier_search_used"],
                 usage["listing_gen_used"], usage["export_used"],
                 local_sub["id"])
            )
            return self._exec("SELECT * FROM billing_subscriptions WHERE id = %s", (local_sub["id"],), "one")
        else:
            row = self._exec(
                """INSERT INTO billing_subscriptions
                   (user_id, billing_customer_id, plan_id, stripe_subscription_id, stripe_price_id,
                    status, billing_cycle, current_period_start, current_period_end,
                    cancel_at_period_end, cancelled_at, trial_start, trial_end,
                    ai_credits_used, research_used, tracking_used,
                    supplier_search_used, listing_gen_used, export_used)
                   VALUES (%s,
                    (SELECT id FROM billing_customers WHERE user_id = %s),
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   RETURNING *""",
                (user_id, user_id, plan_id, stripe_sub_id, price_id,
                 status, "monthly" if "month" in (price_id or "") else "yearly",
                 _ts_to_dt(stripe_sub.current_period_start) if stripe_sub.current_period_start else None,
                 _ts_to_dt(stripe_sub.current_period_end) if stripe_sub.current_period_end else None,
                 stripe_sub.cancel_at_period_end,
                 _ts_to_dt(stripe_sub.canceled_at) if stripe_sub.canceled_at else None,
                 _ts_to_dt(stripe_sub.trial_start) if stripe_sub.trial_start else None,
                 _ts_to_dt(stripe_sub.trial_end) if stripe_sub.trial_end else None,
                 0, 0, 0, 0, 0, 0),
                "one"
            )
            return row

    def cancel_subscription(self, user_id: int, reason: str = "") -> Dict:
        """Cancel user's subscription (at period end)."""
        sub = self._exec(
            "SELECT * FROM billing_subscriptions WHERE user_id = %s AND status = 'active'",
            (user_id,), "one"
        )
        if not sub or not sub.get("stripe_subscription_id"):
            raise ValueError("No active subscription found")

        stripe.Subscription.modify(
            sub["stripe_subscription_id"],
            cancel_at_period_end=True,
            metadata={"cancel_reason": reason}
        )

        self._exec(
            """UPDATE billing_subscriptions
               SET cancel_at_period_end = TRUE, cancel_reason = %s, updated_at = CURRENT_TIMESTAMP
               WHERE id = %s""",
            (reason, sub["id"])
        )

        self._log_audit(user_id=user_id, action="subscription_cancel_requested",
                        entity_type="subscription", entity_id=sub["id"],
                        new_value={"cancel_at_period_end": True, "reason": reason})

        return {"status": "cancellation_scheduled", "ends_at": sub.get("current_period_end")}

    def reactivate_subscription(self, user_id: int) -> Dict:
        """Reactivate a cancelled-but-still-active subscription."""
        sub = self._exec(
            "SELECT * FROM billing_subscriptions WHERE user_id = %s AND cancel_at_period_end = TRUE",
            (user_id,), "one"
        )
        if not sub or not sub.get("stripe_subscription_id"):
            raise ValueError("No cancellable subscription found")

        stripe.Subscription.modify(
            sub["stripe_subscription_id"],
            cancel_at_period_end=False
        )

        self._exec(
            """UPDATE billing_subscriptions
               SET cancel_at_period_end = FALSE, cancel_reason = '', updated_at = CURRENT_TIMESTAMP
               WHERE id = %s""",
            (sub["id"],)
        )

        self._log_audit(user_id=user_id, action="subscription_reactivated",
                        entity_type="subscription", entity_id=sub["id"])

        return {"status": "reactivated"}

    def change_plan(self, user_id: int, new_plan_slug: str, interval: str = "monthly") -> Dict:
        """Change subscription plan (upgrade/downgrade)."""
        sub = self._exec(
            """SELECT bs.*, ap.slug as old_slug FROM billing_subscriptions bs
               LEFT JOIN admin_plans ap ON bs.plan_id = ap.id
               WHERE bs.user_id = %s AND bs.status = 'active' AND bs.stripe_subscription_id IS NOT NULL""",
            (user_id,), "one"
        )
        if not sub:
            raise ValueError("No active subscription to change")

        new_plan = self._exec(
            "SELECT * FROM admin_plans WHERE slug = %s AND is_active = TRUE",
            (new_plan_slug,), "one"
        )
        if not new_plan:
            raise ValueError(f"Plan '{new_plan_slug}' not found")

        new_price_id = new_plan.get("stripe_price_id_yearly" if interval == "yearly" else "stripe_price_id_monthly", "")
        if not new_price_id:
            raise ValueError(f"Stripe price not configured for {new_plan_slug}")

        # Get current subscription item
        stripe_sub = stripe.Subscription.retrieve(sub["stripe_subscription_id"])
        current_item_id = stripe_sub.items.data[0].id

        # Determine proration behavior
        is_upgrade = (new_plan.get("price_monthly", 0) > (sub.get("price_monthly") or 0))

        stripe.Subscription.modify(
            sub["stripe_subscription_id"],
            items=[{
                "id": current_item_id,
                "price": new_price_id
            }],
            proration_behavior="create_prorations" if is_upgrade else "none",
            metadata={"changed_from": sub.get("old_slug", ""), "changed_to": new_plan_slug}
        )

        self._log_audit(user_id=user_id, action="plan_changed",
                        entity_type="subscription", entity_id=sub["id"],
                        previous_value={"plan": sub.get("old_slug")},
                        new_value={"plan": new_plan_slug, "interval": interval})

        return {"status": "plan_change_scheduled", "new_plan": new_plan_slug}

    # ════════════════════════════════════════════════════════════
    # PAYMENTS & INVOICES
    # ════════════════════════════════════════════════════════════

    def get_payment_history(self, user_id: int, limit: int = 50) -> List[Dict]:
        return self._exec(
            """SELECT * FROM billing_payments WHERE user_id = %s
               ORDER BY created_at DESC LIMIT %s""",
            (user_id, limit), "all"
        )

    def get_invoices(self, user_id: int, limit: int = 50) -> List[Dict]:
        return self._exec(
            """SELECT * FROM billing_invoices WHERE user_id = %s
               ORDER BY created_at DESC LIMIT %s""",
            (user_id, limit), "all"
        )

    def record_payment(self, user_id: int, stripe_payment_intent_id: str = "",
                       stripe_invoice_id: str = "", amount: int = 0, currency: str = "usd",
                       status: str = "succeeded", payment_method: Dict = None,
                       description: str = "", subscription_id: int = None) -> Dict:
        pm = payment_method or {}
        return self._exec(
            """INSERT INTO billing_payments
               (user_id, subscription_id, stripe_payment_intent_id, stripe_invoice_id,
                amount, currency, status, payment_method_type, payment_method_last4,
                payment_method_brand, description)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING *""",
            (user_id, subscription_id, stripe_payment_intent_id, stripe_invoice_id,
             amount, currency, status, pm.get("type", ""), pm.get("last4", ""),
             pm.get("brand", ""), description), "one"
        )

    def record_invoice(self, user_id: int, stripe_invoice_id: str, amount_due: int = 0,
                       amount_paid: int = 0, status: str = "paid",
                       period_start: datetime = None, period_end: datetime = None,
                       subscription_id: int = None) -> Dict:
        invoice_num = f"INV-{datetime.now().strftime('%Y')}-{self._exec('SELECT COUNT(*)+1 FROM billing_invoices', (), 'scalar'):06d}"
        return self._exec(
            """INSERT INTO billing_invoices
               (user_id, subscription_id, stripe_invoice_id, invoice_number,
                amount_due, amount_paid, status, period_start, period_end)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (stripe_invoice_id) DO UPDATE SET
                amount_paid = EXCLUDED.amount_paid, status = EXCLUDED.status
               RETURNING *""",
            (user_id, subscription_id, stripe_invoice_id, invoice_num,
             amount_due, amount_paid, status, period_start, period_end), "one"
        )

    # ════════════════════════════════════════════════════════════
    # WEBHOOK HANDLING
    # ════════════════════════════════════════════════════════════

    def verify_webhook(self, payload: bytes, sig_header: str) -> Optional[Dict]:
        """Verify Stripe webhook signature and return event."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.stripe_webhook_secret
            )
            return event
        except stripe.error.SignatureVerificationError:
            return None
        except Exception:
            return None

    def process_webhook_event(self, event: Dict) -> bool:
        """Process a verified Stripe webhook event. Idempotent."""
        event_id = event.get("id", "")
        event_type = event.get("type", "")

        # Check idempotency
        existing = self._exec(
            "SELECT id FROM billing_webhook_events WHERE stripe_event_id = %s",
            (event_id,), "one"
        )
        if existing:
            logger.info("Duplicate webhook event %s, skipping", event_id)
            return True

        # Log event
        self._exec(
            """INSERT INTO billing_webhook_events (stripe_event_id, event_type, status, payload)
               VALUES (%s, %s, 'processing', %s)""",
            (event_id, event_type, json.dumps(event.get("data", {}), default=str))
        )

        try:
            handler = {
                "checkout.session.completed": self._handle_checkout_completed,
                "customer.subscription.created": self._handle_subscription_updated,
                "customer.subscription.updated": self._handle_subscription_updated,
                "customer.subscription.deleted": self._handle_subscription_deleted,
                "invoice.paid": self._handle_invoice_paid,
                "invoice.payment_failed": self._handle_invoice_payment_failed,
            }.get(event_type)

            if handler:
                handler(event.get("data", {}).get("object", {}))
                self._exec(
                    "UPDATE billing_webhook_events SET status = 'processed', processed_at = CURRENT_TIMESTAMP WHERE stripe_event_id = %s",
                    (event_id,)
                )
            else:
                self._exec(
                    "UPDATE billing_webhook_events SET status = 'ignored' WHERE stripe_event_id = %s",
                    (event_id,)
                )
            return True

        except Exception as e:
            logger.error("Webhook processing failed for %s: %s", event_id, e)
            self._exec(
                "UPDATE billing_webhook_events SET status = 'failed', error = %s WHERE stripe_event_id = %s",
                (str(e), event_id)
            )
            return False

    def _handle_checkout_completed(self, session: Dict):
        sub_id = session.get("subscription")
        if sub_id:
            self.sync_subscription_from_stripe(sub_id)
            # Record initial payment
            user_id = int(session.get("metadata", {}).get("user_id", 0))
            if user_id:
                self.record_payment(
                    user_id=user_id,
                    stripe_payment_intent_id=session.get("payment_intent", ""),
                    amount=session.get("amount_total", 0),
                    currency=session.get("currency", "usd"),
                    status="succeeded",
                    description=f"Subscription checkout"
                )

    def _handle_subscription_updated(self, subscription: Dict):
        stripe_sub_id = subscription.get("id")
        if stripe_sub_id:
            self.sync_subscription_from_stripe(stripe_sub_id)

    def _handle_subscription_deleted(self, subscription: Dict):
        stripe_sub_id = subscription.get("id")
        if stripe_sub_id:
            self._exec(
                """UPDATE billing_subscriptions SET status = 'cancelled',
                   cancelled_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                   WHERE stripe_subscription_id = %s""",
                (stripe_sub_id,)
            )

    def _handle_invoice_paid(self, invoice: Dict):
        stripe_invoice_id = invoice.get("id")
        user_id = 0
        sub_local = None

        # Find user from subscription
        sub_id = invoice.get("subscription")
        if sub_id:
            sub_local = self._exec(
                "SELECT * FROM billing_subscriptions WHERE stripe_subscription_id = %s",
                (sub_id,), "one"
            )
            if sub_local:
                user_id = sub_local["user_id"]

        if not user_id:
            customer_id = invoice.get("customer")
            if customer_id:
                cust = self._exec(
                    "SELECT user_id FROM billing_customers WHERE stripe_customer_id = %s",
                    (customer_id,), "one"
                )
                user_id = cust["user_id"] if cust else 0

        if user_id:
            self.record_invoice(
                user_id=user_id,
                stripe_invoice_id=stripe_invoice_id,
                amount_due=invoice.get("amount_due", 0),
                amount_paid=invoice.get("amount_paid", 0),
                status="paid",
                 period_start=_ts_to_dt(invoice["period_start"]) if invoice.get("period_start") else None,
                 period_end=_ts_to_dt(invoice["period_end"]) if invoice.get("period_end") else None,
                subscription_id=sub_local["id"] if sub_local else None
            )
            self.record_payment(
                user_id=user_id,
                stripe_invoice_id=stripe_invoice_id,
                amount=invoice.get("amount_paid", 0),
                currency=invoice.get("currency", "usd"),
                status="succeeded",
                description=f"Invoice {invoice.get('number', '')}",
                subscription_id=sub_local["id"] if sub_local else None
            )

    def _handle_invoice_payment_failed(self, invoice: Dict):
        sub_id = invoice.get("subscription")
        if sub_id:
            self._exec(
                """UPDATE billing_subscriptions SET status = 'past_due', updated_at = CURRENT_TIMESTAMP
                   WHERE stripe_subscription_id = %s""",
                (sub_id,)
            )

    # ════════════════════════════════════════════════════════════
    # PROMO CODES
    # ════════════════════════════════════════════════════════════

    def validate_promo_code(self, code: str, plan_slug: str = None) -> Optional[Dict]:
        promo = self._exec(
            "SELECT * FROM billing_promo_codes WHERE code = %s AND is_active = TRUE",
            (code.upper(),), "one"
        )
        if not promo:
            return None
        if promo.get("expires_at") and promo["expires_at"] < datetime.now():
            return None
        if promo.get("max_uses", 0) > 0 and promo.get("used_count", 0) >= promo["max_uses"]:
            return None
        if promo.get("eligible_plans") and plan_slug:
            eligible = promo["eligible_plans"]
            if isinstance(eligible, str):
                eligible = json.loads(eligible)
            if eligible and plan_slug not in eligible:
                return None
        return {
            "code": promo["code"],
            "discount_type": promo["discount_type"],
            "discount_value": promo["discount_value"],
            "duration": promo["duration"]
        }

    # ════════════════════════════════════════════════════════════
    # USAGE TRACKING
    # ════════════════════════════════════════════════════════════

    def get_user_usage(self, user_id: int) -> Dict:
        sub = self.get_user_subscription(user_id)
        if not sub:
            return {"tier": "none", "plan": None, "usage": {}, "limits": {}, "remaining": {}}

        plan = self._exec("SELECT * FROM admin_plans WHERE id = %s", (sub.get("plan_id"),), "one") if sub.get("plan_id") else None
        if not plan:
            plan = self._exec("SELECT * FROM admin_plans WHERE slug = 'free'", (), "one")

        limits = {
            "ai_credits": plan.get("ai_credits_monthly", 50) if plan else 50,
            "research": plan.get("research_limit", 10) if plan else 10,
            "tracking": plan.get("tracking_limit", 5) if plan else 5,
            "suppliers": plan.get("supplier_search_limit", 3) if plan else 3,
            "listings": plan.get("listing_gen_limit", 2) if plan else 2,
            "exports": plan.get("export_limit", 5) if plan else 5,
        }
        used = {
            "ai_credits": sub.get("ai_credits_used", 0),
            "research": sub.get("research_used", 0),
            "tracking": sub.get("tracking_used", 0),
            "suppliers": sub.get("supplier_search_used", 0),
            "listings": sub.get("listing_gen_used", 0),
            "exports": sub.get("export_used", 0),
        }
        remaining = {k: max(0, limits[k] - used[k]) for k in limits}

        return {
            "tier": sub.get("plan_slug", "free"),
            "plan": {
                "name": sub.get("plan_name", "Free"),
                "slug": sub.get("plan_slug", "free"),
                "status": sub.get("status", "active"),
                "billing_cycle": sub.get("billing_cycle", "monthly"),
                "current_period_end": sub.get("current_period_end"),
                "cancel_at_period_end": sub.get("cancel_at_period_end", False)
            },
            "limits": limits,
            "used": used,
            "remaining": remaining
        }

    # ════════════════════════════════════════════════════════════
    # CUSTOMER PORTAL
    # ════════════════════════════════════════════════════════════

    def create_portal_session(self, user_id: int) -> Dict:
        customer = self.get_customer(user_id)
        if not customer:
            raise ValueError("No billing customer found")

        session = stripe.billing_portal.Session.create(
            customer=customer["stripe_customer_id"],
            return_url=self.success_url
        )
        return {"url": session.url}

    # ════════════════════════════════════════════════════════════
    # ADMIN OPERATIONS
    # ════════════════════════════════════════════════════════════

    def admin_get_all_subscriptions(self, page=1, per_page=25, status="") -> Dict:
        where, params = [], []
        if status: where.append("bs.status = %s"); params.append(status)
        wc = " AND ".join(where) if where else "1=1"
        total = self._exec(f"SELECT COUNT(*) as c FROM billing_subscriptions bs WHERE {wc}", params, "one")["c"]
        offset = (page - 1) * per_page
        params.extend([per_page, offset])
        subs = self._exec(f"""
            SELECT bs.*, u.username, u.email, ap.name as plan_name, ap.slug as plan_slug,
                   ap.price_monthly, ap.price_yearly
            FROM billing_subscriptions bs
            LEFT JOIN users u ON bs.user_id = u.id
            LEFT JOIN admin_plans ap ON bs.plan_id = ap.id
            WHERE {wc} ORDER BY bs.created_at DESC LIMIT %s OFFSET %s
        """, tuple(params), "all")
        return {"subscriptions": subs, "total": total, "page": page, "per_page": per_page}

    def admin_get_all_payments(self, page=1, per_page=25, status="") -> Dict:
        where, params = [], []
        if status: where.append("bp.status = %s"); params.append(status)
        wc = " AND ".join(where) if where else "1=1"
        total = self._exec(f"SELECT COUNT(*) as c FROM billing_payments bp WHERE {wc}", params, "one")["c"]
        offset = (page - 1) * per_page
        params.extend([per_page, offset])
        payments = self._exec(f"""
            SELECT bp.*, u.username, u.email
            FROM billing_payments bp
            LEFT JOIN users u ON bp.user_id = u.id
            WHERE {wc} ORDER BY bp.created_at DESC LIMIT %s OFFSET %s
        """, tuple(params), "all")
        return {"payments": payments, "total": total, "page": page, "per_page": per_page}

    def admin_get_all_invoices(self, page=1, per_page=25, status="") -> Dict:
        where, params = [], []
        if status: where.append("bi.status = %s"); params.append(status)
        wc = " AND ".join(where) if where else "1=1"
        total = self._exec(f"SELECT COUNT(*) as c FROM billing_invoices bi WHERE {wc}", params, "one")["c"]
        offset = (page - 1) * per_page
        params.extend([per_page, offset])
        invoices = self._exec(f"""
            SELECT bi.*, u.username, u.email
            FROM billing_invoices bi
            LEFT JOIN users u ON bi.user_id = u.id
            WHERE {wc} ORDER BY bi.created_at DESC LIMIT %s OFFSET %s
        """, tuple(params), "all")
        return {"invoices": invoices, "total": total, "page": page, "per_page": per_page}

    def admin_revenue_stats(self) -> Dict:
        mrr = self._exec("""
            SELECT COALESCE(SUM(CASE WHEN bs.billing_cycle='monthly' THEN ap.price_monthly
                                     WHEN bs.billing_cycle='yearly' THEN ap.price_yearly/12
                                     ELSE 0 END), 0) as mrr
            FROM billing_subscriptions bs
            JOIN admin_plans ap ON bs.plan_id = ap.id
            WHERE bs.status = 'active'
        """, (), "one")["mrr"]

        total_subscribers = self._exec(
            "SELECT COUNT(*) as c FROM billing_subscriptions WHERE status = 'active'",
            (), "one"
        )["c"]

        revenue_today = self._exec("""
            SELECT COALESCE(SUM(amount), 0) as total
            FROM billing_payments WHERE status = 'succeeded'
            AND DATE(created_at) = CURRENT_DATE
        """, (), "one")["total"]

        revenue_month = self._exec("""
            SELECT COALESCE(SUM(amount), 0) as total
            FROM billing_payments WHERE status = 'succeeded'
            AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW())
        """, (), "one")["total"]

        successful_payments = self._exec(
            "SELECT COUNT(*) as c FROM billing_payments WHERE status = 'succeeded' AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW())",
            (), "one"
        )["c"]

        failed_payments = self._exec(
            "SELECT COUNT(*) as c FROM billing_payments WHERE status = 'failed' AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW())",
            (), "one"
        )["c"]

        refunded_payments = self._exec(
            "SELECT COUNT(*) as c FROM billing_payments WHERE status = 'refunded' AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW())",
            (), "one"
        )["c"]

        plan_distribution = self._exec("""
            SELECT ap.name, ap.slug, COUNT(bs.id) as count
            FROM admin_plans ap
            LEFT JOIN billing_subscriptions bs ON ap.id = bs.plan_id AND bs.status = 'active'
            GROUP BY ap.id, ap.name, ap.slug ORDER BY ap.price_monthly
        """, (), "all")

        return {
            "mrr": round(float(mrr), 2),
            "arr": round(float(mrr) * 12, 2),
            "revenue_today": round(float(revenue_today), 2),
            "revenue_month": round(float(revenue_month), 2),
            "total_subscribers": total_subscribers,
            "successful_payments": successful_payments,
            "failed_payments": failed_payments,
            "refunded_payments": refunded_payments,
            "plan_distribution": plan_distribution
        }

    def admin_grant_override(self, user_id: int, plan_slug: str, admin_id: int,
                              days: int = 14, reason: str = "") -> Dict:
        plan = self._exec("SELECT * FROM admin_plans WHERE slug = %s", (plan_slug,), "one")
        if not plan:
            raise ValueError("Plan not found")

        from datetime import timedelta
        end_date = datetime.now() + timedelta(days=days)
        self._exec(
            """INSERT INTO billing_overrides (user_id, plan_id, granted_by, reason, end_date)
               VALUES (%s, %s, %s, %s, %s)""",
            (user_id, plan["id"], admin_id, reason, end_date)
        )

        self._log_audit(user_id=user_id, admin_id=admin_id, action="override_granted",
                        entity_type="override", new_value={"plan": plan_slug, "days": days, "reason": reason})

        return {"status": "granted", "plan": plan_slug, "days": days}

    def admin_refund_payment(self, payment_id: int, admin_id: int, amount: int = 0, reason: str = "") -> Dict:
        payment = self._exec("SELECT * FROM billing_payments WHERE id = %s", (payment_id,), "one")
        if not payment:
            raise ValueError("Payment not found")

        refund_amount = amount or payment["amount"]

        if payment.get("stripe_payment_intent_id"):
            stripe.Refund.create(
                payment_intent=payment["stripe_payment_intent_id"],
                amount=refund_amount,
                reason="requested_by_customer"
            )

        self._exec(
            """UPDATE billing_payments SET status = 'refunded',
               refund_amount = %s, refund_reason = %s, updated_at = CURRENT_TIMESTAMP
               WHERE id = %s""",
            (refund_amount, reason, payment_id)
        )

        self._log_audit(user_id=payment.get("user_id"), admin_id=admin_id, action="refund_issued",
                        entity_type="payment", entity_id=payment_id,
                        new_value={"amount": refund_amount, "reason": reason})

        return {"status": "refunded", "amount": refund_amount}

    def admin_update_plan(self, plan_id: int, data: Dict, admin_id: int) -> Dict:
        plan = self._exec("SELECT * FROM admin_plans WHERE id = %s", (plan_id,), "one")
        if not plan:
            raise ValueError("Plan not found")

        allowed = {"name", "description", "price_monthly", "price_yearly", "currency",
                    "ai_credits_monthly", "research_limit", "tracking_limit",
                    "supplier_search_limit", "listing_gen_limit", "export_limit",
                    "api_access", "advanced_analytics", "product_ideas_access",
                    "history_retention_days", "team_members", "is_active", "features",
                    "stripe_price_id_monthly", "stripe_price_id_yearly", "stripe_product_id"}
        sets, vals = [], []
        for k, v in data.items():
            if k in allowed:
                if k == "features" and isinstance(v, dict):
                    v = json.dumps(v)
                sets.append(f"{k} = %s"); vals.append(v)
        if sets:
            vals.append(plan_id)
            self._exec(f"UPDATE admin_plans SET {', '.join(sets)}, updated_at = CURRENT_TIMESTAMP WHERE id = %s", tuple(vals))

        self._log_audit(admin_id=admin_id, action="plan_updated",
                        entity_type="plan", entity_id=plan_id,
                        previous_value={k: plan.get(k) for k in data.keys() if k in plan},
                        new_value=data)

        return {"status": "updated"}

    def admin_get_webhook_events(self, page=1, per_page=25) -> Dict:
        total = self._exec("SELECT COUNT(*) as c FROM billing_webhook_events", (), "one")["c"]
        offset = (page - 1) * per_page
        events = self._exec(
            "SELECT * FROM billing_webhook_events ORDER BY created_at DESC LIMIT %s OFFSET %s",
            (per_page, offset), "all"
        )
        return {"events": events, "total": total, "page": page, "per_page": per_page}

    def admin_manage_promo_code(self, data: Dict, admin_id: int = None) -> Dict:
        code = data.get("code", "").upper()
        existing = self._exec("SELECT * FROM billing_promo_codes WHERE code = %s", (code,), "one")
        if existing:
            sets, vals = [], []
            for k in ["discount_type", "discount_value", "max_uses", "eligible_plans",
                       "duration", "duration_in_months", "expires_at", "is_active"]:
                if k in data:
                    v = data[k]
                    if k == "eligible_plans" and isinstance(v, list):
                        v = json.dumps(v)
                    sets.append(f"{k} = %s"); vals.append(v)
            if sets:
                vals.append(existing["id"])
                self._exec(f"UPDATE billing_promo_codes SET {', '.join(sets)}, updated_at = CURRENT_TIMESTAMP WHERE id = %s", tuple(vals))
            return {"status": "updated", "code": code}
        else:
            row = self._exec(
                """INSERT INTO billing_promo_codes (code, discount_type, discount_value, max_uses,
                   eligible_plans, duration, duration_in_months, expires_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                (code, data.get("discount_type", "percentage"), data.get("discount_value", 0),
                 data.get("max_uses", 0), json.dumps(data.get("eligible_plans", [])),
                 data.get("duration", "once"), data.get("duration_in_months", 0),
                 data.get("expires_at")), "one"
            )
            return {"status": "created", "code": code, "id": row["id"]}

    # ════════════════════════════════════════════════════════════
    # HELPERS
    # ════════════════════════════════════════════════════════════

    def _log_audit(self, user_id=None, admin_id=None, action="", entity_type="",
                   entity_id=0, previous_value=None, new_value=None, reason=""):
        self._exec(
            """INSERT INTO billing_audit_log (user_id, admin_id, action, entity_type, entity_id,
               previous_value, new_value, reason) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (user_id, admin_id, action, entity_type, entity_id,
             json.dumps(previous_value) if previous_value else None,
             json.dumps(new_value) if new_value else None, reason)
        )

    def get_plans(self) -> List[Dict]:
        return self._exec(
            "SELECT * FROM admin_plans WHERE is_active = TRUE ORDER BY price_monthly",
            (), "all"
        )

    def get_all_plans(self) -> List[Dict]:
        return self._exec("SELECT * FROM admin_plans ORDER BY price_monthly", (), "all")
