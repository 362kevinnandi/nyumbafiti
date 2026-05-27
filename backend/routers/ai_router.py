"""Phase 4 — AI Property Recommendations via Claude Sonnet 4.5 (Emergent LLM key)."""
import json
import logging
import os
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user
from db import get_db
from models import new_id, now_iso

router = APIRouter(tags=["ai"])
logger = logging.getLogger("ai-router")


class RecommendRequest(BaseModel):
    max_rent: Optional[float] = None
    preferred_bedrooms: Optional[int] = None
    preferred_categories: Optional[List[str]] = None
    area_keywords: Optional[str] = None  # free-form text like "westlands, kilimani"
    notes: Optional[str] = ""


class RecommendItem(BaseModel):
    listing_id: str
    rationale: str


class RecommendResponse(BaseModel):
    items: List[RecommendItem]
    message: str
    used_llm: bool


@router.post("/ai/recommend-properties", response_model=RecommendResponse)
async def recommend_properties(
    payload: RecommendRequest, user: dict = Depends(get_current_user)
):
    """Use Claude Sonnet 4.5 to pick the best 3 listings for the user."""
    db = get_db()
    # Build candidate pool from /public/listings logic
    approved = await db["properties"].find(
        {"approval_status": "approved"}, {"_id": 0, "id": 1}
    ).to_list(2000)
    approved_ids = {p["id"] for p in approved}
    if not approved_ids:
        return RecommendResponse(items=[], message="No active listings on the platform yet.", used_llm=False)

    q: dict = {"occupied": False, "property_id": {"$in": list(approved_ids)}}
    if payload.max_rent:
        q["rent_amount"] = {"$lte": payload.max_rent}
    if payload.preferred_bedrooms:
        q["bedrooms"] = payload.preferred_bedrooms
    units = await db["units"].find(q, {"_id": 0}).to_list(120)
    if not units:
        return RecommendResponse(items=[], message="No listings match your filters. Try widening your criteria.", used_llm=False)

    prop_ids = list({u["property_id"] for u in units})
    props = await db["properties"].find({"id": {"$in": prop_ids}}, {"_id": 0}).to_list(200)
    p_map = {p["id"]: p for p in props}

    # Build compact JSON the LLM will consume
    compact = []
    for u in units:
        prop = p_map.get(u["property_id"])
        if not prop:
            continue
        if payload.preferred_categories and prop.get("category") not in payload.preferred_categories:
            continue
        if payload.area_keywords:
            ks = [k.strip().lower() for k in payload.area_keywords.split(",") if k.strip()]
            if ks and not any(k in (prop.get("address","").lower()) for k in ks):
                continue
        compact.append({
            "listing_id": u["id"],
            "property_name": prop.get("name"),
            "address": prop.get("address"),
            "category": prop.get("category", "apartment"),
            "rent_kes": int(u.get("rent_amount", 0)),
            "bedrooms": u.get("bedrooms"),
            "featured": bool(prop.get("featured")),
        })

    if not compact:
        return RecommendResponse(items=[], message="No listings match all your filters.", used_llm=False)

    # If <= 3 candidates, just return them with a static rationale
    if len(compact) <= 3:
        items = [
            RecommendItem(
                listing_id=c["listing_id"],
                rationale=f"Matches your filters: {c['bedrooms']} bed · KES {c['rent_kes']:,} · {c['category']}",
            )
            for c in compact
        ]
        return RecommendResponse(items=items, message="Top matches based on your filters.", used_llm=False)

    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        # Fallback: cheapest 3
        compact.sort(key=lambda c: c["rent_kes"])
        items = [
            RecommendItem(
                listing_id=c["listing_id"],
                rationale=f"Lowest rent matching your filters · KES {c['rent_kes']:,}",
            )
            for c in compact[:3]
        ]
        return RecommendResponse(items=items, message="Fallback (no LLM key) — sorted by price.", used_llm=False)

    # Call Claude Sonnet 4.5 via Emergent LLM key
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        system_msg = (
            "You are a helpful Nairobi rental property concierge. "
            "Given a JSON array of vacant listings and a prospect's preferences, "
            "pick the THREE best matches and explain in ONE short sentence each (max 18 words) why. "
            "Always reply with VALID JSON ONLY of the shape: "
            '{"items":[{"listing_id":"...","rationale":"..."},...]}. '
            "Use only listing_ids that appear in the input."
        )
        chat = LlmChat(
            api_key=api_key,
            session_id=f"recos-{user['id']}-{new_id()[:8]}",
            system_message=system_msg,
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")

        user_payload = {
            "preferences": payload.model_dump(),
            "listings": compact[:40],  # cap input size
        }
        user_msg = UserMessage(text=json.dumps(user_payload))
        raw = await chat.send_message(user_msg)
        text = raw if isinstance(raw, str) else str(raw)
        # Extract JSON
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("LLM response had no JSON")
        parsed = json.loads(text[start:end + 1])
        items_raw = parsed.get("items") or []
        valid_ids = {c["listing_id"] for c in compact}
        items: List[RecommendItem] = []
        for it in items_raw[:3]:
            lid = it.get("listing_id")
            rationale = (it.get("rationale") or "").strip()[:240]
            if lid in valid_ids and rationale:
                items.append(RecommendItem(listing_id=lid, rationale=rationale))
        if not items:
            raise ValueError("LLM returned no valid listing_ids")
        return RecommendResponse(items=items, message="AI-picked matches.", used_llm=True)
    except Exception as exc:
        logger.warning("AI reco failed, falling back: %s", exc)
        compact.sort(key=lambda c: c["rent_kes"])
        items = [
            RecommendItem(
                listing_id=c["listing_id"],
                rationale=f"Affordable match · KES {c['rent_kes']:,} · {c['bedrooms']} bed",
            )
            for c in compact[:3]
        ]
        return RecommendResponse(items=items, message="Top affordable matches.", used_llm=False)


# ====================== PHASE 5: AI CHAT CONCIERGE ======================

class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    used_llm: bool


async def _build_listings_context(db) -> str:
    """Compact summary of vacant listings the AI can reference."""
    approved = await db["properties"].find(
        {"approval_status": "approved"}, {"_id": 0, "id": 1, "name": 1, "address": 1,
                                          "category": 1, "sub_type": 1, "tenancy_types": 1}
    ).to_list(500)
    if not approved:
        return "[no active listings]"
    pids = [p["id"] for p in approved]
    pmap = {p["id"]: p for p in approved}
    units = await db["units"].find(
        {"occupied": False, "property_id": {"$in": pids}},
        {"_id": 0, "id": 1, "property_id": 1, "unit_number": 1, "rent_amount": 1, "bedrooms": 1},
    ).to_list(200)
    out = []
    for u in units[:30]:
        p = pmap.get(u["property_id"])
        if not p:
            continue
        out.append(
            f"- {p['name']} · {p['address']} · {p.get('category','apartment')}"
            f"{'/' + p['sub_type'] if p.get('sub_type') else ''}"
            f" · KES {int(u['rent_amount']):,}/mo · {u['bedrooms']} bed · listing_id={u['id']}"
        )
    return "\n".join(out) if out else "[no vacant units]"


@router.post("/ai/chat", response_model=ChatResponse)
async def ai_chat(payload: ChatRequest, user: dict = Depends(get_current_user)):
    """Conversational AI concierge. Persists multi-turn history per session.
    Visible to admin for moderation. Falls back gracefully if LLM unavailable."""
    db = get_db()
    session_id = payload.session_id or new_id()

    # Append user message immediately
    user_turn = {
        "role": "user",
        "text": payload.message,
        "created_at": now_iso(),
    }
    await db["ai_conversations"].update_one(
        {"session_id": session_id},
        {
            "$setOnInsert": {
                "session_id": session_id,
                "user_id": user["id"],
                "user_name": user["full_name"],
                "user_role": user["role"],
                "created_at": now_iso(),
            },
            "$set": {"updated_at": now_iso()},
            "$push": {"messages": user_turn},
        },
        upsert=True,
    )

    conv = await db["ai_conversations"].find_one({"session_id": session_id})
    history = conv.get("messages", []) if conv else []

    api_key = os.environ.get("EMERGENT_LLM_KEY")
    reply_text = ""
    used_llm = False

    if not api_key:
        reply_text = (
            "I'm in basic mode right now (no LLM credits). "
            "Try the AI Match form on the marketplace for direct property recommendations, "
            "or filter by 2BR + Westlands in the search bar above."
        )
    else:
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage
            ctx = await _build_listings_context(db)
            system_msg = (
                "You are NyumbaOS Concierge, a friendly Nairobi rental assistant. "
                "Be concise (2-4 sentences). Use KES amounts. If the user shares "
                "preferences (budget, bedrooms, area like Westlands/Kilimani), recommend "
                "specific listings from the catalog below by name and listing_id. "
                "If they ask about how the platform works (viewings KES 200, 3.5% commission, "
                "leases, yard sale), answer truthfully. If they ask about something off-topic, "
                "politely redirect.\n\n"
                f"AVAILABLE LISTINGS:\n{ctx}"
            )
            chat = LlmChat(
                api_key=api_key,
                session_id=session_id,
                system_message=system_msg,
            ).with_model("anthropic", "claude-sonnet-4-5-20250929")
            # Replay previous messages so model has continuity within session
            for h in history[:-1]:  # all except the just-inserted current message
                if h["role"] == "user":
                    await chat.send_message(UserMessage(text=h["text"]))
            raw = await chat.send_message(UserMessage(text=payload.message))
            reply_text = (raw if isinstance(raw, str) else str(raw)).strip()
            used_llm = True
        except Exception as exc:
            logger.warning("AI chat fallback: %s", exc)
            reply_text = (
                "Hmm, my AI is briefly unreachable. While I'm back: try the search "
                "(e.g. 'Westlands 2 bedroom') or the AI Match button for filtered picks."
            )

    assistant_turn = {
        "role": "assistant",
        "text": reply_text,
        "used_llm": used_llm,
        "created_at": now_iso(),
    }
    await db["ai_conversations"].update_one(
        {"session_id": session_id},
        {
            "$push": {"messages": assistant_turn},
            "$set": {"updated_at": now_iso()},
        },
    )
    return ChatResponse(session_id=session_id, reply=reply_text, used_llm=used_llm)


@router.get("/ai/conversations")
async def list_my_conversations(user: dict = Depends(get_current_user)):
    db = get_db()
    rows = await db["ai_conversations"].find(
        {"user_id": user["id"]}, {"_id": 0}
    ).sort("updated_at", -1).to_list(50)
    # Return summary list only
    return [
        {
            "session_id": r["session_id"],
            "created_at": r["created_at"],
            "updated_at": r.get("updated_at", r["created_at"]),
            "message_count": len(r.get("messages", [])),
            "preview": (r.get("messages", [{}])[0].get("text", "") if r.get("messages") else "")[:80],
        }
        for r in rows
    ]


@router.get("/ai/conversations/{session_id}")
async def get_conversation(session_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    conv = await db["ai_conversations"].find_one({"session_id": session_id}, {"_id": 0})
    if not conv:
        raise HTTPException(404, "Conversation not found")
    if user["role"] != "admin" and conv["user_id"] != user["id"]:
        raise HTTPException(403, "Forbidden")
    return conv


@router.get("/admin/ai-conversations")
async def admin_list_all_conversations(user: dict = Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Admin only")
    db = get_db()
    rows = await db["ai_conversations"].find({}, {"_id": 0}).sort("updated_at", -1).to_list(500)
    return [
        {
            "session_id": r["session_id"],
            "user_id": r["user_id"],
            "user_name": r.get("user_name", "?"),
            "user_role": r.get("user_role", "?"),
            "created_at": r["created_at"],
            "updated_at": r.get("updated_at", r["created_at"]),
            "message_count": len(r.get("messages", [])),
            "preview": (r.get("messages", [{}])[0].get("text", "") if r.get("messages") else "")[:120],
        }
        for r in rows
    ]

