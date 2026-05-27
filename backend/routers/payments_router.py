"""M-Pesa Payment routes - STK Push and callback."""
import asyncio
import logging
import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request

from auth import get_current_user, require_role
from db import get_db
from mpesa import is_demo_mode, normalize_phone, schedule_demo_callback, stk_push
from models import PaymentInitiate, new_id, now_iso

router = APIRouter(tags=["payments"])
logger = logging.getLogger("payments")


async def _process_callback_payload(payload: dict):
    """Apply M-Pesa callback to payment + bill/viewing records."""
    db = get_db()
    try:
        stk = payload["Body"]["stkCallback"]
    except KeyError:
        await db["orphan_callbacks"].insert_one({"payload": payload, "at": now_iso()})
        return

    checkout_id = stk.get("CheckoutRequestID")
    result_code = stk.get("ResultCode")
    result_desc = stk.get("ResultDesc")

    payment = await db["payments"].find_one({"checkout_request_id": checkout_id})
    if not payment:
        await db["orphan_callbacks"].insert_one({"payload": payload, "at": now_iso()})
        return

    # parse metadata
    mpesa_receipt = None
    confirmed_amount = None
    metadata = stk.get("CallbackMetadata", {})
    for item in metadata.get("Item", []):
        if item.get("Name") == "MpesaReceiptNumber":
            mpesa_receipt = str(item.get("Value"))
        elif item.get("Name") == "Amount":
            confirmed_amount = float(item.get("Value") or 0)

    if confirmed_amount is None or confirmed_amount == 0:
        confirmed_amount = payment["amount"]

    # ---- Commission calc -----
    from routers.admin_router import compute_commission, get_commission_rate
    rate = await get_commission_rate()
    split = compute_commission(confirmed_amount, rate)

    update = {
        "result_desc": result_desc,
        "updated_at": now_iso(),
    }
    if result_code == 0:
        update["status"] = "succeeded"
        update["mpesa_receipt"] = mpesa_receipt or f"DEMO{uuid.uuid4().hex[:8].upper()}"
        update["amount"] = confirmed_amount
        update["commission_rate"] = rate
        update["commission_amount"] = split["commission"]
        update["net_to_landlord"] = split["net"]
    else:
        update["status"] = "failed"

    await db["payments"].update_one({"id": payment["id"]}, {"$set": update})

    if result_code != 0:
        return

    # SUCCESS: route based on purpose
    if payment.get("viewing_id"):
        await db["viewings"].update_one(
            {"id": payment["viewing_id"]},
            {"$set": {"status": "scheduled", "updated_at": now_iso()}},
        )
        # Phase 5: auto-issue a 24h visitor pass to the prospect for the property they booked
        try:
            v = await db["viewings"].find_one({"id": payment["viewing_id"]})
            if v and v.get("prospect_id") and v.get("property_id"):
                import secrets
                from datetime import datetime, timedelta, timezone
                prospect = await db["users"].find_one({"id": v["prospect_id"]})
                if prospect:
                    expires_at = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
                    # Combine viewing date + time into a single ISO datetime for the pass
                    s_date = v.get("scheduled_date") or datetime.now(timezone.utc).date().isoformat()
                    s_time = v.get("scheduled_time") or "10:00"
                    try:
                        expected_dt = datetime.fromisoformat(f"{s_date}T{s_time}:00").replace(tzinfo=timezone.utc).isoformat()
                    except Exception:
                        expected_dt = now_iso()
                    pass_doc = {
                        "id": new_id(),
                        "token": secrets.token_urlsafe(20),
                        "tenant_id": v["prospect_id"],  # reuse the field for prospect
                        "tenant_name": prospect.get("full_name", "Prospect"),
                        "landlord_id": v.get("landlord_id"),
                        "property_id": v["property_id"],
                        "unit_id": v.get("unit_id"),
                        "visitor_name": prospect.get("full_name", "Prospect"),
                        "visitor_phone": prospect.get("phone", ""),
                        "expected_time": expected_dt,
                        "notes": f"Auto-issued for viewing #{v['id'][:8]}. Bring signed-up ID for security.",
                        "status": "active",
                        "used_at": None,
                        "used_by_caretaker_id": None,
                        "used_by_caretaker_name": None,
                        "expires_at": expires_at,
                        "created_at": now_iso(),
                        "is_prospect_pass": True,
                    }
                    await db["visitor_passes"].insert_one(pass_doc)
                    from notifications import notify_user
                    await notify_user(
                        v["prospect_id"], "visitor_arrived",
                        "Your viewing visitor pass is ready",
                        "A 24-hour QR pass has been issued for your property viewing. Show at the gate and carry your signed-up ID.",
                        link="/visitors",
                    )
        except Exception as exc:
            logger.warning("Could not auto-issue prospect visitor pass: %s", exc)
    elif payment.get("yard_sale_id"):
        purpose = payment.get("purpose", "yard_sale_feature")
        from notifications import notify_user
        item = await db["yard_sale"].find_one({"id": payment["yard_sale_id"]})
        if purpose == "yard_sale_contact":
            await db["yard_sale"].update_one(
                {"id": payment["yard_sale_id"]},
                {"$set": {"contact_unlocked": True, "updated_at": now_iso()}},
            )
            if item and payment.get("tenant_id"):
                await notify_user(
                    payment["tenant_id"], "yard_sale_featured",
                    f"Contact unlocked for \"{item['title']}\"",
                    "Buyers can now see your phone & email on the listing. They can call, message or post directly.",
                    link=f"/yard-sale/{payment['yard_sale_id']}",
                )
        elif purpose == "yard_sale_broadcast":
            await db["yard_sale"].update_one(
                {"id": payment["yard_sale_id"]},
                {"$set": {"scope": "all", "updated_at": now_iso()}},
            )
            if item and payment.get("tenant_id"):
                await notify_user(
                    payment["tenant_id"], "yard_sale_featured",
                    f"\"{item['title']}\" is now broadcast platform-wide",
                    "Your listing is visible to every tenant on NyumbaOS. Featured boosts can be added separately.",
                    link=f"/yard-sale/{payment['yard_sale_id']}",
                )
        else:  # yard_sale_feature (default)
            from datetime import datetime, timedelta, timezone
            from models import YARD_SALE_FEATURE_DAYS
            feat_until = (datetime.now(timezone.utc) + timedelta(days=YARD_SALE_FEATURE_DAYS)).isoformat()
            await db["yard_sale"].update_one(
                {"id": payment["yard_sale_id"]},
                {"$set": {
                    "featured": True,
                    "featured_until": feat_until,
                    "updated_at": now_iso(),
                }},
            )
            if item and payment.get("tenant_id"):
                await notify_user(
                    payment["tenant_id"], "yard_sale_featured",
                    f"\"{item['title']}\" is now featured",
                    f"Your listing will appear at the top of the marketplace until {feat_until[:10]}.",
                    link=f"/yard-sale/{payment['yard_sale_id']}",
                )
    elif payment.get("bill_id"):
        bill = await db["bills"].find_one({"id": payment["bill_id"]})
        if bill:
            new_paid = bill["amount_paid"] + confirmed_amount
            status = "paid" if new_paid >= bill["amount"] else "partial"
            await db["bills"].update_one(
                {"id": bill["id"]},
                {"$set": {"amount_paid": new_paid, "status": status}},
            )
            bill_type_label = (bill.get("bill_type") or "rent").replace("_", " ").title()
            receipt = update.get("mpesa_receipt", "") or ""
            from notifications import notify_user
            if payment.get("tenant_id"):
                await notify_user(
                    payment["tenant_id"], "payment_succeeded",
                    f"{bill_type_label} bill paid · KES {confirmed_amount:,.0f}",
                    f"M-Pesa receipt {receipt}. Bill is now {status}.",
                    link="/payments",
                )
            if payment.get("landlord_id"):
                await notify_user(
                    payment["landlord_id"], "payment_succeeded",
                    f"{bill_type_label} payment received · KES {confirmed_amount:,.0f}",
                    f"From tenant (receipt {receipt}). Bill is now {status}.",
                    link="/payments",
                )


