"""Stripe checkout + fulfillment + webhook."""
import os
from datetime import datetime, timedelta
from typing import Dict
from fastapi import Depends, HTTPException, Request

from core import api, db, logger, now_utc, gen_id, get_current_user
from models import CheckoutRequest
from routers.settings import get_setting
import stripe  # official Stripe Python SDK

# Currencies Stripe treats as zero-decimal (amount is NOT multiplied by 100).
_ZERO_DECIMAL = {"bif", "clp", "djf", "gnf", "jpy", "kmf", "krw", "mga", "pyg", "rwf", "ugx", "vnd", "vuv", "xaf", "xof", "xpf"}


def _to_minor_units(amount: float, currency: str) -> int:
    if (currency or "").lower() in _ZERO_DECIMAL:
        return int(round(float(amount)))
    return int(round(float(amount) * 100))


async def _create_onetime_session(*, amount, currency, success_url, cancel_url, metadata, customer_email, product_name):
    """One-time Checkout session via the official Stripe SDK."""
    stripe.api_key = await _stripe_api_key()
    return stripe.checkout.Session.create(
        mode="payment",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata,
        customer_email=customer_email,
        line_items=[{
            "price_data": {
                "currency": (currency or "usd").lower(),
                "unit_amount": _to_minor_units(amount, currency),
                "product_data": {"name": product_name or "Tony Yoga"},
            },
            "quantity": 1,
        }],
    )


# Map our billing_cycle field to Stripe recurring interval params.
_BILLING_CYCLE_TO_STRIPE = {
    "weekly":    {"interval": "week",  "interval_count": 1},
    "monthly":   {"interval": "month", "interval_count": 1},
    "quarterly": {"interval": "month", "interval_count": 3},
    "yearly":    {"interval": "year",  "interval_count": 1},
}


async def _stripe_api_key() -> str:
    """Effective Stripe secret: DB setting first, then env fallback."""
    key = await get_setting("stripe_secret_key")
    return key or os.environ.get("STRIPE_API_KEY", "")


async def _create_subscription_session(*, user: dict, plan: dict, origin_url: str) -> dict:
    """Create a Stripe Checkout session in subscription mode with optional trial_period_days.

    Uses the official Stripe SDK in subscription mode.
    Returns {url, session_id, amount, currency, metadata}.
    """
    stripe.api_key = await _stripe_api_key()
    cycle = plan.get("billing_cycle", "monthly")
    recurring = _BILLING_CYCLE_TO_STRIPE.get(cycle, _BILLING_CYCLE_TO_STRIPE["monthly"])
    currency = (plan.get("currency") or "usd").lower()
    unit_amount = int(round(float(plan["price"]) * 100))  # Stripe wants integer cents
    trial_days = int(plan.get("trial_days") or 0)

    subscription_data: Dict = {
        "metadata": {
            "user_id": user["id"],
            "plan_id": plan["id"],
            "plan_name": plan.get("name", ""),
        },
    }
    if trial_days > 0:
        subscription_data["trial_period_days"] = trial_days

    metadata = {
        "user_id": user["id"], "user_email": user["email"],
        "item_type": "membership", "item_id": plan["id"],
        "quantity": "1", "plan_name": plan.get("name", ""),
        "trial_days": str(trial_days),
    }
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer_email=user["email"],
        line_items=[{
            "price_data": {
                "currency": currency,
                "product_data": {"name": plan.get("name") or "Membership"},
                "unit_amount": unit_amount,
                "recurring": recurring,
            },
            "quantity": 1,
        }],
        success_url=f"{origin_url}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{origin_url}/checkout/cancel",
        metadata=metadata,
        subscription_data=subscription_data,
    )
    return {
        "url": session.url,
        "session_id": session.id,
        "amount": float(plan["price"]),
        "currency": currency,
        "metadata": metadata,
    }


