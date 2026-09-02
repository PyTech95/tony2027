"""Tony Yoga API — thin application entrypoint.

Routers are registered via side-effect import: each router module attaches
endpoints to the shared `api` APIRouter imported from `core`.
"""
import os
import asyncio
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from core import api, client, db, logger, require_role, now_utc
from seed import seed
from fastapi import Request

# Register all routers (side-effect imports)
from routers import auth, scheduling, content, payments, referrals, admin, workshops, push, orders, submissions, settings, seed_tony, paypal, news, retreats, streaks, passes, wishlist, marketing, providers, bundles, assistant, zoom, broadcasts, leaderboard, giftcards, notifications, uploads, asanas, meditations, printful, quiz  # noqa: F401
from routers.push import send_reminders_tick
from routers.payments import release_stranded_credit_tick
from routers.retreats import send_balance_reminders_tick, expire_seat_offers_tick
from routers.marketing import instagram_sync_tick
from routers.broadcasts import broadcasts_publish_tick
from routers.zoom import zoom_recording_poll_tick

# Set on startup so /api/health can surface why programs=0 (bad MONGO_URL / seed exception).
_seed_ran: bool = False
_seed_error: str = ""


def _mask_mongo_url(url: str) -> str:
    """Strip credentials + return host-only for safe display in /health."""
    if not url:
        return ""
    try:
        # mongodb://user:pass@host:27017/db  →  host:27017
        without_scheme = url.split("://", 1)[-1]
        without_creds = without_scheme.split("@", 1)[-1] if "@" in without_scheme else without_scheme
        host = without_creds.split("/", 1)[0].split("?", 1)[0]
        return host
    except Exception:
        return "<unparseable>"


@api.get("/")
async def root():
    return {"ok": True, "service": "tony-yoga", "time": now_utc().isoformat()}


@api.get("/health")
async def health():
    """Deployment diagnostics. No auth — safe to hit from Hostinger, Vercel, curl, etc.
    Confirms MongoDB is reachable AND that the critical collections have content."""
    global _seed_ran, _seed_error
    result = {
        "ok": True,
        "time": now_utc().isoformat(),
        "db_name": os.environ.get("DB_NAME", ""),
        "mongo_host": _mask_mongo_url(os.environ.get("MONGO_URL", "")),
        "seed_ran": _seed_ran,
    }
    if _seed_error:
        result["seed_error"] = _seed_error
    try:
        await client.admin.command("ping")
        result["db_connected"] = True
        for coll in ("users", "programs", "membership_plans", "workshops", "class_templates", "class_instances", "products", "orders", "bookings"):
            try:
                result[f"count_{coll}"] = await db[coll].count_documents({})
            except Exception as e:
                result[f"count_{coll}"] = f"ERR: {e}"
    except Exception as e:
        result["ok"] = False
        result["db_connected"] = False
        result["db_error"] = str(e)
    return result


@api.post("/admin/reseed")
async def admin_reseed(request: Request):
    """Re-run the idempotent seed. Admin-only.
    Only creates missing content — safe to call anytime after a fresh Hostinger/Vercel
    deploy where the boot-time seed was skipped because Mongo wasn't reachable."""
    await require_role(request, ["admin"])
    global _seed_ran, _seed_error
    before = {c: await db[c].count_documents({}) for c in ("users", "programs", "membership_plans", "workshops", "class_templates", "products")}
    try:
        await seed()
        _seed_ran = True
        _seed_error = ""
    except Exception as e:
        _seed_error = f"Reseed exception: {e}"
        logger.exception(f"Reseed failed: {e}")
        return {"ok": False, "error": str(e), "before": before}
    after = {c: await db[c].count_documents({}) for c in ("users", "programs", "membership_plans", "workshops", "class_templates", "products")}
    return {"ok": True, "before": before, "after": after,
            "created": {c: after[c] - before[c] for c in before}}


app = FastAPI(title="Tony Yoga API")
app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=False,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    # Test DB connectivity FIRST so a missing/misconfigured MONGO_URL fails loudly
    # instead of quietly leaving collections empty.
    global _seed_ran, _seed_error
    try:
        await client.admin.command("ping")
        logger.info(f"MongoDB reachable at {_mask_mongo_url(os.environ.get('MONGO_URL', ''))} (db={os.environ.get('DB_NAME','')})")
    except Exception as e:
        _seed_error = f"MongoDB unreachable at startup: {e}"
        logger.error(
            f"MongoDB NOT REACHABLE — programs and content will be empty. "
            f"Check MONGO_URL in .env. Host: {_mask_mongo_url(os.environ.get('MONGO_URL',''))} — Error: {e}"
        )
        return  # skip seed — nothing to seed into

    try:
        await seed()
        _seed_ran = True
        logger.info("Seed complete — Tony Yoga API ready")
    except Exception as e:
        _seed_error = f"Seed exception: {e}"
        logger.exception(f"Seed failed (app will still start): {e}")

    # Initialise object storage (retreat photo uploads). Best-effort.
    try:
        from routers.uploads import init_storage
        init_storage()
        logger.info("Object storage initialised")
    except Exception as e:
        logger.warning(f"Object storage init failed (uploads will retry on first use): {e}")

    # Enable Stripe (one-time payments via the official Stripe SDK).
    # Subscriptions require a real Stripe key — kept OFF; memberships still
    # process as one-time payments (customer pays for one full billing cycle).
    try:
        from routers.settings import SETTINGS_DOC_ID
        await db.app_settings.update_one(
            {"_id": SETTINGS_DOC_ID},
            {"$set": {"stripe_subscriptions_enabled": False, "stripe_enabled": True},
             "$setOnInsert": {"_id": SETTINGS_DOC_ID}},
            upsert=True,
        )
    except Exception as e:
        logger.warning(f"Could not set stripe settings: {e}")

    # Kick off background reminder loop (best-effort, silent no-op if VAPID missing)
    asyncio.create_task(_reminder_loop())


async def _reminder_loop():
    """Every 60s, send 30-min-before-class push reminders + 7-day-before balance reminders."""
    while True:
        try:
            await send_reminders_tick()
        except Exception as e:
            logger.warning(f"class reminder tick failed: {e}")
        try:
            await send_balance_reminders_tick()
        except Exception as e:
            logger.warning(f"balance reminder tick failed: {e}")
        try:
            await expire_seat_offers_tick()
        except Exception as e:
            logger.warning(f"seat offer expiry tick failed: {e}")
        try:
            await instagram_sync_tick()
        except Exception as e:
            logger.warning(f"instagram sync tick failed: {e}")
        try:
            await broadcasts_publish_tick()
        except Exception as e:
            logger.warning(f"broadcasts publish tick failed: {e}")
        try:
            await zoom_recording_poll_tick()
        except Exception as e:
            logger.warning(f"zoom recording poll tick failed: {e}")
        try:
            await release_stranded_credit_tick()
        except Exception as e:
            logger.warning(f"stranded credit release tick failed: {e}")
        await asyncio.sleep(60)


@app.on_event("shutdown")
async def on_shutdown():
    client.close()
