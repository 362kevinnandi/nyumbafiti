"""Phase 4 — QR Visitor Passes. Tenant creates a one-time pass, caretaker scans on entry."""
import base64
import io
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_user, require_role
from db import get_db
from models import VisitorPassCreate, new_id, now_iso
from notifications import notify_user

router = APIRouter(tags=["visitor-passes"])


def _generate_token() -> str:
    return secrets.token_urlsafe(20)


def _qr_data_url(payload: str) -> str:
    """Return a data: URL with a base64 PNG QR code for the given payload."""
    import qrcode
    qr = qrcode.QRCode(version=1, box_size=8, border=2)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


@router.post("/visitor-passes")
async def create_pass(payload: VisitorPassCreate, user: dict = Depends(require_role("tenant"))):
    db = get_db()
    if not user.get("unit_id") or not user.get("landlord_id"):
        raise HTTPException(400, "You must be assigned to a unit to create visitor passes")
    unit = await db["units"].find_one({"id": user["unit_id"]})
    if not unit:
        raise HTTPException(404, "Unit not found")

    token = _generate_token()
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    doc = {
        "id": new_id(),
        "token": token,
        "tenant_id": user["id"],
        "tenant_name": user["full_name"],
        "landlord_id": user["landlord_id"],
        "property_id": unit["property_id"],
        "unit_id": user["unit_id"],
        "visitor_name": payload.visitor_name,
        "visitor_phone": payload.visitor_phone or "",
        "expected_time": payload.expected_time,
        "notes": payload.notes or "",
        "status": "active",
        "used_at": None,
        "used_by_caretaker_id": None,
        "used_by_caretaker_name": None,
        "expires_at": expires_at,
        "created_at": now_iso(),
    }
    await db["visitor_passes"].insert_one(doc)
    doc.pop("_id", None)
    doc["qr_data_url"] = _qr_data_url(token)
    return doc


@router.get("/visitor-passes")
async def list_passes(user: dict = Depends(get_current_user)):
    db = get_db()
    # auto-expire stale ones
    now = now_iso()
    await db["visitor_passes"].update_many(
        {"status": "active", "expires_at": {"$lt": now}},
        {"$set": {"status": "expired"}},
    )

    if user["role"] == "tenant":
        query = {"tenant_id": user["id"]}
    elif user["role"] in ("caretaker", "security"):
        if not user.get("landlord_id"):
            return []
        query = {"landlord_id": user["landlord_id"]}
    elif user["role"] == "landlord":
        query = {"landlord_id": user["id"]}
    elif user["role"] == "admin":
        query = {}
    else:
        return []
    items = await db["visitor_passes"].find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    # attach QR only for active passes that belong to this tenant
    for it in items:
        if user["role"] == "tenant" and it["status"] == "active":
            it["qr_data_url"] = _qr_data_url(it["token"])
    return items


@router.post("/visitor-passes/scan/{token}")
async def scan_pass(token: str, user: dict = Depends(require_role("caretaker", "security", "admin", "landlord"))):
    db = get_db()
    p = await db["visitor_passes"].find_one({"token": token})
    if not p:
        raise HTTPException(404, "Pass not found")
    if user["role"] in ("caretaker", "security") and p["landlord_id"] != user.get("landlord_id"):
        raise HTTPException(403, "Forbidden")
    if user["role"] == "landlord" and p["landlord_id"] != user["id"]:
        raise HTTPException(403, "Forbidden")
    if p["status"] == "used":
        raise HTTPException(400, "Pass has already been used")
    if p["status"] == "expired" or p["expires_at"] < now_iso():
        raise HTTPException(400, "Pass has expired")
    if p["status"] == "cancelled":
        raise HTTPException(400, "Pass was cancelled")

    used_at = now_iso()
    await db["visitor_passes"].update_one(
        {"id": p["id"]},
        {"$set": {
            "status": "used", "used_at": used_at,
            "used_by_caretaker_id": user["id"],
            "used_by_caretaker_name": user["full_name"],
            "used_by_role": user["role"],
        }},
    )
    await notify_user(
        p["tenant_id"], "visitor_arrived",
        f"Visitor {p['visitor_name']} has arrived",
        f"Scanned by {user['full_name']} ({user['role']}) at {used_at}.",
        link="/visitors",
    )
    fresh = await db["visitor_passes"].find_one({"id": p["id"]}, {"_id": 0})
    return fresh


@router.delete("/visitor-passes/{pid}")
async def cancel_pass(pid: str, user: dict = Depends(get_current_user)):
    db = get_db()
    p = await db["visitor_passes"].find_one({"id": pid})
    if not p:
        raise HTTPException(404, "Pass not found")
    if user["role"] != "admin" and p["tenant_id"] != user["id"]:
        raise HTTPException(403, "Forbidden")
    await db["visitor_passes"].update_one(
        {"id": pid}, {"$set": {"status": "cancelled"}}
    )
    return {"ok": True}
