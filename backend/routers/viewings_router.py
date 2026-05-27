"""Public marketplace listings + viewing booking with M-Pesa fee."""
import asyncio
import os
import secrets
import string
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from auth import hash_password, require_role
from db import get_db
from mpesa import is_demo_mode, normalize_phone, schedule_demo_callback, schedule_status_poll, should_use_demo_fallback, stk_push
from models import VIEWING_FEE_KES, Viewing, ViewingCreate, new_id, now_iso

router = APIRouter(tags=["viewings"])


def _generate_password(length: int = 10) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


# ----------- Public marketplace -----------

@router.get("/public/listings")
async def public_listings(
    city: Optional[str] = None,
    max_rent: Optional[float] = None,
    category: Optional[str] = None,
    tenancy_type: Optional[str] = None,  # 'lease' or 'rental' — filter properties that support it
):
    """List all vacant units across all admin-approved properties (public)."""
    db = get_db()
    prop_filter: dict = {"approval_status": "approved"}
    if category:
        prop_filter["category"] = category
    if tenancy_type in ("lease", "rental"):
        prop_filter["tenancy_types"] = tenancy_type
    approved_props = await db["properties"].find(
        prop_filter, {"_id": 0, "id": 1}
    ).to_list(2000)
    approved_prop_ids = {p["id"] for p in approved_props}
    if not approved_prop_ids:
        return []
    query: dict = {"occupied": False, "property_id": {"$in": list(approved_prop_ids)}}
    if max_rent:
        query["rent_amount"] = {"$lte": max_rent}
    units = await db["units"].find(query, {"_id": 0}).to_list(500)
    if not units:
        return []
    prop_ids = list({u["property_id"] for u in units})
    landlord_ids = list({u["landlord_id"] for u in units})

    props = await db["properties"].find({"id": {"$in": prop_ids}}, {"_id": 0}).to_list(500)
    p_map = {p["id"]: p for p in props}
    if city:
        p_map = {pid: p for pid, p in p_map.items() if city.lower() in (p.get("address") or "").lower()}
    landlords = await db["users"].find(
        {"id": {"$in": landlord_ids}}, {"_id": 0, "id": 1, "full_name": 1}
    ).to_list(500)
    l_map = {ld["id"]: ld for ld in landlords}

    listings = []
    for u in units:
        prop = p_map.get(u["property_id"])
        if not prop:
            continue
        listings.append({
            "id": u["id"],
            "unit_number": u["unit_number"],
            "rent_amount": u["rent_amount"],
            "bedrooms": u["bedrooms"],
            "description": u.get("description", ""),
            "property": {
                "id": prop["id"],
                "name": prop["name"],
                "address": prop["address"],
                "description": prop.get("description", ""),
                "category": prop.get("category", "apartment"),
                "sub_type": prop.get("sub_type"),
                "tenancy_types": prop.get("tenancy_types") or ["rental"],
                "featured": bool(prop.get("featured", False)),
                "images": prop.get("images", []),
            },
            "featured": bool(prop.get("featured", False)),
            "category": prop.get("category", "apartment"),
            "sub_type": prop.get("sub_type"),
            "tenancy_types": prop.get("tenancy_types") or ["rental"],
            "landlord_name": l_map.get(u["landlord_id"], {}).get("full_name", "Verified Landlord"),
        })
    # Featured first, then by rent ascending as tiebreaker
    listings.sort(key=lambda x: (not x["featured"], x["rent_amount"]))
    return listings


