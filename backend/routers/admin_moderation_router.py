"""Phase 5 — Admin god-mode moderation router.

Provides admin-only aggregate read + delete endpoints across every user-generated
collection so the super admin can see, moderate, and delete anything on the platform.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from auth import require_role
from db import get_db
from models import now_iso

router = APIRouter(prefix="/admin/moderation", tags=["admin-moderation"])


# ====================== YARD SALE ======================

@router.get("/yard-sale")
async def list_all_yard_sale(
    status: Optional[str] = None,
    user: dict = Depends(require_role("admin")),
):
    db = get_db()
    q: dict = {}
    if status:
        q["status"] = status
    items = await db["yard_sale"].find(q, {"_id": 0}).sort("created_at", -1).to_list(2000)
    return items


@router.delete("/yard-sale/{lid}")
async def delete_yard_sale(lid: str, user: dict = Depends(require_role("admin"))):
    db = get_db()
    item = await db["yard_sale"].find_one({"id": lid})
    if not item:
        raise HTTPException(404, "Not found")
    await db["yard_sale"].delete_one({"id": lid})
    return {"ok": True}


# ====================== ANNOUNCEMENTS ======================

@router.get("/announcements")
async def list_all_announcements(user: dict = Depends(require_role("admin"))):
    db = get_db()
    items = await db["announcements"].find({}, {"_id": 0}).sort("created_at", -1).to_list(2000)
    return items


@router.delete("/announcements/{ann_id}")
async def delete_announcement(ann_id: str, user: dict = Depends(require_role("admin"))):
    db = get_db()
    found = await db["announcements"].find_one({"id": ann_id})
    if not found:
        raise HTTPException(404, "Not found")
    await db["announcements"].delete_one({"id": ann_id})
    await db["announcement_views"].delete_many({"announcement_id": ann_id})
    await db["reactions"].delete_many({"target_id": ann_id})
    return {"ok": True}


# ====================== FORUM ======================

@router.get("/forum/threads")
async def list_all_threads(user: dict = Depends(require_role("admin"))):
    db = get_db()
    threads = await db["forum_threads"].find({}, {"_id": 0}).sort("created_at", -1).to_list(2000)
    # enrich with reply count
    for t in threads:
        t["replies_count"] = await db["forum_replies"].count_documents({"thread_id": t["id"]})
    return threads


@router.delete("/forum/threads/{thread_id}")
async def delete_thread(thread_id: str, user: dict = Depends(require_role("admin"))):
    db = get_db()
    found = await db["forum_threads"].find_one({"id": thread_id})
    if not found:
        raise HTTPException(404, "Not found")
    await db["forum_threads"].delete_one({"id": thread_id})
    await db["forum_replies"].delete_many({"thread_id": thread_id})
    await db["reactions"].delete_many({"target_id": thread_id})
    return {"ok": True}


# ====================== VIEWINGS ======================

@router.get("/viewings")
async def list_all_viewings(user: dict = Depends(require_role("admin"))):
    db = get_db()
    viewings = await db["viewings"].find({}, {"_id": 0}).sort("created_at", -1).to_list(2000)
    if viewings:
        prop_ids = list({v["property_id"] for v in viewings if v.get("property_id")})
        props = await db["properties"].find({"id": {"$in": prop_ids}}, {"_id": 0}).to_list(500)
        p_map = {p["id"]: p for p in props}
        for v in viewings:
            p = p_map.get(v.get("property_id"))
            v["property_name"] = p["name"] if p else ""
            v["property_address"] = p["address"] if p else ""
    return viewings


@router.delete("/viewings/{viewing_id}")
async def delete_viewing(viewing_id: str, user: dict = Depends(require_role("admin"))):
    db = get_db()
    found = await db["viewings"].find_one({"id": viewing_id})
    if not found:
        raise HTTPException(404, "Not found")
    await db["viewings"].delete_one({"id": viewing_id})
    return {"ok": True}


# ====================== VISITOR PASSES ======================

@router.get("/visitor-passes")
async def list_all_passes(user: dict = Depends(require_role("admin"))):
    db = get_db()
    # auto-expire
    await db["visitor_passes"].update_many(
        {"status": "active", "expires_at": {"$lt": now_iso()}},
        {"$set": {"status": "expired"}},
    )
    items = await db["visitor_passes"].find({}, {"_id": 0}).sort("created_at", -1).to_list(2000)
    return items


@router.delete("/visitor-passes/{pid}")
async def delete_pass(pid: str, user: dict = Depends(require_role("admin"))):
    db = get_db()
    found = await db["visitor_passes"].find_one({"id": pid})
    if not found:
        raise HTTPException(404, "Not found")
    await db["visitor_passes"].delete_one({"id": pid})
    return {"ok": True}


# ====================== ISSUES (already admin-visible elsewhere, included for completeness) ======================

@router.get("/issues")
async def list_all_issues(user: dict = Depends(require_role("admin"))):
    db = get_db()
    issues = await db["issues"].find({}, {"_id": 0}).sort("created_at", -1).to_list(2000)
    return issues


@router.delete("/issues/{issue_id}")
async def delete_issue(issue_id: str, user: dict = Depends(require_role("admin"))):
    db = get_db()
    found = await db["issues"].find_one({"id": issue_id})
    if not found:
        raise HTTPException(404, "Not found")
    await db["issues"].delete_one({"id": issue_id})
    return {"ok": True}


# ====================== AI CONVERSATIONS (delete supplement to existing /admin/ai-conversations) ======================

@router.delete("/ai-conversations/{session_id}")
async def delete_ai_conversation(session_id: str, user: dict = Depends(require_role("admin"))):
    db = get_db()
    found = await db["ai_conversations"].find_one({"session_id": session_id})
    if not found:
        raise HTTPException(404, "Not found")
    await db["ai_conversations"].delete_one({"session_id": session_id})
    return {"ok": True}


# ====================== LEASES ======================

@router.get("/leases")
async def list_all_leases(user: dict = Depends(require_role("admin"))):
    db = get_db()
    leases = await db["leases"].find({}, {"_id": 0}).sort("created_at", -1).to_list(2000)
    return leases


@router.delete("/leases/{lease_id}")
async def delete_lease(lease_id: str, user: dict = Depends(require_role("admin"))):
    db = get_db()
    found = await db["leases"].find_one({"id": lease_id})
    if not found:
        raise HTTPException(404, "Not found")
    await db["leases"].delete_one({"id": lease_id})
    return {"ok": True}


# ====================== PLATFORM SUMMARY ======================

@router.get("/summary")
async def moderation_summary(user: dict = Depends(require_role("admin"))):
    """Quick counts for admin moderation dashboard."""
    db = get_db()
    return {
        "users": await db["users"].count_documents({}),
        "properties": await db["properties"].count_documents({}),
        "units": await db["units"].count_documents({}),
        "yard_sale": await db["yard_sale"].count_documents({}),
        "announcements": await db["announcements"].count_documents({}),
        "forum_threads": await db["forum_threads"].count_documents({}),
        "forum_replies": await db["forum_replies"].count_documents({}),
        "viewings": await db["viewings"].count_documents({}),
        "visitor_passes": await db["visitor_passes"].count_documents({}),
        "issues": await db["issues"].count_documents({}),
        "leases": await db["leases"].count_documents({}),
        "ai_conversations": await db["ai_conversations"].count_documents({}),
        "payments": await db["payments"].count_documents({}),
        "reactions": await db["reactions"].count_documents({}),
    }
