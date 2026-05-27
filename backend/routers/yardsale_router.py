"""Phase 3 — Tenant Yard Sale Marketplace with optional paid 'Feature' boost via M-Pesa."""
import asyncio
import os
import shutil
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from auth import get_current_user, require_role
from db import get_db
from models import (
    YARD_SALE_CATEGORIES, YARD_SALE_FEATURE_FEE_KES, YARD_SALE_FEATURE_DAYS,
    YARD_SALE_CONTACT_UNLOCK_KES, YARD_SALE_BROADCAST_FEE_KES,
    YardSaleUpdate, new_id, now_iso,
)
from mpesa import is_demo_mode, normalize_phone, schedule_demo_callback, stk_push

router = APIRouter(tags=["yard-sale"])

UPLOAD_DIR = "uploads/yardsale"
os.makedirs(UPLOAD_DIR, exist_ok=True)
ALLOWED_MIME_PREFIXES = ("image/",)


async def _save_images(files: List[UploadFile]) -> List[str]:
    out: List[str] = []
    for f in files[:5]:
        if not f.filename:
            continue
        if f.content_type and not any(f.content_type.startswith(p) for p in ALLOWED_MIME_PREFIXES):
            raise HTTPException(400, f"Only image files allowed (got {f.content_type})")
        filename = f"{new_id()}_{f.filename}"
        path = f"{UPLOAD_DIR}/{filename}"
        with open(path, "wb") as buf:
            shutil.copyfileobj(f.file, buf)
        out.append(path)
    return out


async def _expire_stale() -> None:
    """Auto-unfeature listings whose featured_until has passed."""
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    await db["yard_sale"].update_many(
        {"featured": True, "featured_until": {"$lt": now}},
        {"$set": {"featured": False}},
    )


def _mask_contact(listing: dict, viewer: dict) -> dict:
    """Hide seller_phone/seller_email when contact_unlocked=False, except for owner and admin."""
    is_owner = viewer.get("id") == listing.get("seller_id")
    is_admin = viewer.get("role") == "admin"
    if not (listing.get("contact_unlocked") or is_owner or is_admin):
        out = {**listing, "seller_phone": "", "seller_email": ""}
        return out
    return listing


def _can_see_listing(listing: dict, viewer: dict) -> bool:
    """Property-scoped listings are visible only to same-property tenants + same-landlord staff + admin + seller."""
    if viewer.get("role") == "admin":
        return True
    if viewer.get("id") == listing.get("seller_id"):
        return True
    if listing.get("scope") == "all":
        return True
    # property-scoped: must share landlord_id
    return (
        listing.get("landlord_id")
        and viewer.get("landlord_id") == listing.get("landlord_id")
    ) or viewer.get("id") == listing.get("landlord_id")


# ====================== LISTING CRUD ======================

