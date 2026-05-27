"""M-Pesa Payment routes - STK Push and callback."""
import asyncio
import logging
import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from auth import get_current_user, require_role
from db import get_db
from mpesa import is_demo_mode, normalize_phone, schedule_demo_callback, schedule_status_poll, should_use_demo_fallback, stk_push
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
    # Idempotency: if already settled, ignore subsequent callbacks (handles demo fallback racing real Safaricom)
    if payment.get("status") in ("succeeded", "failed", "refunded"):
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
        # Notify tenant so they know to retry — was a silent failure before
        if payment.get("tenant_id"):
            try:
                from notifications import notify_user
                reason = result_desc or "Payment was not completed"
                await notify_user(
                    payment["tenant_id"],
                    "payment_succeeded",  # reused channel
                    f"Payment did not go through — {reason}",
                    "Your M-Pesa payment was not completed (you may have cancelled, timed out, or had insufficient balance). Open the bill and try again.",
                    link="/bills" if payment.get("bill_id") else "/marketplace",
                )
            except Exception:
                pass
        return

    # SUCCESS: route based on purpose
    if payment.get("viewing_id"):
        await db["viewings"].update_one(
            {"id": payment["viewing_id"]},
            {"$set": {"status": "scheduled", "updated_at": now_iso()}},
        )
        # Record a virtual ledger entry: caretaker is owed KES 150, platform keeps KES 50
        try:
            v = await db["viewings"].find_one({"id": payment["viewing_id"]})
            settings = await db["platform_settings"].find_one({"id": "default"}, {"_id": 0}) or {}
            ck_share = float(settings.get("viewing_caretaker_share", 150.0))
            pl_share = float(settings.get("viewing_platform_share", 50.0))
            await db["disbursement_ledger"].insert_one({
                "id": new_id(),
                "payment_id": payment["id"],
                "viewing_id": payment["viewing_id"],
                "landlord_id": v.get("landlord_id") if v else None,
                "property_id": v.get("property_id") if v else None,
                "gross_amount": float(payment["amount"]),
                "platform_share": pl_share,
                "caretaker_share": ck_share,
                "status": "pending",  # admin marks 'paid' after disbursing via M-Pesa portal
                "kind": "viewing_caretaker",
                "created_at": now_iso(),
            })
        except Exception as exc:
            logger.warning("Could not record disbursement ledger entry for viewing: %s", exc)
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
                # Also flip status from pending_payment → active in case this was the mandatory unlock at posting time
                {"$set": {"contact_unlocked": True, "status": "active", "updated_at": now_iso()}},
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
            from notifications import notify_user
            purpose = payment.get("purpose")
            if purpose == "bill_service_fee":
                # Fee STK confirmed — bill stays pending; tenant still needs to submit rent receipt
                await db["bills"].update_one(
                    {"id": bill["id"]},
                    {"$set": {
                        "service_fee_paid_at": now_iso(),
                        "service_fee_amount": float(payment["amount"]),
                        "service_fee_payment_id": payment["id"],
                        "status": "awaiting_rent_receipt",
                    }},
                )
                if payment.get("tenant_id"):
                    await notify_user(
                        payment["tenant_id"], "payment_succeeded",
                        f"Service fee paid · KES {confirmed_amount:,.0f}",
                        "Now pay the rent to your landlord's M-Pesa paybill, then enter the receipt code in the app.",
                        link="/bills",
                    )
            else:
                # Legacy direct-pay flow (kept for safety)
                new_paid = bill.get("amount_paid", 0) + confirmed_amount
                status = "paid" if new_paid >= bill["amount"] else "partial"
                await db["bills"].update_one(
                    {"id": bill["id"]},
                    {"$set": {"amount_paid": new_paid, "status": status}},
                )
                receipt = update.get("mpesa_receipt", "") or ""
                if payment.get("tenant_id"):
                    await notify_user(
                        payment["tenant_id"], "payment_succeeded",
                        f"Payment received · KES {confirmed_amount:,.0f}",
                        f"M-Pesa receipt {receipt}. Bill is now {status}.",
                        link="/payments",
                    )
                if payment.get("landlord_id"):
                    await notify_user(
                        payment["landlord_id"], "payment_succeeded",
                        f"Payment received · KES {confirmed_amount:,.0f}",
                        f"From tenant (receipt {receipt}). Bill is now {status}.",
                        link="/payments",
                    )


