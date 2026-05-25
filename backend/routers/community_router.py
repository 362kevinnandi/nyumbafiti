"""Phase 2 — Community Hub: announcements + per-property tenant forum."""
import os
import shutil
from typing import List, Optional

from fastapi import (
    APIRouter, Depends, File, Form, HTTPException, UploadFile,
)

from auth import get_current_user, require_role
from db import get_db
from models import (
    AnnouncementCreate, ForumReplyCreate, ForumThreadCreate, new_id, now_iso,
)
from notifications import notify_many

router = APIRouter(tags=["community"])

UPLOAD_DIR = "uploads/community"
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_MIME_PREFIXES = ("image/", "application/pdf")


def _validate_upload(file: UploadFile) -> None:
    if not file.filename:
        return
    if file.content_type and not any(file.content_type.startswith(p) for p in ALLOWED_MIME_PREFIXES):
        raise HTTPException(400, f"Unsupported file type: {file.content_type}. Allowed: images and PDFs.")


async def _save_attachments(files: List[UploadFile]) -> List[str]:
    out: List[str] = []
    for f in files[:5]:
        if not f.filename:
            continue
        _validate_upload(f)
        contents = await f.read()
        if len(contents) > MAX_FILE_BYTES:
            raise HTTPException(400, f"File '{f.filename}' exceeds 5MB limit")
        filename = f"{new_id()}_{f.filename}"
        path = f"{UPLOAD_DIR}/{filename}"
        with open(path, "wb") as buf:
            buf.write(contents)
        out.append(path)
    return out


async def _audience_user_ids(scope: str, property_id: Optional[str], landlord_id: Optional[str]) -> List[str]:
    """Return the tenant + caretaker ids who should receive notifications for an announcement."""
    db = get_db()
    query: dict = {"role": {"$in": ["tenant", "caretaker"]}}
    if scope == "property" and property_id:
        units = await db["units"].find({"property_id": property_id}, {"_id": 0, "tenant_id": 1}).to_list(500)
        tenant_ids = [u["tenant_id"] for u in units if u.get("tenant_id")]
        cares = await db["users"].find(
            {"role": "caretaker", "landlord_id": landlord_id}, {"_id": 0, "id": 1}
        ).to_list(200) if landlord_id else []
        ids = tenant_ids + [c["id"] for c in cares]
        return ids
    # global: notify everyone except admins
    users = await db["users"].find(query, {"_id": 0, "id": 1}).to_list(2000)
    return [u["id"] for u in users]


# ====================== ANNOUNCEMENTS ======================

