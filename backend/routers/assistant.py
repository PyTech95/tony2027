"""Tony's virtual assistant — homepage chat (+ browser voice on the client).

Uses the Emergent universal key via emergentintegrations (Claude Sonnet 4.6).
Captures leads and hands hot leads off to WhatsApp via a wa.me deep link.
"""
import os
import base64
import tempfile
from typing import Optional, List
from urllib.parse import quote
from dotenv import load_dotenv
from fastapi import Request, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel, EmailStr

from core import api, db, gen_id, now_utc, logger, require_role, get_optional_user
from routers.settings import get_setting

load_dotenv()
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")
ASSISTANT_MODEL = ("anthropic", "claude-sonnet-4-6")


async def _openai_key() -> Optional[str]:
    """Admin-configured OpenAI key (or OPENAI_API_KEY env). Preferred on a self-hosted VPS."""
    try:
        k = await get_setting("openai_api_key")
    except Exception:
        k = None
    return (k or "").strip() or None


def _openai_client(key: str):
    from openai import AsyncOpenAI  # lazy import
    return AsyncOpenAI(api_key=key, timeout=60.0, max_retries=2)


CAPPED_REPLY = ("I've helped a lot of people today and need a short rest. "
                "Please try again tomorrow, or reach Tony's team on WhatsApp. 🙏")


async def _usage_today() -> tuple:
    """(today_iso, count) of assistant AI turns used today."""
    today = now_utc().date().isoformat()
    doc = await db.assistant_usage.find_one({"_id": today}) or {}
    return today, int(doc.get("count", 0))


async def _usage_ok() -> bool:
    try:
        limit = int(await get_setting("assistant_daily_limit") or 0)
    except Exception:
        limit = 0
    if limit <= 0:
        return True
    _, count = await _usage_today()
    return count < limit


async def _bump_usage():
    today = now_utc().date().isoformat()
    await db.assistant_usage.update_one(
        {"_id": today}, {"$inc": {"count": 1}, "$set": {"date": today}}, upsert=True,
    )

PERSONA = (
    "You are Tony's Assistant — the warm, knowledgeable voice guide for Tony Sanchez Yoga, "
    "led by Tony Sanchez, a master teacher with ~50 years on the mat (Ghosh/Bikram lineage), based in Málaga, Spain. "
    "This is a SPOKEN, hands-free conversation, so keep every reply SHORT and natural — 1 to 3 sentences, no lists, "
    "no markdown, no emojis. Sound calm, friendly and human. Always finish with a brief question to keep the "
    "conversation flowing, unless the person is saying goodbye. "
    "Use ONLY the catalog facts below — never invent prices, dates, links or courses. If you don't know, say so and "
    "offer to take their name and email so Tony's team can follow up (only mention WhatsApp if the visitor asks). Recommend the best-fit next step: Core 26+ for beginners, "
    "Core 40 to progress, Core 84 Asana Mastery for advanced; live Zoom classes; meditations & breathwork; the shop and books; "
    "retreats; or a membership. When someone shows real interest, gently offer to take their name and email so Tony's team can follow up. "
    "If the person says 'no', 'nothing', 'that's all', 'bye' or similar, warmly wish them well in one short sentence and stop."
)


class ChatIn(BaseModel):
    session_id: Optional[str] = None
    message: str


class LeadIn(BaseModel):
    session_id: Optional[str] = None
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    channel: Optional[str] = "whatsapp"
    goal: Optional[str] = None
    interest: Optional[str] = None


