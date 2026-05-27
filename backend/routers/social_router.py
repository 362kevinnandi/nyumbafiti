"""Phase 5 — Reactions (like/love) + view receipts for Community Hub."""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_user
from db import get_db
from models import new_id, now_iso

router = APIRouter(tags=["social"])

ReactionType = Literal["like", "love", "celebrate", "support"]
TargetType = Literal["announcement", "thread", "reply"]


def _collection_for(target_type: str) -> str:
    return {
        "announcement": "announcements",
        "thread": "forum_threads",
        "reply": "forum_replies",
    }[target_type]


@router.post("/social/{target_type}/{target_id}/react")
async def react(
    target_type: TargetType,
    target_id: str,
    reaction: ReactionType,
    user: dict = Depends(get_current_user),
):
    """Add or toggle a reaction. Sending the same reaction again removes it."""
    db = get_db()
    coll = _collection_for(target_type)
    target = await db[coll].find_one({"id": target_id})
    if not target:
        raise HTTPException(404, "Target not found")

    existing = await db["reactions"].find_one({
        "target_id": target_id, "user_id": user["id"]
    })

    if existing and existing["type"] == reaction:
        # Toggle off
        await db["reactions"].delete_one({"id": existing["id"]})
        action = "removed"
    elif existing:
        # Change reaction type
        await db["reactions"].update_one(
            {"id": existing["id"]},
            {"$set": {"type": reaction, "updated_at": now_iso()}},
        )
        action = "changed"
    else:
        await db["reactions"].insert_one({
            "id": new_id(),
            "target_id": target_id,
            "target_type": target_type,
            "type": reaction,
            "user_id": user["id"],
            "user_name": user["full_name"],
            "user_role": user["role"],
            "created_at": now_iso(),
            "updated_at": now_iso(),
        })
        action = "added"

    counts = await _counts_for(target_id)
    return {"action": action, "counts": counts}


async def _counts_for(target_id: str) -> dict:
    db = get_db()
    pipeline = [
        {"$match": {"target_id": target_id}},
        {"$group": {"_id": "$type", "count": {"$sum": 1}}},
    ]
    rows = await db["reactions"].aggregate(pipeline).to_list(20)
    return {row["_id"]: row["count"] for row in rows}


@router.get("/social/{target_type}/{target_id}/reactions")
async def list_reactions(
    target_type: TargetType,
    target_id: str,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    coll = _collection_for(target_type)
    target = await db[coll].find_one({"id": target_id})
    if not target:
        raise HTTPException(404, "Target not found")
    reactions = await db["reactions"].find(
        {"target_id": target_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(500)
    my = next((r for r in reactions if r["user_id"] == user["id"]), None)
    counts = {}
    for r in reactions:
        counts[r["type"]] = counts.get(r["type"], 0) + 1
    return {"counts": counts, "my_reaction": my["type"] if my else None, "reactions": reactions}


# ====================== ANNOUNCEMENT VIEWS ======================

@router.post("/social/announcement/{ann_id}/view")
async def record_view(ann_id: str, user: dict = Depends(get_current_user)):
    """Record (or update timestamp of) a view for read receipts. Author + admin can see."""
    db = get_db()
    ann = await db["announcements"].find_one({"id": ann_id})
    if not ann:
        raise HTTPException(404, "Announcement not found")
    # Don't record author viewing own announcement
    if ann.get("author_id") == user["id"]:
        return {"ok": True, "ignored": True}

    existing = await db["announcement_views"].find_one({
        "announcement_id": ann_id, "user_id": user["id"],
    })
    now = now_iso()
    if existing:
        await db["announcement_views"].update_one(
            {"id": existing["id"]},
            {"$set": {"last_viewed_at": now, "view_count": existing.get("view_count", 1) + 1}},
        )
    else:
        await db["announcement_views"].insert_one({
            "id": new_id(),
            "announcement_id": ann_id,
            "user_id": user["id"],
            "user_name": user["full_name"],
            "user_role": user["role"],
            "first_viewed_at": now,
            "last_viewed_at": now,
            "view_count": 1,
        })
    return {"ok": True}


@router.get("/social/announcement/{ann_id}/views")
async def list_views(ann_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    ann = await db["announcements"].find_one({"id": ann_id})
    if not ann:
        raise HTTPException(404, "Announcement not found")
    # Only author + admin can see the list of viewers
    if user["role"] != "admin" and ann.get("author_id") != user["id"]:
        raise HTTPException(403, "Only the author and platform admin can see read receipts")
    views = await db["announcement_views"].find(
        {"announcement_id": ann_id}, {"_id": 0}
    ).sort("last_viewed_at", -1).to_list(1000)
    return {"total": len(views), "views": views}
