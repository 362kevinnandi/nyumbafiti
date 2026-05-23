"""Tenant & Caretaker management by landlord."""
from fastapi import APIRouter, Depends, HTTPException
from pymongo.errors import DuplicateKeyError

from auth import hash_password, require_role
from db import get_db
from models import CaretakerCreate, TenantCreate, new_id, now_iso

router = APIRouter(tags=["users"])


@router.post("/tenants")
async def create_tenant(
    payload: TenantCreate, user: dict = Depends(require_role("landlord"))
):
    db = get_db()
    unit = await db["units"].find_one(
        {"id": payload.unit_id, "landlord_id": user["id"]}
    )
    if not unit:
        raise HTTPException(404, "Unit not found")
    if unit.get("tenant_id"):
        raise HTTPException(400, "Unit already occupied")

    tenant_doc = {
        "id": new_id(),
        "email": payload.email.lower(),
        "full_name": payload.full_name,
        "phone": payload.phone,
        "role": "tenant",
        "password_hash": hash_password(payload.password),
        "landlord_id": user["id"],
        "unit_id": payload.unit_id,
        "approval_status": "pending",
        "created_at": now_iso(),
    }
    try:
        await db["users"].insert_one(tenant_doc)
    except DuplicateKeyError:
        raise HTTPException(400, "Email already registered")

    await db["units"].update_one(
        {"id": payload.unit_id},
        {"$set": {"tenant_id": tenant_doc["id"], "occupied": True}},
    )
    tenant_doc.pop("password_hash", None)
    tenant_doc.pop("_id", None)
    return tenant_doc


@router.get("/tenants")
async def list_tenants(user: dict = Depends(require_role("landlord"))):
    db = get_db()
    tenants = await db["users"].find(
        {"landlord_id": user["id"], "role": "tenant"},
        {"_id": 0, "password_hash": 0},
    ).to_list(1000)
    # attach unit info
    unit_ids = [t["unit_id"] for t in tenants if t.get("unit_id")]
    if unit_ids:
        units = await db["units"].find(
            {"id": {"$in": unit_ids}}, {"_id": 0}
        ).to_list(1000)
        unit_map = {u["id"]: u for u in units}
        props = await db["properties"].find(
            {"id": {"$in": list({u["property_id"] for u in units})}}, {"_id": 0}
        ).to_list(1000)
        prop_map = {p["id"]: p for p in props}
        for t in tenants:
            u = unit_map.get(t.get("unit_id"))
            if u:
                t["unit_number"] = u["unit_number"]
                t["rent_amount"] = u["rent_amount"]
                p = prop_map.get(u["property_id"])
                t["property_name"] = p["name"] if p else ""
    return tenants


@router.delete("/tenants/{tenant_id}")
async def remove_tenant(tenant_id: str, user: dict = Depends(require_role("landlord"))):
    db = get_db()
    tenant = await db["users"].find_one(
        {"id": tenant_id, "landlord_id": user["id"], "role": "tenant"}
    )
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    if tenant.get("unit_id"):
        await db["units"].update_one(
            {"id": tenant["unit_id"]},
            {"$set": {"tenant_id": None, "occupied": False}},
        )
    await db["users"].delete_one({"id": tenant_id})
    return {"ok": True}


@router.post("/caretakers")
async def create_caretaker(
    payload: CaretakerCreate, user: dict = Depends(require_role("landlord"))
):
    db = get_db()
    doc = {
        "id": new_id(),
        "email": payload.email.lower(),
        "full_name": payload.full_name,
        "phone": payload.phone,
        "role": "caretaker",
        "password_hash": hash_password(payload.password),
        "landlord_id": user["id"],
        "unit_id": None,
        "approval_status": "pending",
        "created_at": now_iso(),
    }
    try:
        await db["users"].insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(400, "Email already registered")
    doc.pop("password_hash", None)
    doc.pop("_id", None)
    return doc


@router.get("/caretakers")
async def list_caretakers(user: dict = Depends(require_role("landlord"))):
    db = get_db()
    cts = await db["users"].find(
        {"landlord_id": user["id"], "role": "caretaker"},
        {"_id": 0, "password_hash": 0},
    ).to_list(1000)
    return cts


@router.delete("/caretakers/{caretaker_id}")
async def remove_caretaker(
    caretaker_id: str, user: dict = Depends(require_role("landlord"))
):
    db = get_db()
    res = await db["users"].delete_one(
        {"id": caretaker_id, "landlord_id": user["id"], "role": "caretaker"}
    )
    if res.deleted_count == 0:
        raise HTTPException(404, "Caretaker not found")
    return {"ok": True}
