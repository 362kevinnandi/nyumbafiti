"""Admin approval, oversight & moderation endpoints.

Separated from admin_router.py for clarity since this is the 'second pair of eyes'
sub-system: approve property/tenant/caretaker additions, view all bills, all issues,
and post moderation messages on issue threads.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import require_role
from db import get_db
from models import new_id, now_iso

router = APIRouter(prefix="/admin", tags=["admin-oversight"])


class ApprovalDecision(BaseModel):
    approve: bool
    reason: str = ""


# =================== Pending Approvals Queue ===================

@router.get("/approvals")
async def list_pending_approvals(_: dict = Depends(require_role("admin"))):
    db = get_db()
    properties = await db["properties"].find(
        {"approval_status": "pending"}, {"_id": 0}
    ).sort("created_at", -1).to_list(500)
    tenants = await db["users"].find(
        {"role": "tenant", "approval_status": "pending"},
        {"_id": 0, "password_hash": 0},
    ).sort("created_at", -1).to_list(500)
    caretakers = await db["users"].find(
        {"role": "caretaker", "approval_status": "pending"},
        {"_id": 0, "password_hash": 0},
    ).sort("created_at", -1).to_list(500)
    security = await db["users"].find(
        # Security personnel are landlord-managed (no admin approval) — kept for backwards-compat
        # but no longer surfaced in the queue.
        {"role": "security", "approval_status": "pending"},
        {"_id": 0, "password_hash": 0},
    ).sort("created_at", -1).to_list(500)
    # Auto-approve any legacy pending security users (one-time sweep)
    if security:
        await db["users"].update_many(
            {"role": "security", "approval_status": "pending"},
            {"$set": {"approval_status": "approved", "updated_at": now_iso()}},
        )
        security = []

    # Enrich with landlord names + unit info for context
    all_landlord_ids = list({
        *[p["landlord_id"] for p in properties],
        *[t["landlord_id"] for t in tenants if t.get("landlord_id")],
        *[c["landlord_id"] for c in caretakers if c.get("landlord_id")],
        *[s["landlord_id"] for s in security if s.get("landlord_id")],
    })
    landlords = await db["users"].find(
        {"id": {"$in": all_landlord_ids}}, {"_id": 0, "id": 1, "full_name": 1, "email": 1}
    ).to_list(500) if all_landlord_ids else []
    l_map = {ld["id"]: ld for ld in landlords}

    for items in (properties, tenants, caretakers, security):
        for it in items:
            ll = l_map.get(it.get("landlord_id"))
            if ll:
                it["landlord_name"] = ll.get("full_name", "")
                it["landlord_email"] = ll.get("email", "")

    # For tenants, also include unit + property name
    unit_ids = [t["unit_id"] for t in tenants if t.get("unit_id")]
    if unit_ids:
        units = await db["units"].find({"id": {"$in": unit_ids}}, {"_id": 0}).to_list(500)
        u_map = {u["id"]: u for u in units}
        prop_ids = list({u["property_id"] for u in units})
        props_by_id = {
            p["id"]: p
            for p in await db["properties"].find({"id": {"$in": prop_ids}}, {"_id": 0}).to_list(500)
        }
        for t in tenants:
            u = u_map.get(t.get("unit_id"))
            if u:
                t["unit_number"] = u["unit_number"]
                t["rent_amount"] = u["rent_amount"]
                p = props_by_id.get(u["property_id"])
                if p:
                    t["property_name"] = p["name"]

    return {
        "properties": properties,
        "tenants": tenants,
        "caretakers": caretakers,
        "security": security,
        "total_pending": len(properties) + len(tenants) + len(caretakers) + len(security),
    }


@router.post("/approvals/property/{property_id}")
async def decide_property(
    property_id: str,
    decision: ApprovalDecision,
    admin: dict = Depends(require_role("admin")),
):
    db = get_db()
    prop = await db["properties"].find_one({"id": property_id})
    if not prop:
        raise HTTPException(404, "Property not found")
    new_status = "approved" if decision.approve else "rejected"
    await db["properties"].update_one(
        {"id": property_id},
        {
            "$set": {
                "approval_status": new_status,
                "approval_decided_by": admin["id"],
                "approval_decided_at": now_iso(),
                "rejection_reason": decision.reason if not decision.approve else "",
            }
        },
    )
    return {"ok": True, "status": new_status}


@router.post("/approvals/user/{user_id}")
async def decide_user(
    user_id: str,
    decision: ApprovalDecision,
    admin: dict = Depends(require_role("admin")),
):
    db = get_db()
    user = await db["users"].find_one({"id": user_id})
    if not user:
        raise HTTPException(404, "User not found")
    if user["role"] not in ("tenant", "caretaker", "security"):
        raise HTTPException(400, "Only tenants and caretakers require approval")
    new_status = "approved" if decision.approve else "rejected"
    await db["users"].update_one(
        {"id": user_id},
        {
            "$set": {
                "approval_status": new_status,
                "approval_decided_by": admin["id"],
                "approval_decided_at": now_iso(),
                "rejection_reason": decision.reason if not decision.approve else "",
            }
        },
    )
    return {"ok": True, "status": new_status}


# =================== Oversight Views ===================

@router.get("/bills")
async def list_all_bills(
    status: str | None = None, _: dict = Depends(require_role("admin"))
):
    db = get_db()
    query: dict = {}
    if status:
        query["status"] = status
    bills = await db["bills"].find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    if bills:
        tenant_ids = list({b["tenant_id"] for b in bills})
        landlord_ids = list({b["landlord_id"] for b in bills})
        unit_ids = list({b["unit_id"] for b in bills})
        prop_ids = list({b["property_id"] for b in bills})
        tenants = await db["users"].find(
            {"id": {"$in": tenant_ids}}, {"_id": 0, "id": 1, "full_name": 1, "phone": 1}
        ).to_list(1000)
        landlords = await db["users"].find(
            {"id": {"$in": landlord_ids}}, {"_id": 0, "id": 1, "full_name": 1}
        ).to_list(1000)
        units = await db["units"].find({"id": {"$in": unit_ids}}, {"_id": 0}).to_list(1000)
        props = await db["properties"].find({"id": {"$in": prop_ids}}, {"_id": 0}).to_list(1000)
        t_map = {t["id"]: t for t in tenants}
        l_map = {ld["id"]: ld for ld in landlords}
        u_map = {u["id"]: u for u in units}
        p_map = {p["id"]: p for p in props}
        for b in bills:
            t = t_map.get(b["tenant_id"])
            if t:
                b["tenant_name"] = t["full_name"]
                b["tenant_phone"] = t.get("phone", "")
            ld = l_map.get(b["landlord_id"])
            if ld:
                b["landlord_name"] = ld["full_name"]
            u = u_map.get(b["unit_id"])
            if u:
                b["unit_number"] = u["unit_number"]
            p = p_map.get(b["property_id"])
            if p:
                b["property_name"] = p["name"]
    return bills


@router.get("/issues")
async def list_all_issues(
    status: str | None = None, _: dict = Depends(require_role("admin"))
):
    db = get_db()
    query: dict = {}
    if status:
        query["status"] = status
    issues = await db["issues"].find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    if issues:
        tenant_ids = list({i["tenant_id"] for i in issues})
        landlord_ids = list({i["landlord_id"] for i in issues})
        unit_ids = list({i["unit_id"] for i in issues})
        prop_ids = list({i["property_id"] for i in issues})
        assigned_ids = list({i["assigned_to"] for i in issues if i.get("assigned_to")})
        tenants = await db["users"].find(
            {"id": {"$in": tenant_ids + assigned_ids}}, {"_id": 0, "id": 1, "full_name": 1, "phone": 1, "role": 1}
        ).to_list(1000)
        landlords = await db["users"].find(
            {"id": {"$in": landlord_ids}}, {"_id": 0, "id": 1, "full_name": 1}
        ).to_list(1000)
        units = await db["units"].find({"id": {"$in": unit_ids}}, {"_id": 0}).to_list(1000)
        props = await db["properties"].find({"id": {"$in": prop_ids}}, {"_id": 0}).to_list(1000)
        u_by_id = {t["id"]: t for t in tenants}
        l_map = {ld["id"]: ld for ld in landlords}
        un_map = {u["id"]: u for u in units}
        p_map = {p["id"]: p for p in props}
        for i in issues:
            t = u_by_id.get(i["tenant_id"])
            if t:
                i["tenant_name"] = t["full_name"]
                i["tenant_phone"] = t.get("phone", "")
            ld = l_map.get(i["landlord_id"])
            if ld:
                i["landlord_name"] = ld["full_name"]
            u = un_map.get(i["unit_id"])
            if u:
                i["unit_number"] = u["unit_number"]
            p = p_map.get(i["property_id"])
            if p:
                i["property_name"] = p["name"]
            assigned = u_by_id.get(i.get("assigned_to") or "")
            if assigned:
                i["assigned_to_name"] = assigned["full_name"]
    return issues


# Admin can read AND post in any issue thread (acts as mediator)
@router.get("/issues/{issue_id}/messages")
async def admin_get_issue_messages(
    issue_id: str, _: dict = Depends(require_role("admin"))
):
    db = get_db()
    issue = await db["issues"].find_one({"id": issue_id})
    if not issue:
        raise HTTPException(404, "Issue not found")
    msgs = await db["issue_messages"].find(
        {"issue_id": issue_id}, {"_id": 0}
    ).sort("created_at", 1).to_list(1000)
    return msgs


class AdminMessage(BaseModel):
    body: str


@router.post("/issues/{issue_id}/messages")
async def admin_post_issue_message(
    issue_id: str,
    payload: AdminMessage,
    admin: dict = Depends(require_role("admin")),
):
    db = get_db()
    issue = await db["issues"].find_one({"id": issue_id})
    if not issue:
        raise HTTPException(404, "Issue not found")
    msg = {
        "id": new_id(),
        "issue_id": issue_id,
        "author_id": admin["id"],
        "author_name": admin["full_name"],
        "author_role": "admin",
        "body": payload.body,
        "created_at": now_iso(),
    }
    await db["issue_messages"].insert_one(msg)
    await db["issues"].update_one(
        {"id": issue_id}, {"$set": {"updated_at": now_iso()}}
    )
    msg.pop("_id", None)
    return msg