@router.post("/yard-sale/listings")
async def create_listing(
    title: str = Form(...),
    description: str = Form(""),
    price: float = Form(...),
    category: str = Form("other"),
    scope: str = Form("property"),
    images: List[UploadFile] = File([]),
    user: dict = Depends(require_role("tenant", "landlord", "caretaker", "security")),
):
    if category not in YARD_SALE_CATEGORIES:
        raise HTTPException(400, f"Invalid category. Allowed: {', '.join(YARD_SALE_CATEGORIES)}")
    if scope not in ("property", "all"):
        raise HTTPException(400, "Scope must be 'property' or 'all'")
    if price < 0:
        raise HTTPException(400, "Price must be >= 0")

    paths = await _save_images(images)
    db = get_db()
    doc = {
        "id": new_id(),
        "seller_id": user["id"],
        "seller_name": user["full_name"],
        "seller_phone": user.get("phone", ""),
        "seller_email": user.get("email", ""),
        "landlord_id": user.get("landlord_id"),
        "property_id": None,
        "title": title,
        "description": description,
        "price": float(price),
        "category": category,
        "images": paths,
        "featured": False,
        "featured_until": None,
        "contact_unlocked": False,
        # New listings start property-scoped (free). Broadcast requires KES 50 STK.
        "scope": "property",
        "status": "active",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    # If tenant, attach property via unit
    if user["role"] == "tenant" and user.get("unit_id"):
        unit = await db["units"].find_one({"id": user["unit_id"]})
        if unit:
            doc["property_id"] = unit["property_id"]
    await db["yard_sale"].insert_one(doc)
    doc.pop("_id", None)
    return _mask_contact(doc, user)


@router.get("/yard-sale/listings")
async def list_listings(
    category: Optional[str] = None,
    max_price: Optional[float] = None,
    status: str = "active",
    user: dict = Depends(get_current_user),
):
    await _expire_stale()
    db = get_db()
    query: dict = {"status": status}
    if category:
        query["category"] = category
    if max_price is not None:
        query["price"] = {"$lte": max_price}
    items = await db["yard_sale"].find(query, {"_id": 0}).sort(
        [("featured", -1), ("created_at", -1)]
    ).to_list(500)
    visible = [it for it in items if _can_see_listing(it, user)]
    return [_mask_contact(it, user) for it in visible]


@router.get("/yard-sale/listings/{lid}")
async def get_listing(lid: str, user: dict = Depends(get_current_user)):
    db = get_db()
    item = await db["yard_sale"].find_one({"id": lid}, {"_id": 0})
    if not item:
        raise HTTPException(404, "Listing not found")
    if not _can_see_listing(item, user):
        raise HTTPException(403, "This listing is not available to you")
    return _mask_contact(item, user)


@router.patch("/yard-sale/listings/{lid}")
async def update_listing(
    lid: str,
    payload: YardSaleUpdate,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    item = await db["yard_sale"].find_one({"id": lid})
    if not item:
        raise HTTPException(404, "Listing not found")
    if user["role"] != "admin" and item["seller_id"] != user["id"]:
        raise HTTPException(403, "Forbidden")
    updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if updates:
        updates["updated_at"] = now_iso()
        await db["yard_sale"].update_one({"id": lid}, {"$set": updates})
    fresh = await db["yard_sale"].find_one({"id": lid}, {"_id": 0})
    return fresh


@router.delete("/yard-sale/listings/{lid}")
async def delete_listing(lid: str, user: dict = Depends(get_current_user)):
    db = get_db()
    item = await db["yard_sale"].find_one({"id": lid})
    if not item:
        raise HTTPException(404, "Listing not found")
    if user["role"] != "admin" and item["seller_id"] != user["id"]:
        raise HTTPException(403, "Forbidden")
    await db["yard_sale"].delete_one({"id": lid})
    return {"ok": True}


# ====================== FEATURE BOOST via M-PESA ======================

@router.post("/yard-sale/listings/{lid}/feature")
async def feature_listing(
    lid: str,
    phone_number: str = Form(...),
    user: dict = Depends(get_current_user),
):
    """Initiate KES 100 STK push to feature this listing for 7 days."""
    db = get_db()
    item = await db["yard_sale"].find_one({"id": lid})
    if not item:
        raise HTTPException(404, "Listing not found")
    if user["role"] != "admin" and item["seller_id"] != user["id"]:
        raise HTTPException(403, "Forbidden")
    if item.get("featured") and item.get("featured_until", "") > now_iso():
        raise HTTPException(400, "Listing is already featured")

    phone = normalize_phone(phone_number)
    if not (phone.startswith("254") and len(phone) == 12 and phone.isdigit()):
        raise HTTPException(400, "Phone must be a valid Kenyan number")

    payment_id = new_id()
    payment_doc = {
        "id": payment_id,
        "bill_id": None,
        "viewing_id": None,
        "yard_sale_id": lid,
        "tenant_id": user["id"],
        "prospect_id": None,
        "landlord_id": item.get("landlord_id"),
        "amount": float(YARD_SALE_FEATURE_FEE_KES),
        "phone_number": phone,
        "status": "pending",
        "checkout_request_id": None,
        "merchant_request_id": None,
        "mpesa_receipt": None,
        "result_desc": None,
        "idempotency_key": f"yardsale-{lid}-{payment_id}",
        "purpose": "yard_sale_feature",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db["payments"].insert_one(payment_doc)

    callback_base = os.environ.get("MPESA_CALLBACK_BASE_URL", "")
    callback_secret = os.environ.get("MPESA_CALLBACK_SECRET", "secret")
    callback_url = f"{callback_base}/api/payments/mpesa/callback/{callback_secret}"

    try:
        from routers.payments_router import _process_callback_payload
        resp = await stk_push(
            phone=phone,
            amount=YARD_SALE_FEATURE_FEE_KES,
            account_ref=f"BOOST-{lid[:8]}",
            description="Feature listing",
            callback_url=callback_url,
        )
    except Exception as exc:
        await db["payments"].update_one(
            {"id": payment_id},
            {"$set": {"status": "failed", "result_desc": str(exc), "updated_at": now_iso()}},
        )
        raise HTTPException(502, f"M-Pesa request failed: {exc}")

    await db["payments"].update_one(
        {"id": payment_id},
        {"$set": {
            "checkout_request_id": resp.get("CheckoutRequestID"),
            "merchant_request_id": resp.get("MerchantRequestID"),
            "updated_at": now_iso(),
        }},
    )

    if resp.get("_demo") or is_demo_mode():
        asyncio.create_task(
            schedule_demo_callback(resp["CheckoutRequestID"], _process_callback_payload)
        )

    return {
        "payment_id": payment_id,
        "amount": YARD_SALE_FEATURE_FEE_KES,
        "demo_mode": is_demo_mode(),
        "message": resp.get("CustomerMessage", "STK push sent. Check your phone."),
    }


async def _initiate_yardsale_payment(
    lid: str,
    phone_number: str,
    amount: int,
    purpose: str,
    user: dict,
    account_ref_prefix: str,
    description: str,
) -> dict:
    """Shared M-Pesa STK init flow for yard sale monetization endpoints."""
    db = get_db()
    item = await db["yard_sale"].find_one({"id": lid})
    if not item:
        raise HTTPException(404, "Listing not found")
    if user["role"] != "admin" and item["seller_id"] != user["id"]:
        raise HTTPException(403, "Forbidden")

    phone = normalize_phone(phone_number)
    if not (phone.startswith("254") and len(phone) == 12 and phone.isdigit()):
        raise HTTPException(400, "Phone must be a valid Kenyan number")

    payment_id = new_id()
    payment_doc = {
        "id": payment_id,
        "bill_id": None,
        "viewing_id": None,
        "yard_sale_id": lid,
        "tenant_id": user["id"],
        "prospect_id": None,
        "landlord_id": item.get("landlord_id"),
        "amount": float(amount),
        "phone_number": phone,
        "status": "pending",
        "checkout_request_id": None,
        "merchant_request_id": None,
        "mpesa_receipt": None,
        "result_desc": None,
        "idempotency_key": f"{purpose}-{lid}-{payment_id}",
        "purpose": purpose,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db["payments"].insert_one(payment_doc)

    callback_base = os.environ.get("MPESA_CALLBACK_BASE_URL", "")
    callback_secret = os.environ.get("MPESA_CALLBACK_SECRET", "secret")
    callback_url = f"{callback_base}/api/payments/mpesa/callback/{callback_secret}"

    try:
        from routers.payments_router import _process_callback_payload
        resp = await stk_push(
            phone=phone,
            amount=amount,
            account_ref=f"{account_ref_prefix}-{lid[:8]}",
            description=description,
            callback_url=callback_url,
        )
    except Exception as exc:
        await db["payments"].update_one(
            {"id": payment_id},
            {"$set": {"status": "failed", "result_desc": str(exc), "updated_at": now_iso()}},
        )
        raise HTTPException(502, f"M-Pesa request failed: {exc}")

    await db["payments"].update_one(
        {"id": payment_id},
        {"$set": {
            "checkout_request_id": resp.get("CheckoutRequestID"),
            "merchant_request_id": resp.get("MerchantRequestID"),
            "updated_at": now_iso(),
        }},
    )

    if resp.get("_demo") or is_demo_mode():
        asyncio.create_task(
            schedule_demo_callback(resp["CheckoutRequestID"], _process_callback_payload)
        )

    return {
        "payment_id": payment_id,
        "amount": amount,
        "demo_mode": is_demo_mode(),
        "message": resp.get("CustomerMessage", "STK push sent. Check your phone."),
    }


@router.post("/yard-sale/listings/{lid}/unlock-contact")
async def unlock_contact(
    lid: str,
    phone_number: str = Form(...),
    user: dict = Depends(get_current_user),
):
    """Seller pays KES 35 once to make their contact (phone/email) visible to buyers."""
    db = get_db()
    item = await db["yard_sale"].find_one({"id": lid})
    if not item:
        raise HTTPException(404, "Listing not found")
    if item.get("contact_unlocked"):
        raise HTTPException(400, "Contact is already unlocked on this listing")
    return await _initiate_yardsale_payment(
        lid, phone_number, YARD_SALE_CONTACT_UNLOCK_KES,
        "yard_sale_contact", user, "CONTACT", "Unlock contact",
    )


@router.post("/yard-sale/listings/{lid}/broadcast")
async def broadcast_listing(
    lid: str,
    phone_number: str = Form(...),
    user: dict = Depends(get_current_user),
):
    """Seller pays KES 50 to make listing visible to ALL tenants across the platform (vs property-only)."""
    db = get_db()
    item = await db["yard_sale"].find_one({"id": lid})
    if not item:
        raise HTTPException(404, "Listing not found")
    if item.get("scope") == "all":
        raise HTTPException(400, "Listing is already broadcast to all tenants")
    return await _initiate_yardsale_payment(
        lid, phone_number, YARD_SALE_BROADCAST_FEE_KES,
        "yard_sale_broadcast", user, "BROADCAST", "Broadcast listing",
    )

