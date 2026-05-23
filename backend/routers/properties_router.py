"""Property and Unit management."""
from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_user, require_role
from db import get_db
from models import Property, PropertyCreate, Unit, UnitCreate, new_id, now_iso

router = APIRouter(tags=["properties"])


@router.get("/properties")
async def list_properties(user: dict = Depends(get_current_user)):
    db = get_db()
    if user["role"] == "landlord":
        cursor = db["properties"].find({"landlord_id": user["id"]}, {"_id": 0})
    elif user["role"] == "tenant":
        # tenant sees only their landlord's property
        if not user.get("landlord_id"):
            return []
        cursor = db["properties"].find({"landlord_id": user["landlord_id"]}, {"_id": 0})
    else:  # caretaker
        if not user.get("landlord_id"):
            return []
        cursor = db["properties"].find({"landlord_id": user["landlord_id"]}, {"_id": 0})
    props = await cursor.to_list(500)
    # add unit counts
    for p in props:
        p["units_count"] = await db["units"].count_documents({"property_id": p["id"]})
    return props


@router.post("/properties", response_model=Property)
async def create_property(
    payload: PropertyCreate, user: dict = Depends(require_role("landlord"))
):
    db = get_db()
    doc = {
        "id": new_id(),
        "landlord_id": user["id"],
        "name": payload.name,
        "address": payload.address,
        "description": payload.description or "",
        "image_url": payload.image_url or "",
        "units_count": 0,
        "approval_status": "pending",
        "created_at": now_iso(),
    }
    await db["properties"].insert_one(doc)
    doc.pop("_id", None)
    return Property(**doc)


@router.delete("/properties/{prop_id}")
async def delete_property(prop_id: str, user: dict = Depends(require_role("landlord"))):
    db = get_db()
    res = await db["properties"].delete_one({"id": prop_id, "landlord_id": user["id"]})
    if res.deleted_count == 0:
        raise HTTPException(404, "Property not found")
    await db["units"].delete_many({"property_id": prop_id})
    return {"ok": True}


@router.get("/units")
async def list_units(
    property_id: str | None = None, user: dict = Depends(get_current_user)
):
    db = get_db()
    query: dict = {}
    if user["role"] == "landlord":
        query["landlord_id"] = user["id"]
    elif user["role"] == "tenant":
        if user.get("unit_id"):
            query["id"] = user["unit_id"]
        else:
            return []
    else:
        query["landlord_id"] = user.get("landlord_id")
    if property_id:
        query["property_id"] = property_id
    units = await db["units"].find(query, {"_id": 0}).to_list(1000)
    # attach tenant name
    tenant_ids = [u["tenant_id"] for u in units if u.get("tenant_id")]
    if tenant_ids:
        tenants = await db["users"].find(
            {"id": {"$in": tenant_ids}}, {"_id": 0, "id": 1, "full_name": 1, "phone": 1, "email": 1}
        ).to_list(1000)
        tenant_map = {t["id"]: t for t in tenants}
        for u in units:
            if u.get("tenant_id"):
                t = tenant_map.get(u["tenant_id"])
                if t:
                    u["tenant_name"] = t["full_name"]
                    u["tenant_phone"] = t["phone"]
                    u["tenant_email"] = t["email"]
    return units


@router.post("/units", response_model=Unit)
async def create_unit(payload: UnitCreate, user: dict = Depends(require_role("landlord"))):
    db = get_db()
    prop = await db["properties"].find_one(
        {"id": payload.property_id, "landlord_id": user["id"]}
    )
    if not prop:
        raise HTTPException(404, "Property not found")
    doc = {
        "id": new_id(),
        "landlord_id": user["id"],
        "property_id": payload.property_id,
        "unit_number": payload.unit_number,
        "rent_amount": payload.rent_amount,
        "bedrooms": payload.bedrooms,
        "description": payload.description or "",
        "tenant_id": None,
        "occupied": False,
        "created_at": now_iso(),
    }
    await db["units"].insert_one(doc)
    doc.pop("_id", None)
    return Unit(**doc)


@router.delete("/units/{unit_id}")
async def delete_unit(unit_id: str, user: dict = Depends(require_role("landlord"))):
    db = get_db()
    unit = await db["units"].find_one({"id": unit_id, "landlord_id": user["id"]})
    if not unit:
        raise HTTPException(404, "Unit not found")
    if unit.get("tenant_id"):
        raise HTTPException(400, "Unit has a tenant. Remove tenant first.")
    await db["units"].delete_one({"id": unit_id})
    return {"ok": True}