@router.get("/public/listings/{unit_id}")
async def public_listing_detail(unit_id: str):
    db = get_db()
    unit = await db["units"].find_one({"id": unit_id, "occupied": False}, {"_id": 0})
    if not unit:
        raise HTTPException(404, "Listing not found or no longer available")
    prop = await db["properties"].find_one({"id": unit["property_id"]}, {"_id": 0})
    if not prop or prop.get("approval_status") != "approved":
        raise HTTPException(404, "Listing not found or no longer available")
    landlord = await db["users"].find_one(
        {"id": unit["landlord_id"]}, {"_id": 0, "full_name": 1}
    )
    return {
        "id": unit["id"],
        "unit_number": unit["unit_number"],
        "rent_amount": unit["rent_amount"],
        "bedrooms": unit["bedrooms"],
        "description": unit.get("description", ""),
        "viewing_fee": VIEWING_FEE_KES,
       "property": {
    "id": prop["id"],
    "name": prop["name"],
    "address": prop["address"],
    "description": prop.get("description", ""),
    "category": prop.get("category", "apartment"),
    "featured": bool(prop.get("featured", False)),
    "images": prop.get("images", []),
},
        "landlord_name": (landlord or {}).get("full_name", "Verified Landlord"),
    }


# ----------- Viewing booking + payment -----------