@router.post("/payments/mpesa/stk-push")
async def initiate_payment(
    payload: PaymentInitiate, user: dict = Depends(require_role("tenant"))
):
    db = get_db()
    if user.get("approval_status") == "pending":
        raise HTTPException(
            403,
            "Your account is pending admin verification. You cannot make payments yet — please contact your landlord or platform admin.",
        )
    if user.get("approval_status") == "rejected":
        raise HTTPException(
            403,
            "Your account has been rejected by platform admin. Please contact support.",
        )
    bill = await db["bills"].find_one({"id": payload.bill_id, "tenant_id": user["id"]})
    if not bill:
        raise HTTPException(404, "Bill not found")
    if bill["status"] == "paid":
        raise HTTPException(400, "Bill is already paid")

    amount = payload.amount or (bill["amount"] - bill["amount_paid"])
    if amount <= 0:
        raise HTTPException(400, "Invalid amount")

    phone = normalize_phone(payload.phone_number)
    if not (phone.startswith("254") and len(phone) == 12 and phone.isdigit()):
        raise HTTPException(400, "Phone must be in format 2547XXXXXXXX")

    payment_id = new_id()
    idempotency_key = f"{payload.bill_id}-{payment_id}"

    payment_doc = {
        "id": payment_id,
        "bill_id": bill["id"],
        "tenant_id": user["id"],
        "landlord_id": bill["landlord_id"],
        "amount": amount,
        "phone_number": phone,
        "status": "pending",
        "checkout_request_id": None,
        "merchant_request_id": None,
        "mpesa_receipt": None,
        "result_desc": None,
        "idempotency_key": idempotency_key,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db["payments"].insert_one(payment_doc)

    # construct callback URL (best effort)
    callback_base = os.environ.get("MPESA_CALLBACK_BASE_URL", "")
    callback_secret = os.environ.get("MPESA_CALLBACK_SECRET", "secret")
    callback_url = f"{callback_base}/api/payments/mpesa/callback/{callback_secret}"

    resp: dict = {}
    try:
        resp = await stk_push(
            phone=phone,
            amount=amount,
            account_ref=f"BILL-{bill['id'][:8]}",
            description=f"{bill['bill_type'].title()} {bill['period']}",
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

    # demo mode: schedule auto-callback
    if resp.get("_demo") or is_demo_mode():
        asyncio.create_task(
            schedule_demo_callback(resp["CheckoutRequestID"], _process_callback_payload)
        )

    return {
        "payment_id": payment_id,
        "checkout_request_id": resp.get("CheckoutRequestID"),
        "status": "pending",
        "demo_mode": is_demo_mode(),
        "message": resp.get("CustomerMessage", "STK push sent. Check your phone."),
    }


@router.post("/payments/mpesa/callback/{secret}")
async def mpesa_callback(secret: str, request: Request):
    expected = os.environ.get("MPESA_CALLBACK_SECRET", "secret")
    if secret != expected:
        raise HTTPException(404, "Not found")
    payload = await request.json()
    await _process_callback_payload(payload)
    return {"ResultCode": 0, "ResultDesc": "Accepted"}


@router.get("/payments")
async def list_payments(user: dict = Depends(get_current_user)):
    db = get_db()
    if user["role"] == "landlord":
        query = {"landlord_id": user["id"]}
    elif user["role"] == "tenant":
        query = {"tenant_id": user["id"]}
    else:
        return []
    payments = await db["payments"].find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return payments


@router.get("/payments/{payment_id}")
async def get_payment(payment_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    p = await db["payments"].find_one({"id": payment_id}, {"_id": 0})
    if not p:
        raise HTTPException(404, "Payment not found")
    if user["role"] == "tenant" and p["tenant_id"] != user["id"]:
        raise HTTPException(403, "Forbidden")
    if user["role"] == "landlord" and p["landlord_id"] != user["id"]:
        raise HTTPException(403, "Forbidden")
    return p