async def _resolve_price(item_type: str, item_id: str, quantity: int):
    if item_type == "membership":
        plan = await db.membership_plans.find_one({"id": item_id})
        if not plan: raise HTTPException(404, "Plan not found")
        return plan["price"], plan["currency"], {"plan_name": plan["name"]}
    if item_type == "program":
        program = await db.programs.find_one({"id": item_id})
        if not program: raise HTTPException(404, "Program not found")
        return program["price"], "usd", {"program_title": program["title"]}
    if item_type == "product":
        product = await db.products.find_one({"id": item_id})
        if not product: raise HTTPException(404, "Product not found")
        return product["price"] * quantity, product["currency"], {"product_title": product["title"], "quantity": str(quantity)}
    if item_type == "cart":
        # item_id holds the order_id; use the persisted order total (already enriched with items)
        order = await db.orders.find_one({"id": item_id})
        if not order: raise HTTPException(404, "Order not found")
        titles = ", ".join(i["title"] for i in order.get("items", []))[:400]
        return order["total"], order.get("currency", "usd"), {"order_id": item_id, "item_titles": titles}
    if item_type == "workshop_deposit":
        reg = await db.workshop_registrations.find_one({"id": item_id})
        if not reg: raise HTTPException(404, "Reservation not found")
        if reg.get("status") != "pending_deposit":
            raise HTTPException(400, f"Reservation is not awaiting a deposit (status={reg.get('status')})")
        return reg["deposit_eur"], "eur", {"reservation_id": item_id, "workshop_title": reg.get("workshop_title", ""), "payment_kind": "deposit"}
    if item_type == "workshop_balance":
        reg = await db.workshop_registrations.find_one({"id": item_id})
        if not reg: raise HTTPException(404, "Reservation not found")
        if reg.get("status") != "deposit_paid":
            raise HTTPException(400, f"Reservation not eligible for balance (status={reg.get('status')})")
        return reg["balance_eur"], "eur", {"reservation_id": item_id, "workshop_title": reg.get("workshop_title", ""), "payment_kind": "balance"}
    if item_type == "drop_in":
        p = {"price": 22.0}
        try:
            from routers.passes import PASS_CATALOG
            p = PASS_CATALOG.get("drop_in", p)
        except Exception:
            pass
        return p["price"], "usd", {"description": "Drop-in class", "pass_type": "drop_in", "credits": "1"}
    if item_type == "class_pack":
        p = {"price": 99.0}
        try:
            from routers.passes import PASS_CATALOG
            p = PASS_CATALOG.get("class_pack", p)
        except Exception:
            pass
        return p["price"], "usd", {"description": "5-class pack", "pass_type": "class_pack", "credits": "5"}
    if item_type == "private_session":
        return 120.0, "usd", {"description": "Private session"}
    if item_type == "bundle":
        bundle = await db.bundles.find_one({"id": item_id})
        if not bundle: raise HTTPException(404, "Bundle not found")
        return bundle["price"], (bundle.get("currency") or "eur"), {"bundle_title": bundle.get("title", "")}
    raise HTTPException(400, "Invalid item type")


async def _reserve_store_credit(user_id: str, amount: float) -> float:
    """Atomically reserve up to `amount` of the user's store credit. Returns the
    amount actually reserved (0 if none available). Credit is treated 1:1 as money."""
    u = await db.users.find_one({"id": user_id}, {"store_credit": 1})
    bal = round(float((u or {}).get("store_credit") or 0), 2)
    applied = round(min(bal, float(amount)), 2)
    if applied <= 0:
        return 0.0
    r = await db.users.update_one(
        {"id": user_id, "store_credit": {"$gte": applied}},
        {"$inc": {"store_credit": -applied}},
    )
    return applied if r.modified_count else 0.0


async def _release_store_credit(user_id: str, amount: float):
    if amount and amount > 0:
        await db.users.update_one({"id": user_id}, {"$inc": {"store_credit": round(float(amount), 2)}})


async def release_stranded_credit_tick():
    """Return reserved store credit for unpaid checkouts abandoned >45 min ago
    (safety net for users who close the Stripe/PayPal page without cancelling)."""
    from datetime import timedelta
    cutoff = (now_utc() - timedelta(minutes=45)).isoformat()
    cursor = db.payment_transactions.find({
        "payment_status": "initiated",
        "credit_applied": {"$gt": 0},
        "credit_released": {"$ne": True},
        "created_at": {"$lt": cutoff},
    })
    async for txn in cursor:
        await _release_store_credit(txn.get("user_id"), txn.get("credit_applied") or 0)
        await db.payment_transactions.update_one(
            {"id": txn["id"]}, {"$set": {"credit_released": True, "status": "expired"}}
        )


