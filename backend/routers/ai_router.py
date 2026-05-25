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
