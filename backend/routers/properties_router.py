"""Property and Unit management."""
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Form,
)
from auth import get_current_user, require_role
from db import get_db
from models import (
    PROPERTY_CATEGORIES,
    Property,
    PropertyUpdate,
    Unit,
    UnitCreate,
    new_id,
    now_iso,
)
from typing import List, Optional
import os
import shutil

router = APIRouter(tags=["properties"])

UPLOAD_DIR = "uploads/properties"

os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.get("/properties")
async def list_properties(user: dict = Depends(get_current_user)):
    db = get_db()
    if user["role"] == "admin":
        cursor = db["properties"].find({}, {"_id": 0})
    elif user["role"] == "landlord":
        cursor = db["properties"].find({"landlord_id": user["id"]}, {"_id": 0})
    elif user["role"] == "tenant":
        if not user.get("landlord_id"):
            return []
        cursor = db["properties"].find({"landlord_id": user["landlord_id"]}, {"_id": 0})
    else:  # caretaker
        if not user.get("landlord_id"):
            return []
        cursor = db["properties"].find({"landlord_id": user["landlord_id"]}, {"_id": 0})
    props = await cursor.to_list(500)
    for p in props:
        p["units_count"] = await db["units"].count_documents({"property_id": p["id"]})
    return props


@router.post("/properties", response_model=Property)
async def create_property(
    name: str = Form(...),
    address: str = Form(...),
    description: str = Form(""),
    category: str = Form("apartment"),
    images: List[UploadFile] = File([]),
    user: dict = Depends(require_role("landlord")),
):
    db = get_db()

    if category not in PROPERTY_CATEGORIES:
        raise HTTPException(400, f"Invalid category. Must be one of: {', '.join(PROPERTY_CATEGORIES)}")

    image_paths = []
    for image in images[:5]:
        if not image.filename:
            continue
        filename = f"{new_id()}_{image.filename}"
        file_path = f"{UPLOAD_DIR}/{filename}"
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
        image_paths.append(file_path)

    doc = {
        "id": new_id(),
        "landlord_id": user["id"],
        "name": name,
        "address": address,
        "description": description,
        "category": category,
        "featured": False,
        "images": image_paths,
        "units_count": 0,
        "approval_status": "pending",
        "created_at": now_iso(),
    }

    await db["properties"].insert_one(doc)
    doc.pop("_id", None)
    return Property(**doc)


@router.patch("/properties/{prop_id}", response_model=Property)
async def update_property(
    prop_id: str,
    payload: PropertyUpdate,
    user: dict = Depends(get_current_user),
):
    """Edit a property. Landlord can edit own; admin can edit any + toggle 'featured'."""
    db = get_db()
    query: dict = {"id": prop_id}
    if user["role"] == "landlord":
        query["landlord_id"] = user["id"]
    elif user["role"] != "admin":
        raise HTTPException(403, "Forbidden")

    prop = await db["properties"].find_one(query)
    if not prop:
        raise HTTPException(404, "Property not found")

    updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    # Only admin can change 'featured'
    if "featured" in updates and user["role"] != "admin":
        updates.pop("featured")

    if "category" in updates and updates["category"] not in PROPERTY_CATEGORIES:
        raise HTTPException(400, "Invalid category")

    if updates:
        updates["updated_at"] = now_iso()
        await db["properties"].update_one({"id": prop_id}, {"$set": updates})

    fresh = await db["properties"].find_one({"id": prop_id}, {"_id": 0})
    fresh["units_count"] = await db["units"].count_documents({"property_id": prop_id})
    # Backfill new fields for old docs
    fresh.setdefault("category", "apartment")
    fresh.setdefault("featured", False)
    return Property(**fresh)


@router.delete("/properties/{prop_id}")
async def delete_property(prop_id: str, user: dict = Depends(get_current_user)):
    """Landlord deletes their own property; admin can delete any."""
    db = get_db()
    if user["role"] == "admin":
        res = await db["properties"].delete_one({"id": prop_id})
    elif user["role"] == "landlord":
        res = await db["properties"].delete_one(
            {"id": prop_id, "landlord_id": user["id"]}
        )
    else:
        raise HTTPException(403, "Forbidden")
    if res.deleted_count == 0:
        raise HTTPException(404, "Property not found")
    await db["units"].delete_many({"property_id": prop_id})
    return {"ok": True}


@router.get("/units")
async def list_units(
    property_id: Optional[str] = None, user: dict = Depends(get_current_user)
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
    elif user["role"] == "admin":
        pass
    else:
        query["landlord_id"] = user.get("landlord_id")
    if property_id:
        query["property_id"] = property_id
    units = await db["units"].find(query, {"_id": 0}).to_list(1000)
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