def _credit_eligible(item_type: str) -> bool:
    # Store credit applies to one-time purchases (not real Stripe subscriptions).
    return item_type in (
        "membership", "program", "product", "cart", "bundle",
        "workshop_deposit", "workshop_balance", "drop_in", "class_pack", "private_session",
    )


async def _fulfill_credit_only(*, user: dict, item_type: str, item_id: str, quantity: int,
                               currency: str, credit_applied: float, meta: dict):
    """When store credit fully covers the price, complete the purchase with no gateway."""
    txn = {
        "id": gen_id(), "session_id": f"credit_{gen_id()}",
        "provider": "credit",
        "user_id": user["id"], "user_email": user["email"],
        "amount": round(credit_applied, 2), "currency": currency,
        "credit_applied": round(credit_applied, 2),
        "item_type": item_type, "item_id": item_id,
        "quantity": quantity,
        "metadata": {"user_id": user["id"], "user_email": user["email"],
                     "item_type": item_type, "item_id": item_id,
                     "quantity": str(quantity), **(meta or {})},
        "payment_status": "paid", "status": "complete", "mode": "credit",
        "created_at": now_utc().isoformat(), "completed_at": now_utc().isoformat(),
    }
    await db.payment_transactions.insert_one(txn)
    await _fulfill_payment(txn)
    return txn


@api.post("/checkout/credit-release")
async def release_credit(request: Request, user: dict = Depends(get_current_user)):
    """Refund reserved store credit for an abandoned/cancelled unpaid checkout."""
    body = await request.json()
    session_id = (body or {}).get("session_id")
    if not session_id:
        raise HTTPException(400, "session_id required")
    txn = await db.payment_transactions.find_one({"session_id": session_id, "user_id": user["id"]})
    if not txn:
        raise HTTPException(404, "Transaction not found")
    applied = round(float(txn.get("credit_applied") or 0), 2)
    if txn.get("payment_status") == "paid" or txn.get("credit_released") or applied <= 0:
        return {"released": 0.0}
    await _release_store_credit(user["id"], applied)
    await db.payment_transactions.update_one({"session_id": session_id}, {"$set": {"credit_released": True}})
    fresh = await db.users.find_one({"id": user["id"]}, {"_id": 0, "store_credit": 1})
    return {"released": applied, "store_credit": round((fresh or {}).get("store_credit", 0) or 0, 2)}