@router.post("/announcements")
async def create_announcement(
    scope: str = Form(...),
    title: str = Form(...),
    body: str = Form(...),
    property_id: Optional[str] = Form(None),
    pinned: bool = Form(False),
    attachments: List[UploadFile] = File([]),
    user: dict = Depends(get_current_user),
):
    db = get_db()
    if scope not in ("global", "property"):
        raise HTTPException(400, "scope must be 'global' or 'property'")

    if scope == "global":
        if user["role"] != "admin":
            raise HTTPException(403, "Only platform admin can post global announcements")
        landlord_id = None
    else:
        if not property_id:
            raise HTTPException(400, "property_id required for property-scope")
        prop = await db["properties"].find_one({"id": property_id})
        if not prop:
            raise HTTPException(404, "Property not found")
        if user["role"] == "landlord" and prop["landlord_id"] != user["id"]:
            raise HTTPException(403, "You can only post to your own properties")
        if user["role"] not in ("landlord", "admin"):
            raise HTTPException(403, "Only landlords (own property) and admins can post")
        landlord_id = prop["landlord_id"]

    paths = await _save_attachments(attachments)
    doc = {
        "id": new_id(),
        "scope": scope,
        "property_id": property_id if scope == "property" else None,
        "landlord_id": landlord_id,
        "author_id": user["id"],
        "author_name": user["full_name"],
        "author_role": user["role"],
        "title": title,
        "body": body,
        "attachments": paths,
        "pinned": bool(pinned),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db["announcements"].insert_one(doc)
    doc.pop("_id", None)

    # fan-out notifications
    audience = await _audience_user_ids(scope, property_id, landlord_id)
    await notify_many(
        audience, "announcement", f"New announcement: {title}",
        body[:140], link="/community",
    )
    return doc


@router.get("/announcements")
async def list_announcements(user: dict = Depends(get_current_user)):
    db = get_db()
    role = user["role"]
    queries: list = [{"scope": "global"}]
    if role == "admin":
        queries.append({"scope": "property"})
    elif role == "landlord":
        queries.append({"scope": "property", "landlord_id": user["id"]})
    elif role in ("tenant", "caretaker"):
        if user.get("landlord_id"):
            # tenants see announcements for properties they belong to (via unit)
            queries.append({"scope": "property", "landlord_id": user["landlord_id"]})
    items = await db["announcements"].find(
        {"$or": queries}, {"_id": 0}
    ).sort([("pinned", -1), ("created_at", -1)]).to_list(500)
    return items


@router.delete("/announcements/{ann_id}")
async def delete_announcement(ann_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    ann = await db["announcements"].find_one({"id": ann_id})
    if not ann:
        raise HTTPException(404, "Announcement not found")
    if user["role"] != "admin" and ann["author_id"] != user["id"]:
        raise HTTPException(403, "Forbidden")
    await db["announcements"].delete_one({"id": ann_id})
    return {"ok": True}


@router.patch("/announcements/{ann_id}/pin")
async def toggle_pin_announcement(ann_id: str, user: dict = Depends(require_role("admin", "landlord"))):
    db = get_db()
    ann = await db["announcements"].find_one({"id": ann_id})
    if not ann:
        raise HTTPException(404, "Announcement not found")
    if user["role"] == "landlord" and ann.get("landlord_id") != user["id"]:
        raise HTTPException(403, "Forbidden")
    await db["announcements"].update_one(
        {"id": ann_id}, {"$set": {"pinned": not bool(ann.get("pinned")), "updated_at": now_iso()}}
    )
    return {"ok": True, "pinned": not bool(ann.get("pinned"))}


# ====================== FORUM THREADS ======================

async def _can_access_property_forum(user: dict, property_id: str) -> bool:
    db = get_db()
    if user["role"] == "admin":
        return True
    prop = await db["properties"].find_one({"id": property_id})
    if not prop:
        return False
    if user["role"] == "landlord":
        return prop["landlord_id"] == user["id"]
    if user["role"] == "caretaker":
        return user.get("landlord_id") == prop["landlord_id"]
    if user["role"] == "tenant":
        # tenant must have a unit in this property
        unit = await db["units"].find_one({"id": user.get("unit_id")})
        return bool(unit and unit.get("property_id") == property_id)
    return False


@router.post("/forum/threads")
async def create_thread(
    property_id: str = Form(...),
    title: str = Form(...),
    body: str = Form(...),
    attachments: List[UploadFile] = File([]),
    user: dict = Depends(get_current_user),
):
    if user["role"] not in ("tenant", "landlord", "caretaker", "admin"):
        raise HTTPException(403, "Forbidden")
    if not await _can_access_property_forum(user, property_id):
        raise HTTPException(403, "You do not belong to this property forum")

    db = get_db()
    prop = await db["properties"].find_one({"id": property_id})
    if not prop:
        raise HTTPException(404, "Property not found")

    paths = await _save_attachments(attachments)
    doc = {
        "id": new_id(),
        "property_id": property_id,
        "landlord_id": prop["landlord_id"],
        "author_id": user["id"],
        "author_name": user["full_name"],
        "author_role": user["role"],
        "title": title,
        "body": body,
        "attachments": paths,
        "pinned": False,
        "locked": False,
        "replies_count": 0,
        "last_reply_at": None,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db["forum_threads"].insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/forum/threads")
async def list_threads(
    property_id: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    query: dict = {}
    if user["role"] == "tenant":
        # tenants only see their own property's threads
        unit = await db["units"].find_one({"id": user.get("unit_id")}) if user.get("unit_id") else None
        if not unit:
            return []
        query["property_id"] = unit["property_id"]
    elif user["role"] == "landlord":
        query["landlord_id"] = user["id"]
        if property_id:
            query["property_id"] = property_id
    elif user["role"] == "caretaker":
        if not user.get("landlord_id"):
            return []
        query["landlord_id"] = user["landlord_id"]
        if property_id:
            query["property_id"] = property_id
    elif user["role"] == "admin":
        if property_id:
            query["property_id"] = property_id
    threads = await db["forum_threads"].find(query, {"_id": 0}).sort(
        [("pinned", -1), ("last_reply_at", -1), ("created_at", -1)]
    ).to_list(500)
    return threads


@router.get("/forum/threads/{thread_id}")
async def get_thread(thread_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    thread = await db["forum_threads"].find_one({"id": thread_id}, {"_id": 0})
    if not thread:
        raise HTTPException(404, "Thread not found")
    if not await _can_access_property_forum(user, thread["property_id"]):
        raise HTTPException(403, "Forbidden")
    replies = await db["forum_replies"].find(
        {"thread_id": thread_id}, {"_id": 0}
    ).sort("created_at", 1).to_list(500)
    return {"thread": thread, "replies": replies}


@router.post("/forum/threads/{thread_id}/replies")
async def post_reply(
    thread_id: str,
    body: str = Form(...),
    attachments: List[UploadFile] = File([]),
    user: dict = Depends(get_current_user),
):
    db = get_db()
    thread = await db["forum_threads"].find_one({"id": thread_id})
    if not thread:
        raise HTTPException(404, "Thread not found")
    if thread.get("locked") and user["role"] != "admin":
        raise HTTPException(403, "Thread is locked")
    if not await _can_access_property_forum(user, thread["property_id"]):
        raise HTTPException(403, "Forbidden")

    paths = await _save_attachments(attachments)
    reply = {
        "id": new_id(),
        "thread_id": thread_id,
        "author_id": user["id"],
        "author_name": user["full_name"],
        "author_role": user["role"],
        "body": body,
        "attachments": paths,
        "created_at": now_iso(),
    }
    await db["forum_replies"].insert_one(reply)
    await db["forum_threads"].update_one(
        {"id": thread_id},
        {"$set": {"last_reply_at": reply["created_at"], "updated_at": reply["created_at"]},
         "$inc": {"replies_count": 1}},
    )
    reply.pop("_id", None)

    # notify the thread author (skip if self-reply)
    if thread["author_id"] != user["id"]:
        from notifications import notify_user
        await notify_user(
            thread["author_id"], "forum_reply",
            f"New reply on “{thread['title']}”",
            f"{user['full_name']}: {body[:120]}",
            link="/community",
        )
    return reply


@router.delete("/forum/threads/{thread_id}")
async def delete_thread(thread_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    thread = await db["forum_threads"].find_one({"id": thread_id})
    if not thread:
        raise HTTPException(404, "Thread not found")
    if user["role"] != "admin" and thread["author_id"] != user["id"]:
        raise HTTPException(403, "Forbidden")
    await db["forum_threads"].delete_one({"id": thread_id})
    await db["forum_replies"].delete_many({"thread_id": thread_id})
    return {"ok": True}


@router.patch("/forum/threads/{thread_id}/moderate")
async def moderate_thread(
    thread_id: str,
    pinned: Optional[bool] = None,
    locked: Optional[bool] = None,
    user: dict = Depends(require_role("admin", "landlord")),
):
    db = get_db()
    thread = await db["forum_threads"].find_one({"id": thread_id})
    if not thread:
        raise HTTPException(404, "Thread not found")
    if user["role"] == "landlord" and thread["landlord_id"] != user["id"]:
        raise HTTPException(403, "Forbidden")
    update: dict = {"updated_at": now_iso()}
    if pinned is not None:
        update["pinned"] = bool(pinned)
    if locked is not None:
        update["locked"] = bool(locked)
    await db["forum_threads"].update_one({"id": thread_id}, {"$set": update})
    fresh = await db["forum_threads"].find_one({"id": thread_id}, {"_id": 0})
    return fresh


# ====================== ATTACHMENT DOWNLOAD HELPER ======================
# Files are served via the existing /api/uploads/<path> static mount.
# Frontend uses mediaUrl() to build proper URLs from the returned paths.