@router.post("/public/viewings")
async def book_viewing(payload: ViewingCreate):
    """Create a viewing record + auto-create prospect user + initiate M-Pesa STK push."""
    db = get_db()
    unit = await db["units"].find_one({"id": payload.unit_id, "occupied": False}, {"_id": 0})
    if not unit:
        raise HTTPException(404, "This unit is no longer available for viewing.")

    phone = normalize_phone(payload.prospect_phone)
    if not (phone.startswith("254") and len(phone) == 12 and phone.isdigit()):
        raise HTTPException(400, "Phone must be a valid Kenyan number (e.g. 0712345678)")

    # find or create prospect
    email_lower = payload.prospect_email.lower()
    prospect = await db["users"].find_one({"email": email_lower})
    generated_password = None
    if prospect:
        if prospect.get("role") != "prospect":
            raise HTTPException(
                400,
                "This email is registered under another account. Please use a different email or login.",
            )
    else:
        generated_password = _generate_password()
        prospect = {
            "id": new_id(),
            "email": email_lower,
            "full_name": payload.prospect_name,
            "phone": phone,
            "role": "prospect",
            "password_hash": hash_password(generated_password),
            "landlord_id": None,
            "unit_id": None,
            "created_at": now_iso(),
        }
        await db["users"].insert_one(prospect)

    viewing_id = new_id()
    payment_id = new_id()
    viewing_doc = {
        "id": viewing_id,
        "unit_id": unit["id"],
        "property_id": unit["property_id"],
        "landlord_id": unit["landlord_id"],
        "prospect_id": prospect["id"],
        "prospect_name": payload.prospect_name,
        "prospect_email": email_lower,
        "prospect_phone": phone,
        "scheduled_date": payload.scheduled_date,
        "scheduled_time": payload.scheduled_time,
        "notes": payload.notes or "",
        "status": "pending_payment",
        "viewing_fee": VIEWING_FEE_KES,
        "payment_id": payment_id,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db["viewings"].insert_one(viewing_doc)

    # payment record
    payment_doc = {
        "id": payment_id,
        "bill_id": None,
        "viewing_id": viewing_id,
        "tenant_id": None,
        "prospect_id": prospect["id"],
        "landlord_id": unit["landlord_id"],
        "amount": float(VIEWING_FEE_KES),
        "phone_number": phone,
        "status": "pending",
        "checkout_request_id": None,
        "merchant_request_id": None,
        "mpesa_receipt": None,
        "result_desc": None,
        "idempotency_key": f"viewing-{viewing_id}",
        "purpose": "viewing_fee",
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
            amount=VIEWING_FEE_KES,
            account_ref=f"VIEW-{viewing_id[:8]}",
            description="Viewing fee",
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
        {
            "$set": {
                "checkout_request_id": resp.get("CheckoutRequestID"),
                "merchant_request_id": resp.get("MerchantRequestID"),
                "updated_at": now_iso(),
            }
        },
    )

    if should_use_demo_fallback(resp):
        asyncio.create_task(
            schedule_demo_callback(resp["CheckoutRequestID"], _process_callback_payload)
        )
    elif resp.get("CheckoutRequestID"):
        asyncio.create_task(
            schedule_status_poll(resp["CheckoutRequestID"], _process_callback_payload)
        )

    return {
        "viewing_id": viewing_id,
        "payment_id": payment_id,
        "prospect_email": email_lower,
        "prospect_password": generated_password,  # only returned for newly created prospects
        "demo_mode": is_demo_mode(),
        "message": resp.get("CustomerMessage", "STK push sent. Check your phone."),
    }


@router.get("/public/viewings/{viewing_id}")
async def get_viewing_status(viewing_id: str):
    """Poll viewing status. Returns sanitized version - reveals contact only once paid."""
    db = get_db()
    viewing = await db["viewings"].find_one({"id": viewing_id}, {"_id": 0})
    if not viewing:
        raise HTTPException(404, "Viewing not found")
    payment = await db["payments"].find_one({"id": viewing["payment_id"]}, {"_id": 0})
    base = {
        "id": viewing["id"],
        "status": viewing["status"],
        "scheduled_date": viewing["scheduled_date"],
        "scheduled_time": viewing["scheduled_time"],
        "payment_status": payment["status"] if payment else "unknown",
        "payment_result_desc": payment.get("result_desc") if payment else None,
        "viewing_fee": viewing["viewing_fee"],
        "mpesa_receipt": payment.get("mpesa_receipt") if payment else None,
    }
    if viewing["status"] in ("scheduled", "completed"):
        # reveal contact info
        prop = await db["properties"].find_one({"id": viewing["property_id"]}, {"_id": 0})
        unit = await db["units"].find_one({"id": viewing["unit_id"]}, {"_id": 0})
        landlord = await db["users"].find_one(
            {"id": viewing["landlord_id"]}, {"_id": 0, "full_name": 1, "phone": 1}
        )
        # Get any caretaker for this landlord
        caretaker = await db["users"].find_one(
            {"landlord_id": viewing["landlord_id"], "role": "caretaker"},
            {"_id": 0, "full_name": 1, "phone": 1},
        )
        base.update({
            "property_name": prop["name"] if prop else "",
            "property_address": prop["address"] if prop else "",
            "unit_number": unit["unit_number"] if unit else "",
            "landlord_contact": landlord,
            "caretaker_contact": caretaker,
        })
    return base


# ----------- Landlord-side dashboard for incoming viewings -----------

@router.get("/viewings")
async def list_viewings_for_landlord(user: dict = Depends(require_role("landlord"))):
    db = get_db()
    viewings = await db["viewings"].find(
        {"landlord_id": user["id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(500)
    # enrich with unit + property names
    if viewings:
        unit_ids = list({v["unit_id"] for v in viewings})
        prop_ids = list({v["property_id"] for v in viewings})
        units = await db["units"].find({"id": {"$in": unit_ids}}, {"_id": 0}).to_list(500)
        props = await db["properties"].find({"id": {"$in": prop_ids}}, {"_id": 0}).to_list(500)
        u_map = {u["id"]: u for u in units}
        p_map = {p["id"]: p for p in props}
        for v in viewings:
            u = u_map.get(v["unit_id"])
            p = p_map.get(v["property_id"])
            v["unit_number"] = u["unit_number"] if u else ""
            v["property_name"] = p["name"] if p else ""
    return viewings


# ----------- Prospect-side: list their own viewings -----------

@router.get("/my-viewings")
async def list_my_viewings(user: dict = Depends(require_role("prospect"))):
    db = get_db()
    viewings = await db["viewings"].find(
        {"prospect_id": user["id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(500)
    if viewings:
        unit_ids = list({v["unit_id"] for v in viewings})
        prop_ids = list({v["property_id"] for v in viewings})
        units = await db["units"].find({"id": {"$in": unit_ids}}, {"_id": 0}).to_list(500)
        props = await db["properties"].find({"id": {"$in": prop_ids}}, {"_id": 0}).to_list(500)
        u_map = {u["id"]: u for u in units}
        p_map = {p["id"]: p for p in props}
        for v in viewings:
            u = u_map.get(v["unit_id"])
            p = p_map.get(v["property_id"])
            v["unit_number"] = u["unit_number"] if u else ""
            v["property_name"] = p["name"] if p else ""
            v["property_address"] = p["address"] if p else ""
    return viewings