async def _catalog_text() -> str:
    lines: List[str] = []
    def _money(v) -> str:
        try: n = float(v or 0)
        except Exception: n = 0.0
        return (f"{n:.2f}".rstrip("0").rstrip("."))
    TIER_LABEL = {"online_only": "Essential (online)", "online_inperson": "Unlimited (online + in-person)", "vip": "Annual VIP"}
    def _plan_name(m) -> str:
        nm = m.get("name") or m.get("title") or ""
        if not nm or str(nm).startswith("i18n:"):
            return TIER_LABEL.get(m.get("tier"), (m.get("tier") or "Membership").replace("_", " ").title())
        return nm
    try:
        progs = await db.programs.find({}, {"_id": 0, "title": 1, "level": 1, "price": 1, "price_model": 1, "description": 1, "duration_weeks": 1}).to_list(50)
        if progs:
            lines.append("COURSES (on-demand programs):")
            for p in progs:
                price = "free" if p.get("price_model") == "free" else (f"€{_money(p.get('price'))}" + (" or included with a membership" if p.get("price_model") == "membership" else " one-time"))
                dur = f"{p.get('duration_weeks')} weeks, " if p.get("duration_weeks") else ""
                desc = (p.get("description") or "")[:100]
                lines.append(f"- {p.get('title')} ({dur}{p.get('level')}, {price}): {desc}")
    except Exception:
        pass
    try:
        plans = await db.membership_plans.find({"is_active": True}, {"_id": 0, "name": 1, "title": 1, "price": 1, "billing_cycle": 1, "tier": 1}).to_list(20)
        if plans:
            lines.append("MEMBERSHIPS:")
            for m in plans:
                lines.append(f"- {_plan_name(m)}: €{_money(m.get('price'))}/{m.get('billing_cycle', 'month')}")
    except Exception:
        pass
    lines.append("CLASS PASSES: Drop-in class €22 (1 credit); 5-class pack €99 (never expires). Live Zoom classes are on the Schedule page.")
    try:
        works = await db.workshops.find({"is_active": True}, {"_id": 0, "title": 1, "start_date": 1, "deposit_eur": 1, "location": 1}).sort("start_date", 1).to_list(10)
        if works:
            lines.append("RETREATS:")
            for w in works:
                when = ""
                if w.get("start_date"):
                    try: when = " · " + str(w["start_date"])[:7]
                    except Exception: when = ""
                dep = f", deposit €{_money(w.get('deposit_eur'))}" if w.get("deposit_eur") else ""
                loc = f" in {w.get('location')}" if w.get("location") else ""
                lines.append(f"- {w.get('title')}{loc}{when}{dep}")
    except Exception:
        pass
    try:
        meds = await db.meditations.count_documents({"is_published": True})
        if meds:
            lines.append(f"MEDITATION & BREATHWORK: {meds} guided audio/video sessions (meditation, breathwork, yoga nidra), filterable by focus & length.")
    except Exception:
        pass
    try:
        books = await db.products.find({"category": "books", "visible": {"$ne": False}}, {"_id": 0, "title": 1, "price": 1, "type": 1}).to_list(20)
        if books:
            lines.append("BOOKS & READING:")
            for b in books:
                kind = "eBook, instant download here" if b.get("type") == "ebook" else "print, on Amazon"
                lines.append(f"- {b.get('title')} (€{_money(b.get('price'))}, {kind})")
    except Exception:
        pass
    lines.append("SHOP also has mats, blocks, apparel, posters. Payment: card or PayPal; gift-card store credit can be applied at checkout. Not sure where to start? The 'Find Your Path' quiz recommends a program.")
    return "\n".join(lines)


@api.get("/assistant/config")
async def assistant_config():
    return {
        "enabled": (await get_setting("assistant_enabled")) is not False,
        "greeting": (await get_setting("assistant_greeting")) or "Hi, I'm Tony's assistant. How can I help you find the right yoga path today?",
        "popup_delay": int((await get_setting("assistant_popup_delay")) or 8),
        "whatsapp": (await get_setting("social_whatsapp")) or "",
    }


@api.get("/admin/assistant/usage")
async def admin_assistant_usage(request: Request):
    """Today's AI-turn count vs the configured daily cap (for the admin guardrail UI)."""
    await require_role(request, ["admin"])
    today, count = await _usage_today()
    try:
        limit = int(await get_setting("assistant_daily_limit") or 0)
    except Exception:
        limit = 0
    return {"date": today, "count": count, "limit": limit}


@api.post("/assistant/chat")
async def assistant_chat(payload: ChatIn, user: Optional[dict] = Depends(get_optional_user)):
    if (await get_setting("assistant_enabled")) is False:
        raise HTTPException(403, "Assistant is disabled.")
    msg = (payload.message or "").strip()
    if not msg:
        raise HTTPException(400, "Empty message.")
    if not await _usage_ok():
        sid = payload.session_id or gen_id()
        return {"session_id": sid, "reply": CAPPED_REPLY, "capped": True}
    sid, reply_text = await _generate_reply(payload.session_id, msg, user)
    return {"session_id": sid, "reply": reply_text}


