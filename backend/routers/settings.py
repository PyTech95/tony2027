"""App-wide settings (payments + video) editable from the Admin panel.

Stored as a single document in `app_settings`. DB values OVERRIDE the equivalent
.env variables at runtime, so non-developers can swap keys without redeploying.
Sensitive fields are masked when read and preserved when the masked value is
sent back (i.e. the UI sends "••••••••abcd" and we keep the real value).
"""
import os
from typing import Any, Dict, Optional
from fastapi import Request, HTTPException

from core import api, db, require_role, now_utc, gen_id


SETTINGS_DOC_ID = "global"

# Fields treated as secrets: masked on read, only overwritten when explicitly set.
SECRET_FIELDS = {
    "stripe_secret_key",
    "stripe_webhook_secret",
    "paypal_client_secret",
    "vimeo_access_token",
    "mux_token_secret",
    "smtp_password",
    "vapid_private_key",
    "instagram_access_token",
    "zoom_client_secret",
    "twilio_auth_token",
    "openai_api_key",
}

# Map of setting -> env var to fall back on when the DB value is empty.
ENV_FALLBACK = {
    "stripe_publishable_key": "STRIPE_PUBLISHABLE_KEY",
    "stripe_secret_key": "STRIPE_API_KEY",
    "stripe_webhook_secret": "STRIPE_WEBHOOK_SECRET",
    "paypal_client_id": "PAYPAL_CLIENT_ID",
    "paypal_client_secret": "PAYPAL_CLIENT_SECRET",
    "vimeo_access_token": "VIMEO_ACCESS_TOKEN",
    "mux_token_id": "MUX_TOKEN_ID",
    "mux_token_secret": "MUX_TOKEN_SECRET",
    "smtp_host": "SMTP_HOST",
    "smtp_port": "SMTP_PORT",
    "smtp_user": "SMTP_USER",
    "smtp_password": "SMTP_PASSWORD",
    "sender_email": "SENDER_EMAIL",
    "sender_name": "SENDER_NAME",
    "vapid_public_key": "VAPID_PUBLIC_KEY",
    "vapid_private_key": "VAPID_PRIVATE_KEY",
    "vapid_claim_email": "VAPID_CLAIM_EMAIL",
    "zoom_account_id": "ZOOM_ACCOUNT_ID",
    "zoom_client_id": "ZOOM_CLIENT_ID",
    "zoom_client_secret": "ZOOM_CLIENT_SECRET",
    "zoom_host_user_id": "ZOOM_HOST_USER_ID",
    "twilio_account_sid": "TWILIO_ACCOUNT_SID",
    "twilio_auth_token": "TWILIO_AUTH_TOKEN",
    "twilio_whatsapp_from": "TWILIO_WHATSAPP_FROM",
    "openai_api_key": "OPENAI_API_KEY",
}

