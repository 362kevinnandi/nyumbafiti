"""Issues / ticketing system with threaded messages."""
from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_user, require_role
from db import get_db
from models import IssueCreate, IssueMessageCreate, IssueUpdate, new_id, now_iso

router = APIRouter(tags=["issues"])


@router.get("/issues")
async def list_issues(user: dict = Depends(get_current_user)):
    db = get_db()
    if user["role"] == "landlord":
        query = {"landlord_id": user["id"]}
    elif user["role"] == "tenant":
        query = {"tenant_id": user["id"]}
    elif user["role"] == "caretaker":
        query = {"$or": [{"assigned_to": user["id"]}, {"landlord_id": user.get("landlord_id")}]}
    else:
        return []
    issues = await db["issues"].find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    # attach tenant / unit info
    tenant_ids = list({i["tenant_id"] for i in issues})
    unit_ids = list({i["unit_id"] for i in issues})
    if tenant_ids:
        tenants = await db["users"].find(
            {"id": {"$in": tenant_ids}}, {"_id": 0, "id": 1, "full_name": 1, "phone": 1}
        ).to_list(1000)
        t_map = {t["id"]: t for t in tenants}
    else:
        t_map = {}
    if unit_ids:
        units = await db["units"].find({"id": {"$in": unit_ids}}, {"_id": 0}).to_list(1000)
        u_map = {u["id"]: u for u in units}
    else:
        u_map = {}
    for i in issues:
        t = t_map.get(i["tenant_id"])
        if t:
            i["tenant_name"] = t["full_name"]
            i["tenant_phone"] = t["phone"]
        u = u_map.get(i["unit_id"])
        if u:
            i["unit_number"] = u["unit_number"]
        if i.get("assigned_to"):
            ct = await db["users"].find_one({"id": i["assigned_to"]}, {"_id": 0, "full_name": 1})
            if ct:
                i["assigned_to_name"] = ct["full_name"]
    return issues


@router.post("/issues")
async def create_issue(payload: IssueCreate, user: dict = Depends(require_role("tenant"))):
    db = get_db()
    if not user.get("unit_id") or not user.get("landlord_id"):
        raise HTTPException(400, "Tenant has no unit assigned")
    unit = await db["units"].find_one({"id": user["unit_id"]}, {"_id": 0})
    if not unit:
        raise HTTPException(404, "Unit not found")
    doc = {
        "id": new_id(),
        "landlord_id": user["landlord_id"],
        "tenant_id": user["id"],
        "unit_id": user["unit_id"],
        "property_id": unit["property_id"],
        "title": payload.title,
        "description": payload.description,
        "priority": payload.priority,
        "status": "open",
        "assigned_to": None,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db["issues"].insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.patch("/issues/{issue_id}")
async def update_issue(
    issue_id: str, payload: IssueUpdate, user: dict = Depends(get_current_user)
):
    db = get_db()
    issue = await db["issues"].find_one({"id": issue_id})
    if not issue:
        raise HTTPException(404, "Issue not found")
    # permission: landlord (own), caretaker (assigned), tenant cannot update
    if user["role"] == "landlord" and issue["landlord_id"] != user["id"]:
        raise HTTPException(403, "Forbidden")
    if user["role"] == "caretaker" and issue.get("assigned_to") != user["id"]:
        # allow caretakers in the same landlord network to claim
        if issue["landlord_id"] != user.get("landlord_id"):
            raise HTTPException(403, "Forbidden")
    if user["role"] == "tenant":
        raise HTTPException(403, "Tenants cannot update issues")
    if user["role"] == "caretaker" and user.get("approval_status") == "pending":
        raise HTTPException(
            403,
            "Your caretaker account is pending admin verification. You cannot take action on tickets yet.",
        )

    update = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    if update:
        update["updated_at"] = now_iso()
        await db["issues"].update_one({"id": issue_id}, {"$set": update})
    fresh = await db["issues"].find_one({"id": issue_id}, {"_id": 0})
    return fresh


@router.get("/issues/{issue_id}/messages")
async def get_messages(issue_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    issue = await db["issues"].find_one({"id": issue_id})
    if not issue:
        raise HTTPException(404, "Issue not found")
    # access control
    allowed = (
        (user["role"] == "landlord" and issue["landlord_id"] == user["id"])
        or (user["role"] == "tenant" and issue["tenant_id"] == user["id"])
        or (user["role"] == "caretaker" and issue["landlord_id"] == user.get("landlord_id"))
    )
    if not allowed:
        raise HTTPException(403, "Forbidden")
    msgs = await db["issue_messages"].find({"issue_id": issue_id}, {"_id": 0}).sort("created_at", 1).to_list(1000)
    return msgs


@router.post("/issues/{issue_id}/messages")
async def post_message(
    issue_id: str, payload: IssueMessageCreate, user: dict = Depends(get_current_user)
):
    db = get_db()
    issue = await db["issues"].find_one({"id": issue_id})
    if not issue:
        raise HTTPException(404, "Issue not found")
    allowed = (
        (user["role"] == "landlord" and issue["landlord_id"] == user["id"])
        or (user["role"] == "tenant" and issue["tenant_id"] == user["id"])
        or (user["role"] == "caretaker" and issue["landlord_id"] == user.get("landlord_id"))
    )
    if not allowed:
        raise HTTPException(403, "Forbidden")

    msg = {
        "id": new_id(),
        "issue_id": issue_id,
        "author_id": user["id"],
        "author_name": user["full_name"],
        "author_role": user["role"],
        "body": payload.body,
        "created_at": now_iso(),
    }
    await db["issue_messages"].insert_one(msg)
    await db["issues"].update_one({"id": issue_id}, {"$set": {"updated_at": now_iso()}})
    msg.pop("_id", None)
    return msg