async def _generate_reply(session_id: Optional[str], msg: str, user: Optional[dict]) -> tuple:
    """Shared assistant brain used by both text chat and voice. Returns (session_id, reply)."""
    sid = session_id or gen_id()
    session = await db.chatbot_sessions.find_one({"id": sid}, {"_id": 0})
    history: List[dict] = (session or {}).get("messages", [])

    reply_text = "I'm here to help! Could you tell me a bit about your goals — flexibility, stress relief, or building strength?"
    system = PERSONA + "\n\n" + await _catalog_text()
    okey = await _openai_key()
    if okey:
        # Self-host path: user's own OpenAI key (chat + voice all on one key).
        try:
            client = _openai_client(okey)
            messages = [{"role": "system", "content": system}]
            for m in history[-8:]:
                messages.append({"role": "assistant" if m.get("role") == "assistant" else "user", "content": m.get("text", "")})
            messages.append({"role": "user", "content": msg})
            model = (await get_setting("assistant_openai_model")) or "gpt-4o-mini"
            comp = await client.chat.completions.create(model=model, messages=messages, temperature=0.4, max_tokens=220)
            reply_text = (comp.choices[0].message.content or "").strip() or reply_text
            await client.close()
        except Exception as e:
            logger.warning(f"assistant chat (openai) failed: {e}")
    elif EMERGENT_LLM_KEY:
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage  # type: ignore
            convo = "\n".join(f"{m['role'].upper()}: {m['text']}" for m in history[-8:])
            prompt = (f"Conversation so far:\n{convo}\n\n" if convo else "") + f"VISITOR: {msg}\n\nReply as the assistant:"
            chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"assist-{sid}", system_message=system).with_model(*ASSISTANT_MODEL)
            resp = await chat.send_message(UserMessage(text=prompt))
            reply_text = str(resp).strip() or reply_text
        except Exception as e:
            logger.warning(f"assistant chat failed: {e}")

    if okey or EMERGENT_LLM_KEY:
        await _bump_usage()

    now = now_utc().isoformat()
    new_msgs = history + [
        {"role": "visitor", "text": msg, "at": now},
        {"role": "assistant", "text": reply_text, "at": now},
    ]
    await db.chatbot_sessions.update_one(
        {"id": sid},
        {"$set": {"messages": new_msgs[-40:], "updated_at": now, "user_id": (user or {}).get("id")},
         "$setOnInsert": {"id": sid, "created_at": now}},
        upsert=True,
    )
    return sid, reply_text


async def _tts_base64(text: str, voice: Optional[str] = None) -> str:
    """Synthesize spoken audio (mp3) as base64. Prefers the admin OpenAI key, else Emergent. '' on failure."""
    if not text.strip():
        return ""
    if not voice:
        voice = (await get_setting("assistant_voice")) or "nova"
    okey = await _openai_key()
    if okey:
        try:
            client = _openai_client(okey)
            resp = await client.audio.speech.create(model="tts-1", voice=voice, input=text[:4000], response_format="mp3")
            data = resp.content
            await client.close()
            return base64.b64encode(data).decode("ascii")
        except Exception as e:
            logger.warning(f"assistant TTS (openai) failed: {e}")
            return ""
    if EMERGENT_LLM_KEY:
        try:
            from emergentintegrations.llm.openai import OpenAITextToSpeech  # type: ignore
            tts = OpenAITextToSpeech(api_key=EMERGENT_LLM_KEY)
            return await tts.generate_speech_base64(text=text[:900], voice=voice, response_format="mp3")
        except Exception as e:
            logger.warning(f"assistant TTS failed: {e}")
    return ""


class TTSIn(BaseModel):
    text: str
    voice: Optional[str] = None


@api.post("/assistant/tts")
async def assistant_tts(payload: TTSIn):
    if (await get_setting("assistant_enabled")) is False:
        raise HTTPException(403, "Assistant is disabled.")
    audio = await _tts_base64(payload.text or "", payload.voice)
    return {"audio_base64": audio, "mime": "audio/mpeg"}