DEFAULT_SETTINGS: Dict[str, Any] = {
    # ---- Payments ----
    "default_currency": "usd",            # usd | eur | gbp
    "tax_rate_percent": 0.0,
    "min_order_amount": 0.0,
    "stripe_enabled": True,
    "stripe_mode": "test",                # test | live
    "stripe_subscriptions_enabled": False,  # when True, memberships use recurring subscriptions with trial. Requires real Stripe key.
    "stripe_publishable_key": "",
    "stripe_secret_key": "",
    "stripe_webhook_secret": "",
    "paypal_enabled": False,
    "paypal_mode": "sandbox",             # sandbox | live
    "paypal_client_id": "",
    "paypal_client_secret": "",
    "paypal_webhook_id": "",
    "crypto_enabled": False,
    "success_url_path": "/checkout/success",
    "cancel_url_path": "/checkout/cancel",
    # ---- Email (SMTP) ----
    "email_enabled": False,
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_user": "",
    "smtp_password": "",
    "sender_email": "",
    "sender_name": "Tony Yoga",
    # ---- Web Push (VAPID) ----
    "push_enabled": False,
    "vapid_public_key": "",
    "vapid_private_key": "",
    "vapid_claim_email": "mailto:tony@tonysanchezyoga.com",
    "reminder_lead_minutes": 30,
    # ---- Zoom (live classes + cloud recordings) ----
    "zoom_enabled": False,
    "zoom_account_id": "",
    "zoom_client_id": "",
    "zoom_client_secret": "",
    "zoom_host_user_id": "",
    "recording_replay_days": 3,      # default replay window for class recordings
    # ---- WhatsApp (Twilio) notifications ----
    "whatsapp_enabled": False,
    "twilio_account_sid": "",
    "twilio_auth_token": "",
    "twilio_whatsapp_from": "",      # e.g. whatsapp:+14155238886 (Twilio sandbox)
    # ---- Video ----
    "default_video_provider": "youtube",  # youtube | vimeo | mux
    "vimeo_access_token": "",
    "mux_token_id": "",
    "mux_token_secret": "",
    "video_autoplay": False,
    "video_default_quality": "auto",      # auto | 480p | 720p | 1080p
    "video_allow_downloads": False,
    "video_drm_enabled": False,
    "video_default_duration_minutes": 30,
    "video_watermark_text": "",
    # ---- Social links (footer + about pages) ----
    "social_facebook": "https://www.facebook.com/TonYoga.online/",
    "social_instagram": "https://www.instagram.com/tonyoga_school/",
    "social_youtube": "https://www.youtube.com/channel/UCrOeMWIAVwYhPwwF5cQZk3g",
    "social_linkedin": "https://www.linkedin.com/in/tonysanchezyoga/",
    "social_whatsapp": "",
    "social_tiktok": "",
    # ---- Marketing hero testimonial ----
    "hero_testimonial": {},               # {video_url, poster_url, name, role, headline}
    # ---- Instagram feed (homepage reels) ----
    "reels_enabled": True,                # show/hide the Instagram reels section
    "instagram_reels": [],                # list of {shortcode, caption}; empty → curated defaults
    "instagram_auto_sync": False,         # auto-pull latest reels via Meta Graph API
    "instagram_user_id": "",              # IG professional account id
    "instagram_access_token": "",         # long-lived IG User token (secret)
    "instagram_last_sync": "",            # ISO timestamp of last successful sync
    "instagram_last_error": "",           # last sync error (for admin visibility)
    # ---- Printful fulfillment (Part B) ----
    "printful_fulfill_enabled": True,     # auto-submit paid Printful orders (only fires on live payments)
    # ---- AI assistant (homepage chat + voice) ----
    "assistant_enabled": True,
    "assistant_greeting": "Hi, I'm Tony's assistant. How can I help you find the right yoga path today?",
    "assistant_popup_delay": 8,           # seconds before the popup appears on the homepage
    # OpenAI key powers chat + voice (Whisper STT + TTS) when self-hosting off the Emergent platform.
    # When empty, the app falls back to the Emergent universal key (works only on Emergent hosting).
    "openai_api_key": "",
    "assistant_openai_model": "gpt-4o-mini",
}

# Fields safe to expose to unauthenticated clients (frontend bootstrapping).
PUBLIC_FIELDS = {
    "default_currency",
    "stripe_enabled",
    "stripe_publishable_key",
    "stripe_subscriptions_enabled",
    "paypal_enabled",
    "paypal_mode",
    "crypto_enabled",
    "tax_rate_percent",
    "min_order_amount",
    "default_video_provider",
    "video_autoplay",
    "video_default_quality",
    "video_allow_downloads",
    "video_watermark_text",
    "social_facebook",
    "social_instagram",
    "social_youtube",
    "social_linkedin",
    "social_whatsapp",
    "social_tiktok",
    "hero_testimonial",
    "reels_enabled",
    "assistant_enabled",
    "assistant_greeting",
    "assistant_popup_delay",
    "social_whatsapp",
}


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 6:
        return "••••"
    return "•" * 8 + value[-4:]