@api.post("/checkout/session")
async def create_checkout(payload: CheckoutRequest, request: Request, user: dict = Depends(get_current_user)):
    # Memberships CAN go through Stripe Subscriptions (with trial) when the admin
    # explicitly enables it AND a real Stripe key is configured. Otherwise we fall
    # back to the safe one-time payment flow (customer pays for one full billing
    # cycle up-front; admin can extend manually).
    subs_enabled = bool(await get_setting("stripe_subscriptions_enabled"))
    if payload.item_type == "membership" and subs_enabled:
        plan = await db.membership_plans.find_one({"id": payload.item_id})
        if not plan:
            raise HTTPException(404, "Plan not found")
        try:
            session = await _create_subscription_session(user=user, plan=plan, origin_url=payload.origin_url)
        except stripe.error.StripeError as e:
            logger.exception(f"Stripe subscription creation failed: {e}")
            raise HTTPException(500, f"Stripe error: {e.user_message or str(e)}")
        await db.payment_transactions.insert_one({
            "id": gen_id(), "session_id": session["session_id"],
            "user_id": user["id"], "user_email": user["email"],
            "amount": session["amount"], "currency": session["currency"],
            "item_type": "membership", "item_id": payload.item_id,
            "quantity": 1, "metadata": session["metadata"],
            "payment_status": "initiated", "status": "open",
            "mode": "subscription",
            "trial_days": int(plan.get("trial_days") or 0),
            "created_at": now_utc().isoformat(),
        })
        return {"url": session["url"], "session_id": session["session_id"]}

    amount, currency, meta = await _resolve_price(payload.item_type, payload.item_id, payload.quantity)

    # Gift-card store credit: reserve and deduct from the amount to charge.
    credit_applied = 0.0
    if payload.apply_credit and _credit_eligible(payload.item_type):
        credit_applied = await _reserve_store_credit(user["id"], float(amount))
    charge_amount = round(float(amount) - credit_applied, 2)
    if credit_applied > 0 and charge_amount <= 0.009:
        # Credit fully covers it — no gateway needed.
        await _fulfill_credit_only(user=user, item_type=payload.item_type, item_id=payload.item_id,
                                   quantity=payload.quantity, currency=currency,
                                   credit_applied=credit_applied, meta=meta)
        return {"credit_only": True, "credit_applied": credit_applied}

    success_url = f"{payload.origin_url}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{payload.origin_url}/checkout/cancel?session_id={{CHECKOUT_SESSION_ID}}"
    metadata = {
        "user_id": user["id"], "user_email": user["email"],
        "item_type": payload.item_type, "item_id": payload.item_id,
        "quantity": str(payload.quantity), **meta, **(payload.metadata or {}),
    }
    try:
        session = await _create_onetime_session(
            amount=float(charge_amount), currency=currency,
            success_url=success_url, cancel_url=cancel_url, metadata=metadata,
            customer_email=user.get("email"),
            product_name=meta.get("product_name") or meta.get("title") or meta.get("name"),
        )
    except Exception:
        await _release_store_credit(user["id"], credit_applied)
        raise
    await db.payment_transactions.insert_one({
        "id": gen_id(), "session_id": session.id,
        "user_id": user["id"], "user_email": user["email"],
        "amount": float(charge_amount), "currency": currency,
        "credit_applied": credit_applied,
        "item_type": payload.item_type, "item_id": payload.item_id,
        "quantity": payload.quantity, "metadata": metadata,
        "payment_status": "initiated", "status": "open",
        "mode": "payment",
        "created_at": now_utc().isoformat(),
    })
    return {"url": session.url, "session_id": session.id}


@api.get("/checkout/status/{session_id}")
async def checkout_status(session_id: str, request: Request):
    txn = await db.payment_transactions.find_one({"session_id": session_id})
    if not txn:
        raise HTTPException(404, "Transaction not found")

    # Subscription-mode sessions: query Stripe directly (retrieve + expand subscription)
    # so we can reflect trial/active status accurately.
    if txn.get("mode") == "subscription":
        stripe.api_key = await _stripe_api_key()
        try:
            s = stripe.checkout.Session.retrieve(session_id, expand=["subscription"])
        except Exception as e:
            logger.warning(f"Stripe subscription status lookup failed for {session_id}: {e}")
            raise HTTPException(404, "Session not found at Stripe")
        sub = s.get("subscription")
        sub_status = sub["status"] if isinstance(sub, dict) else None  # trialing|active|past_due|canceled|...
        # For subscription sessions, "paid" means either the trial started OR first invoice succeeded.
        session_complete = s.get("status") == "complete"
        is_active = sub_status in ("trialing", "active")
        if session_complete and is_active and txn.get("payment_status") != "paid":
            await db.payment_transactions.update_one(
                {"session_id": session_id},
                {"$set": {
                    "payment_status": "paid", "status": "complete",
                    "stripe_subscription_id": (sub.get("id") if isinstance(sub, dict) else None),
                    "stripe_subscription_status": sub_status,
                    "completed_at": now_utc().isoformat(),
                }},
            )
            await _fulfill_payment(await db.payment_transactions.find_one({"session_id": session_id}))
        return {
            "status": s.get("status", "open"),
            "payment_status": "paid" if (session_complete and is_active) else "pending",
            "subscription_status": sub_status,
            "amount_total": s.get("amount_total", 0),
            "currency": s.get("currency", txn.get("currency", "usd")),
            "metadata": s.get("metadata", {}) or {},
        }

    stripe.api_key = await _stripe_api_key()
    try:
        status = stripe.checkout.Session.retrieve(session_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Stripe status lookup failed for {session_id}: {e}")
        raise HTTPException(404, "Session not found at Stripe")
    if txn.get("payment_status") != "paid" and status.payment_status == "paid":
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {"payment_status": status.payment_status, "status": status.status, "completed_at": now_utc().isoformat()}},
        )
        await _fulfill_payment(txn)
    else:
        await db.payment_transactions.update_one(
            {"session_id": session_id}, {"$set": {"payment_status": status.payment_status, "status": status.status}},
        )
    return {
        "status": status.status, "payment_status": status.payment_status,
        "amount_total": status.amount_total, "currency": status.currency, "metadata": dict(status.metadata or {}),
    }