@api.post("/assistant/voice")
async def assistant_voice(
    audio: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    speak: Optional[bool] = Form(True),
    user: Optional[dict] = Depends(get_optional_user),
):
    """Voice turn: transcribe mic audio (Whisper), get an assistant reply, and
    return spoken audio (OpenAI TTS)."""
    if (await get_setting("assistant_enabled")) is False:
        raise HTTPException(403, "Assistant is disabled.")
    okey = await _openai_key()
    if not okey and not EMERGENT_LLM_KEY:
        raise HTTPException(503, "Voice is not available right now.")
    if not await _usage_ok():
        # Daily cap reached — skip all paid calls (STT/LLM/TTS) and reply gracefully.
        return {"session_id": session_id or gen_id(), "transcript": "", "reply": CAPPED_REPLY,
                "audio_base64": "", "mime": "audio/mpeg", "capped": True}
    raw = await audio.read()
    if not raw:
        raise HTTPException(400, "Empty audio.")
    # Whisper needs a file with a recognised extension; browsers send webm/ogg.
    suffix = ".webm"
    name = (audio.filename or "").lower()
    for ext in (".webm", ".mp3", ".m4a", ".wav", ".mp4", ".ogg"):
        if name.endswith(ext):
            suffix = ".ogg" if ext == ".ogg" else ext
            break
    transcript = ""
    tmp_path = None
    try:
        if okey:
            # Self-host path: transcribe directly via the user's OpenAI key (no temp file needed).
            client = _openai_client(okey)
            resp = await client.audio.transcriptions.create(
                model="whisper-1",
                file=(audio.filename or f"voice{suffix}", raw, audio.content_type or "audio/webm"),
                response_format="text",
            )
            await client.close()
            transcript = (resp if isinstance(resp, str) else getattr(resp, "text", "")).strip()
        else:
            from emergentintegrations.llm.openai import OpenAISpeechToText  # type: ignore
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tf:
                tf.write(raw)
                tmp_path = tf.name
            stt = OpenAISpeechToText(api_key=EMERGENT_LLM_KEY)
            with open(tmp_path, "rb") as f:
                resp = await stt.transcribe(file=f, model="whisper-1", response_format="text")
            transcript = (resp if isinstance(resp, str) else getattr(resp, "text", "")).strip()
    except Exception as e:
        logger.warning(f"assistant STT failed: {e}")
        raise HTTPException(502, "Could not understand the audio. Please try again.")
    finally:
        if tmp_path:
            try: os.unlink(tmp_path)
            except Exception: pass

    if not transcript:
        raise HTTPException(400, "No speech detected.")
    sid, reply_text = await _generate_reply(session_id, transcript, user)
    audio_b64 = await _tts_base64(reply_text) if speak else ""
    return {"session_id": sid, "transcript": transcript, "reply": reply_text,
            "audio_base64": audio_b64, "mime": "audio/mpeg"}


@api.post("/assistant/lead")
async def assistant_lead(payload: LeadIn, user: Optional[dict] = Depends(get_optional_user)):
    if not (payload.name or payload.email or payload.phone):
        raise HTTPException(400, "Please share at least a name and a way to reach you.")
    now = now_utc().isoformat()
    lead = {
        "id": gen_id(),
        "session_id": payload.session_id,
        "user_id": (user or {}).get("id"),
        "name": payload.name, "email": payload.email, "phone": payload.phone,
        "channel": payload.channel or "whatsapp",
        "goal": payload.goal, "interest": payload.interest,
        "status": "new", "created_at": now,
    }
    await db.ai_leads.insert_one(lead)
    if payload.session_id:
        await db.chatbot_sessions.update_one({"id": payload.session_id}, {"$set": {"lead_id": lead["id"], "captured": True}})

    # Best-effort acknowledgment email to the enquirer (no-op if SMTP disabled).
    if payload.email:
        try:
            from email_service import send_enquiry_ack
            await send_enquiry_ack(payload.email, payload.name, payload.interest)
        except Exception as e:
            logger.warning(f"enquiry ack email failed for {payload.email}: {e}")

    wa_number = (await get_setting("social_whatsapp")) or ""
    digits = "".join(ch for ch in wa_number if ch.isdigit())
    wa_url = ""
    if digits:
        text = quote(f"Hi Tony! I'm {payload.name or 'a new student'} and I'm interested in {payload.interest or 'your yoga courses'}.")
        wa_url = f"https://wa.me/{digits}?text={text}"
    lead.pop("_id", None)
    return {"ok": True, "lead_id": lead["id"], "whatsapp_url": wa_url}


@api.get("/admin/assistant/leads")
async def admin_assistant_leads(request: Request):
    await require_role(request, ["admin"])
    rows = await db.ai_leads.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return {"leads": rows, "total": len(rows)}


@api.get("/admin/assistant/leads/export.csv")
async def export_leads_csv(request: Request):
    """CSV of captured AI-assistant leads for CRM / Google Sheet import. Admin-only."""
    import io
    import csv
    from fastapi.responses import Response
    await require_role(request, ["admin"])
    rows = await db.ai_leads.find({}, {"_id": 0}).sort("created_at", -1).to_list(5000)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["name", "email", "phone", "channel", "goal", "interest", "status", "created_at"])
    for r in rows:
        writer.writerow([
            r.get("name", ""), r.get("email", ""), r.get("phone", ""), r.get("channel", ""),
            r.get("goal", ""), r.get("interest", ""), r.get("status", ""), r.get("created_at", ""),
        ])
    return Response(
        content=buf.getvalue(), media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="ai_leads.csv"'},
    )