def _is_masked(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("•")


async def get_all_settings() -> Dict[str, Any]:
    """Return merged settings: defaults <- DB. Does NOT apply env fallback."""
    doc = await db.app_settings.find_one({"_id": SETTINGS_DOC_ID}) or {}
    merged = {**DEFAULT_SETTINGS}
    for k, v in doc.items():
        if k.startswith("_"):
            continue
        merged[k] = v
    return merged


async def get_setting(key: str) -> Any:
    """Read a single effective setting. Empty DB values fall back to ENV."""
    settings = await get_all_settings()
    val = settings.get(key)
    if (val is None or val == "") and key in ENV_FALLBACK:
        return os.environ.get(ENV_FALLBACK[key], "")
    return val


# ----------------------------------------------------------------------------
# Endpoints
# ----------------------------------------------------------------------------
@api.get("/admin/settings")
async def admin_get_settings(request: Request):
    await require_role(request, ["admin"])
    settings = await get_all_settings()
    out: Dict[str, Any] = {}
    for k, v in settings.items():
        if k in SECRET_FIELDS:
            # Compute effective value (DB or env) so we can show "is configured"
            effective = v or os.environ.get(ENV_FALLBACK.get(k, ""), "")
            out[k] = _mask(str(effective))
            out[f"{k}_set"] = bool(effective)
            out[f"{k}_from_env"] = bool(not v and os.environ.get(ENV_FALLBACK.get(k, ""), ""))
        elif k in ENV_FALLBACK:
            # Non-secret with env fallback (e.g. stripe publishable key) — show full value.
            effective = v or os.environ.get(ENV_FALLBACK[k], "")
            out[k] = effective
            out[f"{k}_from_env"] = bool(not v and os.environ.get(ENV_FALLBACK[k], ""))
        else:
            out[k] = v
    return out


@api.patch("/admin/settings")
async def admin_patch_settings(payload: Dict[str, Any], request: Request):
    admin = await require_role(request, ["admin"])
    # Validate Stripe key formats up-front (reject obvious typos before they break checkout).
    _prefixes = {"stripe_secret_key": "sk_", "stripe_publishable_key": "pk_", "stripe_webhook_secret": "whsec_"}
    for k, pfx in _prefixes.items():
        v = payload.get(k)
        if isinstance(v, str) and v and v != "__clear__" and not _is_masked(v) and not v.startswith(pfx):
            raise HTTPException(400, f"{k} must start with '{pfx}'")
    update: Dict[str, Any] = {}
    for k, v in payload.items():
        if k not in DEFAULT_SETTINGS:
            continue
        # Explicit clear sentinel for secrets ("__clear__" wipes the stored value).
        if k in SECRET_FIELDS and v == "__clear__":
            update[k] = ""
            continue
        # Ignore masked or empty values for secret fields (would wipe real key).
        if k in SECRET_FIELDS and (_is_masked(v) or v in (None, "")):
            continue
        # Light type coercion
        default_v = DEFAULT_SETTINGS[k]
        if isinstance(default_v, bool):
            update[k] = bool(v)
        elif isinstance(default_v, int) and not isinstance(default_v, bool):
            try:
                update[k] = int(v)
            except (TypeError, ValueError):
                continue
            if k == "reminder_lead_minutes":
                update[k] = max(5, min(240, update[k]))
        elif isinstance(default_v, float):
            try:
                update[k] = float(v)
            except (TypeError, ValueError):
                continue
        else:
            update[k] = v
    if not update:
        return {"updated": 0, "warnings": []}
    update["_updated_by"] = admin["id"]
    update["_updated_at"] = now_utc().isoformat()
    await db.app_settings.update_one(
        {"_id": SETTINGS_DOC_ID},
        {"$set": update, "$setOnInsert": {"_id": SETTINGS_DOC_ID}},
        upsert=True,
    )
    real_keys = [k for k in update if not k.startswith("_")]
    await _write_audit(admin, real_keys)
    # Live-mode / test-key mismatch warning (non-blocking).
    warnings = []
    eff_mode = await get_setting("stripe_mode")
    eff_secret = await get_setting("stripe_secret_key")
    if eff_mode == "live" and isinstance(eff_secret, str) and eff_secret.startswith("sk_test_"):
        warnings.append("Stripe is set to LIVE mode but the secret key is a test key (sk_test_). Real charges will fail.")
    if eff_mode == "live" and not eff_secret:
        warnings.append("Stripe is set to LIVE mode but no secret key is configured.")
    return {"updated": len(real_keys), "keys": real_keys, "warnings": warnings}


async def _write_audit(admin: dict, keys: list):
    """Append an audit entry. Records which keys changed and by whom — never the values."""
    if not keys:
        return
    await db.settings_audit.insert_one({
        "id": gen_id(),
        "admin_id": admin.get("id"),
        "admin_email": admin.get("email"),
        "keys": keys,
        "secret_changed": [k for k in keys if k in SECRET_FIELDS],
        "at": now_utc().isoformat(),
    })


@api.get("/settings/public")
async def public_settings():
    """Read-only public-safe settings (no secrets, no auth required)."""
    settings = await get_all_settings()
    return {k: settings[k] for k in PUBLIC_FIELDS if k in settings}


@api.post("/admin/email/test")
async def admin_test_email(payload: Dict[str, Any], request: Request):
    """Send a test email to verify the configured SMTP settings work."""
    admin = await require_role(request, ["admin"])
    to = (payload.get("to") or admin.get("email") or "").strip()
    if not to:
        return {"ok": False, "error": "No recipient address."}
    from email_service import send_test_email
    ok = await send_test_email(to)
    return {"ok": ok, "to": to,
            "error": None if ok else "Send failed — check SMTP host, port, user and app password."}


@api.post("/admin/whatsapp/test")
async def admin_test_whatsapp(payload: Dict[str, Any], request: Request):
    """Send a test WhatsApp message to verify Twilio settings."""
    await require_role(request, ["admin"])
    to = (payload.get("to") or "").strip()
    if not to:
        return {"ok": False, "error": "Enter a WhatsApp number (E.164, e.g. +34600123456)."}
    from whatsapp_service import whatsapp_enabled, send_whatsapp
    if not await whatsapp_enabled():
        return {"ok": False, "error": "WhatsApp is not configured. Add Twilio SID, token and From number."}
    ok = await send_whatsapp(to, "Tony Yoga test message — your WhatsApp alerts are working. 🧘")
    return {"ok": ok, "to": to, "error": None if ok else "Send failed — check Twilio credentials and the From number."}


@api.post("/admin/push/generate-vapid")
async def admin_generate_vapid(request: Request):
    """Generate a fresh VAPID keypair, store it, and enable web push."""
    admin = await require_role(request, ["admin"])
    from routers.push import generate_vapid_keys
    private_key, public_key = generate_vapid_keys()
    await db.app_settings.update_one(
        {"_id": SETTINGS_DOC_ID},
        {"$set": {
            "vapid_private_key": private_key,
            "vapid_public_key": public_key,
            "push_enabled": True,
            "_updated_by": admin["id"],
            "_updated_at": now_utc().isoformat(),
        }, "$setOnInsert": {"_id": SETTINGS_DOC_ID}},
        upsert=True,
    )
    await _write_audit(admin, ["vapid_public_key", "vapid_private_key", "push_enabled"])
    return {"ok": True, "public_key": public_key}


@api.get("/admin/settings/audit")
async def admin_settings_audit(request: Request):
    """Recent history of settings changes (who + which keys + when). Admin only."""
    await require_role(request, ["admin"])
    rows = await db.settings_audit.find({}, {"_id": 0}).sort("at", -1).to_list(50)
    return rows