async def _receipt_description(txn: dict) -> str:
    it = txn.get("item_type"); iid = txn.get("item_id")
    if it == "membership":
        plan = await db.membership_plans.find_one({"id": iid})
        tier = ((plan or {}).get("tier") or "").replace("_", " ")
        return f"{tier.title()} membership".strip() or "Membership"
    if it == "program":
        prog = await db.programs.find_one({"id": iid})
        return f"Program — {(prog or {}).get('title', 'Program')}"
    if it in ("product", "cart"):
        return "Shop order"
    if it == "workshop_deposit":
        return "Workshop / retreat deposit"
    if it == "workshop_balance":
        return "Workshop / retreat balance"
    if it == "drop_in":
        return "Drop-in class"
    if it == "class_pack":
        return "Class pack (5 classes)"
    return "Tony Yoga purchase"


async def _send_receipt(txn: dict):
    """Best-effort branded receipt email after a successful payment."""
    try:
        user = await db.users.find_one({"id": txn.get("user_id")})
        if not user or not user.get("email"):
            return
        from email_service import send_payment_receipt
        desc = await _receipt_description(txn)
        await send_payment_receipt(
            user["email"], desc, float(txn.get("amount", 0)),
            txn.get("currency", "usd"), txn.get("session_id"),
        )
    except Exception as e:
        logger.warning(f"receipt email skipped: {e}")