def _round_up_to_10(x: float) -> int:
    """Round up to the nearest 10 KES so service-fee amounts look clean (250, 310, 530 ...)."""
    import math
    return int(math.ceil(x / 10.0) * 10)


async def _get_settings_value(db, key: str, fallback):
    s = await db["platform_settings"].find_one({"id": "default"}, {"_id": 0}) or {}
    return s.get(key, fallback)


@router.post("/payments/mpesa/stk-push")
async def initiate_payment(
    payload: PaymentInitiate, user: dict = Depends(require_role("tenant"))
):
    """Tenant initiates payment for a bill.

    Flow (Option 1b):
    1. Tenant manually pays the *rent amount* via M-Pesa to the landlord's paybill (shown in the UI).
    2. This endpoint STK-pushes ONLY the 2.5% service fee (rounded up to KES 10) to the PLATFORM paybill.
    3. The bill remains pending until tenant submits the rent receipt (POST /bills/{id}/submit-rent-receipt)
       AND the landlord/caretaker confirms it (POST /bills/{id}/confirm-rent-receipt).
    """
    db = get_db()
    if user.get("approval_status") == "pending":
        raise HTTPException(
            403,
            "Your account is pending admin verification. You cannot make payments yet — please contact your landlord or platform admin.",
        )
    if user.get("approval_status") == "rejected":
        raise HTTPException(403, "Your account has been rejected by platform admin. Please contact support.")
    bill = await db["bills"].find_one({"id": payload.bill_id, "tenant_id": user["id"]})
    if not bill:
        raise HTTPException(404, "Bill not found")
    if bill["status"] == "paid":
        raise HTTPException(400, "Bill is already paid")
    if bill.get("service_fee_paid_at"):
        raise HTTPException(400, "Service fee already paid for this bill — submit your rent receipt next")

    # Compute service fee
    service_fee_pct = float(await _get_settings_value(db, "service_fee_pct", 0.025))
    rent_amount = float(bill["amount"]) - float(bill.get("amount_paid", 0) or 0)
    service_fee = _round_up_to_10(rent_amount * service_fee_pct)
    if service_fee <= 0:
        raise HTTPException(400, "Computed service fee is zero")

    phone = normalize_phone(payload.phone_number)
    if not (phone.startswith("254") and len(phone) == 12 and phone.isdigit()):
        raise HTTPException(400, "Phone must be in format 2547XXXXXXXX")

    payment_id = new_id()
    payment_doc = {
        "id": payment_id,
        "bill_id": bill["id"],
        "tenant_id": user["id"],
        "landlord_id": bill["landlord_id"],
        "amount": float(service_fee),
        "phone_number": phone,
        "status": "pending",
        "purpose": "bill_service_fee",
        "rent_amount": rent_amount,           # store the underlying rent so admin can reconcile
        "service_fee_pct": service_fee_pct,
        "checkout_request_id": None,
        "merchant_request_id": None,
        "mpesa_receipt": None,
        "result_desc": None,
        "idempotency_key": f"{payload.bill_id}-fee-{payment_id}",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db["payments"].insert_one(payment_doc)

    callback_base = os.environ.get("MPESA_CALLBACK_BASE_URL", "")
    callback_secret = os.environ.get("MPESA_CALLBACK_SECRET", "secret")
    callback_url = f"{callback_base}/api/payments/mpesa/callback/{callback_secret}"

    resp: dict = {}
    try:
        resp = await stk_push(
            phone=phone,
            amount=float(service_fee),
            account_ref=f"FEE-{bill['id'][:8]}",
            description=f"Fee {bill['bill_type'][:6]} {bill['period']}",
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

    if should_use_demo_fallback(resp):
        asyncio.create_task(schedule_demo_callback(resp["CheckoutRequestID"], _process_callback_payload))
    elif resp.get("CheckoutRequestID"):
        asyncio.create_task(schedule_status_poll(resp["CheckoutRequestID"], _process_callback_payload))

    # Pull landlord paybill info for the UI
    prop = await db["properties"].find_one({"id": bill["property_id"]}, {"_id": 0}) or {}
    return {
        "payment_id": payment_id,
        "checkout_request_id": resp.get("CheckoutRequestID"),
        "status": "pending",
        "demo_mode": is_demo_mode(),
        "service_fee_amount": float(service_fee),
        "rent_amount": rent_amount,
        "total_cost_to_tenant": rent_amount + float(service_fee),
        "landlord_paybill": prop.get("landlord_paybill") or "",
        "landlord_account_number": prop.get("landlord_account_number") or "",
        "platform_paybill": await _get_settings_value(db, "platform_paybill", "247247"),
        "platform_account": await _get_settings_value(db, "platform_account", "0740479864"),
        "message": resp.get("CustomerMessage", "STK push sent — enter PIN to pay the 2.5% service fee."),
    }


# ============ Manual rent receipt flow ============

class RentReceiptSubmit(BaseModel):
    mpesa_receipt: str  # M-Pesa SMS receipt code, e.g. "SGH7XYZ123"
    amount_paid: float


@router.post("/bills/{bill_id}/submit-rent-receipt")
async def submit_rent_receipt(
    bill_id: str,
    payload: RentReceiptSubmit,
    user: dict = Depends(require_role("tenant")),
):
    """Tenant submits the M-Pesa receipt code after paying the landlord directly."""
    db = get_db()
    bill = await db["bills"].find_one({"id": bill_id, "tenant_id": user["id"]})
    if not bill:
        raise HTTPException(404, "Bill not found")
    if bill["status"] == "paid":
        raise HTTPException(400, "Bill is already paid")
    if not bill.get("service_fee_paid_at"):
        raise HTTPException(400, "Pay the 2.5% service fee first — landlords trust receipts that come with the fee")
    if not payload.mpesa_receipt.strip():
        raise HTTPException(400, "M-Pesa receipt code is required")
    await db["bills"].update_one(
        {"id": bill_id},
        {"$set": {
            "rent_receipt_code": payload.mpesa_receipt.strip().upper(),
            "rent_receipt_amount": float(payload.amount_paid),
            "rent_receipt_submitted_at": now_iso(),
            "status": "awaiting_landlord_confirmation",
        }},
    )
    # Notify landlord + caretaker so they can confirm
    from notifications import notify_user
    await notify_user(
        bill["landlord_id"], "payment_succeeded",
        f"Rent receipt submitted — KES {payload.amount_paid:,.0f}",
        f"Tenant {user['full_name']} submitted M-Pesa receipt {payload.mpesa_receipt}. Please confirm on the Bills page.",
        link="/bills",
    )
    return {"ok": True, "status": "awaiting_landlord_confirmation"}


@router.post("/bills/{bill_id}/confirm-rent-receipt")
async def confirm_rent_receipt(
    bill_id: str,
    user: dict = Depends(require_role("landlord", "caretaker", "admin")),
):
    """Landlord (or their caretaker) confirms the rent receipt → bill flips to paid."""
    db = get_db()
    bill = await db["bills"].find_one({"id": bill_id})
    if not bill:
        raise HTTPException(404, "Bill not found")
    # Auth check
    if user["role"] == "landlord" and bill["landlord_id"] != user["id"]:
        raise HTTPException(403, "Not your bill")
    if user["role"] == "caretaker" and bill["landlord_id"] != user.get("landlord_id"):
        raise HTTPException(403, "Not your landlord's bill")
    if not bill.get("rent_receipt_submitted_at"):
        raise HTTPException(400, "Tenant hasn't submitted the rent receipt yet")
    if bill["status"] == "paid":
        return {"ok": True, "status": "paid"}
    new_paid = float(bill.get("amount_paid", 0)) + float(bill.get("rent_receipt_amount", 0))
    status = "paid" if new_paid >= float(bill["amount"]) else "partial"
    await db["bills"].update_one(
        {"id": bill_id},
        {"$set": {
            "amount_paid": new_paid,
            "status": status,
            "rent_confirmed_at": now_iso(),
            "rent_confirmed_by": user["id"],
            "rent_confirmed_by_role": user["role"],
        }},
    )
    from notifications import notify_user
    await notify_user(
        bill["tenant_id"], "payment_succeeded",
        f"Rent payment confirmed by {user['role']}",
        f"M-Pesa receipt {bill.get('rent_receipt_code')} was confirmed. Bill #{bill_id[:8]} is now {status}.",
        link="/bills",
    )
    return {"ok": True, "status": status}


@router.post("/bills/{bill_id}/reject-rent-receipt")
async def reject_rent_receipt(
    bill_id: str,
    payload: dict,
    user: dict = Depends(require_role("landlord", "caretaker", "admin")),
):
    """Landlord rejects a fishy receipt → status reverts to service_fee_paid so tenant can re-submit."""
    db = get_db()
    bill = await db["bills"].find_one({"id": bill_id})
    if not bill:
        raise HTTPException(404, "Bill not found")
    if user["role"] == "landlord" and bill["landlord_id"] != user["id"]:
        raise HTTPException(403, "Not your bill")
    if user["role"] == "caretaker" and bill["landlord_id"] != user.get("landlord_id"):
        raise HTTPException(403, "Not your landlord's bill")
    reason = (payload or {}).get("reason", "")
    await db["bills"].update_one(
        {"id": bill_id},
        {"$set": {
            "status": "pending",
            "rent_receipt_code": None,
            "rent_receipt_amount": None,
            "rent_receipt_submitted_at": None,
            "rent_receipt_rejection": reason,
            "rent_receipt_rejected_at": now_iso(),
        }},
    )
    from notifications import notify_user
    await notify_user(
        bill["tenant_id"], "payment_succeeded",
        "Rent receipt rejected — please re-submit",
        f"Landlord rejected receipt for bill #{bill_id[:8]}. Reason: {reason or 'no reason provided'}",
        link="/bills",
    )
    return {"ok": True, "status": "pending"}


@router.post("/payments/mpesa/callback/{secret}")
async def mpesa_callback(secret: str, request: Request):
    expected = os.environ.get("MPESA_CALLBACK_SECRET", "secret")
    if secret != expected:
        raise HTTPException(404, "Not found")
    payload = await request.json()
    await _process_callback_payload(payload)
    return {"ResultCode": 0, "ResultDesc": "Accepted"}


@router.post("/payments/{payment_id}/check")
async def force_status_check(payment_id: str, user: dict = Depends(get_current_user)):
    """Manually trigger a Safaricom STK query for this payment + settle accordingly.

    Useful when the automatic poller hasn't yet detected the user's action (paid / cancelled),
    or when the tenant wants to refresh the status immediately.
    """
    db = get_db()
    p = await db["payments"].find_one({"id": payment_id})
    if not p:
        raise HTTPException(404, "Payment not found")
    # Auth: tenant who initiated, landlord on the bill, or admin
    if user["role"] != "admin" and p.get("tenant_id") != user["id"] and p.get("landlord_id") != user["id"]:
        raise HTTPException(403, "Forbidden")
    if p["status"] in ("succeeded", "failed", "refunded"):
        return p
    if not p.get("checkout_request_id"):
        raise HTTPException(400, "No checkout_request_id on this payment")
    if is_demo_mode():
        # In pure demo mode we cannot query Safaricom
        return p
    from mpesa import _synth_callback, query_stk_status
    try:
        data = await query_stk_status(p["checkout_request_id"])
    except Exception as exc:
        raise HTTPException(502, f"Safaricom query failed: {exc}")
    code = str(data.get("ResultCode", ""))
    desc = data.get("ResultDesc", "") or data.get("errorMessage", "")
    if code == "0":
        await _process_callback_payload(_synth_callback(p["checkout_request_id"], 0, desc or "Success"))
    elif code in ("1", "1032", "1037", "1019", "1025", "1031", "2001"):
        await _process_callback_payload(_synth_callback(p["checkout_request_id"], int(code), desc))
    # else still pending — leave as-is
    return await db["payments"].find_one({"id": payment_id}, {"_id": 0})


@router.post("/payments/{payment_id}/cancel")
async def cancel_payment(payment_id: str, user: dict = Depends(get_current_user)):
    """Tenant aborts a stuck-pending STK push so they can retry."""
    db = get_db()
    p = await db["payments"].find_one({"id": payment_id})
    if not p:
        raise HTTPException(404, "Payment not found")
    if user["role"] != "admin" and p.get("tenant_id") != user["id"]:
        raise HTTPException(403, "Forbidden")
    if p["status"] != "pending":
        raise HTTPException(400, "Payment is no longer pending")
    await db["payments"].update_one(
        {"id": payment_id},
        {"$set": {"status": "failed", "result_desc": "Cancelled by user", "updated_at": now_iso()}},
    )
    return {"ok": True, "status": "failed"}


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
