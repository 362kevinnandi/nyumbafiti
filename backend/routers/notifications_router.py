"""In-app notifications router."""
from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_user
from db import get_db

router = APIRouter(tags=["notifications"])


@router.get("/notifications")
async def list_notifications(
    unread_only: bool = False,
    limit: int = 50,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    query: dict = {"user_id": user["id"]}
    if unread_only:
        query["read"] = False
    items = await db["notifications"].find(query, {"_id": 0}).sort("created_at", -1).to_list(limit)
    unread = await db["notifications"].count_documents({"user_id": user["id"], "read": False})
    return {"items": items, "unread_count": unread}


@router.patch("/notifications/{nid}/read")
async def mark_read(nid: str, user: dict = Depends(get_current_user)):
    db = get_db()
    res = await db["notifications"].update_one(
        {"id": nid, "user_id": user["id"]}, {"$set": {"read": True}}
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Notification not found")
    return {"ok": True}


@router.post("/notifications/mark-all-read")
async def mark_all_read(user: dict = Depends(get_current_user)):
    db = get_db()
    await db["notifications"].update_many(
        {"user_id": user["id"], "read": False}, {"$set": {"read": True}}
    )
    return {"ok": True}