async def _fulfill_payment(txn: dict):
    item_type = txn["item_type"]; item_id = txn["item_id"]; user_id = txn["user_id"]
    # Safety: if the abandonment sweeper already refunded this txn's reserved credit
    # but the gateway payment landed late, re-consume that credit so it isn't double-spent.
    if txn.get("credit_released") and (txn.get("credit_applied") or 0) > 0:
        await db.users.update_one({"id": user_id}, {"$inc": {"store_credit": -round(float(txn["credit_applied"]), 2)}})
        await db.payment_transactions.update_one({"id": txn.get("id")}, {"$set": {"credit_released": False}})
    if item_type == "membership":
        plan = await db.membership_plans.find_one({"id": item_id})
        if not plan: return
        days_per_cycle = {"weekly": 7, "monthly": 30, "quarterly": 90, "yearly": 365}.get(plan["billing_cycle"], 30)
        trial_days = int(txn.get("trial_days") or plan.get("trial_days") or 0)
        is_trialing = txn.get("stripe_subscription_status") == "trialing"
        now = now_utc()
        # For trialing subs, end_date = now + trial; otherwise = now + full billing cycle.
        period_days = trial_days if is_trialing else days_per_cycle
        end_date = now + timedelta(days=period_days)
        # Referral reward (only when actual money has moved → skip if still in trial)
        if not is_trialing:
            user = await db.users.find_one({"id": user_id})
            if user and user.get("referred_by"):
                ref = await db.referrals.find_one({
                    "referrer_id": user["referred_by"], "referred_user_id": user_id, "reward_granted": False,
                })
                if ref:
                    referrer_sub = await db.subscriptions.find_one({"user_id": user["referred_by"], "status": "active"})
                    if referrer_sub:
                        end = datetime.fromisoformat(referrer_sub["end_date"]) + timedelta(days=30)
                        next_bill = datetime.fromisoformat(referrer_sub["next_billing_date"]) + timedelta(days=30)
                        await db.subscriptions.update_one(
                            {"id": referrer_sub["id"]},
                            {"$set": {"end_date": end.isoformat(), "next_billing_date": next_bill.isoformat()}},
                        )
                    else:
                        await db.referral_credits.insert_one({
                            "id": gen_id(), "user_id": user["referred_by"],
                            "days": 30, "active": True, "created_at": now_utc().isoformat(),
                        })
                    await db.referrals.update_one(
                        {"id": ref["id"]},
                        {"$set": {"status": "converted", "reward_granted": True, "converted_at": now_utc().isoformat()}},
                    )
        await db.subscriptions.update_one(
            {"user_id": user_id, "plan_id": item_id, "status": {"$in": ["active", "trialing"]}},
            {"$set": {
                "id": gen_id(), "user_id": user_id, "plan_id": item_id,
                "status": "trialing" if is_trialing else "active",
                "stripe_subscription_id": txn.get("stripe_subscription_id"),
                "start_date": now.isoformat(),
                "end_date": end_date.isoformat(),
                "next_billing_date": end_date.isoformat(),
                "trial_end_date": (now + timedelta(days=trial_days)).isoformat() if trial_days > 0 else None,
            }},
            upsert=True,
        )
    elif item_type == "program":
        await db.program_purchases.insert_one({
            "id": gen_id(), "user_id": user_id, "program_id": item_id,
            "purchased_at": now_utc().isoformat(),
        })
        # Enrollment record drives access checks + drip start date.
        await db.program_enrollments.update_one(
            {"user_id": user_id, "program_id": item_id},
            {"$setOnInsert": {"id": gen_id(), "user_id": user_id, "program_id": item_id,
                              "source": "purchase", "created_at": now_utc().isoformat()}},
            upsert=True,
        )
    elif item_type == "bundle":
        bundle = await db.bundles.find_one({"id": item_id}, {"_id": 0})
        for pid in (bundle or {}).get("program_ids", []):
            await db.program_enrollments.update_one(
                {"user_id": user_id, "program_id": pid},
                {"$setOnInsert": {"id": gen_id(), "user_id": user_id, "program_id": pid,
                                  "source": "bundle", "bundle_id": item_id, "created_at": now_utc().isoformat()}},
                upsert=True,
            )
    elif item_type == "product":
        # Decrement stock (physical only) and create a paid order.
        prod = await db.products.find_one({"id": item_id}, {"_id": 0})
        if prod and prod.get("type") != "ebook":
            await db.products.update_one({"id": item_id}, {"$inc": {"stock_qty": -int(txn.get("quantity", 1))}})
        await db.orders.insert_one({
            "id": gen_id(), "user_id": user_id,
            "items": [{"product_id": item_id, "quantity": txn.get("quantity", 1),
                       "title": (prod or {}).get("title")}],
            "total": txn["amount"], "currency": txn["currency"],
            "status": "paid", "created_at": now_utc().isoformat(),
        })
    elif item_type == "cart":
        # Mark the existing order as paid + decrement inventory for each line item.
        order_id = txn.get("metadata", {}).get("order_id") or txn.get("item_id")
        if order_id:
            order = await db.orders.find_one({"id": order_id})
            if order:
                for line in order.get("items", []):
                    pid = line.get("product_id"); qty = int(line.get("quantity", 1))
                    if pid:
                        prod = await db.products.find_one({"id": pid}, {"_id": 0, "type": 1})
                        if not prod or prod.get("type") != "ebook":
                            await db.products.update_one({"id": pid}, {"$inc": {"stock_qty": -qty}})
                await db.orders.update_one(
                    {"id": order_id},
                    {"$set": {"status": "paid", "paid_at": now_utc().isoformat()}},
                )
                # Part B: push paid cart order to Printful for POD fulfillment (best-effort).
                try:
                    from routers.printful import try_auto_fulfill_order
                    await try_auto_fulfill_order(order_id)
                except Exception as e:
                    logger.warning(f"printful auto-fulfill hook failed for {order_id}: {e}")
    elif item_type == "workshop_deposit":
        reservation_id = txn.get("metadata", {}).get("reservation_id") or txn.get("item_id")
        if reservation_id:
            await db.workshop_registrations.update_one(
                {"id": reservation_id},
                {"$set": {"status": "deposit_paid", "deposit_paid_at": now_utc().isoformat()}},
            )
            try:
                reg = await db.workshop_registrations.find_one({"id": reservation_id}, {"_id": 0})
                if reg:
                    from email_service import send_retreat_booking
                    await send_retreat_booking(reg, "deposit")
            except Exception as e:
                logger.warning(f"retreat deposit email failed for {reservation_id}: {e}")
    elif item_type == "workshop_balance":
        reservation_id = txn.get("metadata", {}).get("reservation_id") or txn.get("item_id")
        if reservation_id:
            await db.workshop_registrations.update_one(
                {"id": reservation_id},
                {"$set": {"status": "paid_in_full", "balance_paid_at": now_utc().isoformat()}},
            )
            try:
                reg = await db.workshop_registrations.find_one({"id": reservation_id}, {"_id": 0})
                if reg:
                    from email_service import send_retreat_booking
                    await send_retreat_booking(reg, "balance")
            except Exception as e:
                logger.warning(f"retreat balance email failed for {reservation_id}: {e}")
    elif item_type in ("drop_in", "class_pack"):
        credits = 1 if item_type == "drop_in" else 5
        await db.class_passes.update_one(
            {"user_id": user_id, "active": True},
            {"$inc": {"remaining": credits},
             "$setOnInsert": {"id": gen_id(), "user_id": user_id, "active": True, "created_at": now_utc().isoformat()}},
            upsert=True,
        )

    # Branded receipt (best-effort, respects the SMTP enable toggle).
    await _send_receipt(txn)


