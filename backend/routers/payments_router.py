"""M-Pesa Payment routes - STK Push and callback."""
import asyncio
import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request

from auth import get_current_user, require_role
from db import get_db
from mpesa import is_demo_mode, normalize_phone, schedule_demo_callback, stk_push
from models import PaymentInitiate, new_id, now_iso

router = APIRouter(tags=["payments"])


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

    update = {
        "result_desc": result_desc,
        "updated_at": now_iso(),
    }
    if result_code == 0:
        update["status"] = "succeeded"
        update["mpesa_receipt"] = mpesa_receipt or f"DEMO{uuid.uuid4().hex[:8].upper()}"
        update["amount"] = confirmed_amount
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
    elif payment.get("bill_id"):
        bill = await db["bills"].find_one({"id": payment["bill_id"]})
        if bill:
            new_paid = bill["amount_paid"] + confirmed_amount
            status = "paid" if new_paid >= bill["amount"] else "partial"
            await db["bills"].update_one(
                {"id": bill["id"]},
                {"$set": {"amount_paid": new_paid, "status": status}},
            )


@router.post("/payments/mpesa/stk-push")
async def initiate_payment(
    payload: PaymentInitiate, user: dict = Depends(require_role("tenant"))
):
    db = get_db()
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