@api.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Official Stripe webhook. Verifies the signature when a webhook secret is configured,
    fulfills one-time payments (checkout.session.completed), and keeps subscriptions in sync.
    Idempotent: fulfillment only runs when the transaction is not already marked paid."""
    body = await request.body()
    sig = request.headers.get("Stripe-Signature")
    stripe.api_key = await _stripe_api_key()
    webhook_secret = await get_setting("stripe_webhook_secret") or os.environ.get("STRIPE_WEBHOOK_SECRET", "")

    if webhook_secret:
        try:
            event = stripe.Webhook.construct_event(body, sig, webhook_secret)
        except Exception as e:
            logger.warning(f"Stripe webhook signature verification failed: {e}")
            raise HTTPException(400, "Invalid webhook signature")
    else:
        # No secret configured (staging) — parse the body without verification.
        import json
        try:
            event = json.loads(body.decode("utf-8"))
        except Exception as e:
            logger.exception(f"Webhook parse error: {e}")
            raise HTTPException(400, "Invalid webhook")

    etype = event.get("type") if isinstance(event, dict) else event["type"]
    obj = (event.get("data", {}) or {}).get("object", {}) if isinstance(event, dict) else event["data"]["object"]

    try:
        # One-time payment completion (idempotent fulfillment).
        if etype in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
            session_id = obj.get("id")
            paid = obj.get("payment_status") == "paid" or obj.get("status") == "complete"
            if session_id and paid:
                txn = await db.payment_transactions.find_one({"session_id": session_id})
                if txn and txn.get("payment_status") != "paid":
                    await db.payment_transactions.update_one(
                        {"session_id": session_id},
                        {"$set": {"payment_status": "paid", "status": "complete", "completed_at": now_utc().isoformat()}},
                    )
                    await _fulfill_payment(txn)

        # Subscription lifecycle sync (trial → active, renewals, cancellations).
        elif etype in ("customer.subscription.updated", "customer.subscription.created", "customer.subscription.deleted"):
            sub = obj
            sub_id = sub.get("id")
            sub_status = sub.get("status")  # trialing | active | past_due | canceled | unpaid
            current_period_end = sub.get("current_period_end")  # unix ts
            update = {"status": sub_status if sub_status in ("trialing", "active") else "cancelled"}
            if current_period_end:
                end_iso = datetime.fromtimestamp(current_period_end).isoformat()
                update["end_date"] = end_iso
                update["next_billing_date"] = end_iso
            await db.subscriptions.update_many({"stripe_subscription_id": sub_id}, {"$set": update})
            logger.info(f"Subscription {sub_id} synced → {sub_status}")
    except Exception as e:
        logger.exception(f"Webhook handling error for {etype}: {e}")
        raise HTTPException(400, "Webhook handling failed")

    return {"received": True}
