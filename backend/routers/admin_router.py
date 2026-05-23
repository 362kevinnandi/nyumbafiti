"""Super-admin endpoints: platform-wide visibility, payouts, commission settings."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import require_role
from db import get_db
from models import DEFAULT_COMMISSION_RATE, now_iso

router = APIRouter(prefix="/admin", tags=["admin"])


# ============ helpers ============

async def get_commission_rate() -> float:
    db = get_db()
    settings = await db["platform_settings"].find_one({"id": "default"}, {"_id": 0})
    if not settings:
        return DEFAULT_COMMISSION_RATE
    return float(settings.get("commission_rate", DEFAULT_COMMISSION_RATE))


def compute_commission(amount: float, rate: float) -> dict:
    """Return {gross, commission, net} for a given amount + rate."""
    gross = round(float(amount), 2)
    commission = round(gross * rate, 2)
    net = round(gross - commission, 2)
    return {"gross": gross, "commission": commission, "net": net, "rate": rate}


# ============ Settings ============

class SettingsUpdate(BaseModel):
    commission_rate: float


@router.get("/settings")
async def get_settings(_: dict = Depends(require_role("admin"))):
    db = get_db()
    settings = await db["platform_settings"].find_one({"id": "default"}, {"_id": 0})
    if not settings:
        settings = {
            "id": "default",
            "commission_rate": DEFAULT_COMMISSION_RATE,
            "updated_at": now_iso(),
        }
        await db["platform_settings"].insert_one(settings)
        settings.pop("_id", None)
    return settings


@router.patch("/settings")
async def update_settings(
    payload: SettingsUpdate, _: dict = Depends(require_role("admin"))
):
    db = get_db()
    if not (0 <= payload.commission_rate <= 0.5):
        raise HTTPException(400, "Commission rate must be between 0 and 0.5 (50%)")
    await db["platform_settings"].update_one(
        {"id": "default"},
        {
            "$set": {
                "commission_rate": payload.commission_rate,
                "updated_at": now_iso(),
            }
        },
        upsert=True,
    )
    return await get_settings(_)


# ============ Platform stats ============

@router.get("/stats")
async def platform_stats(_: dict = Depends(require_role("admin"))):
    db = get_db()
    users_by_role = {}
    for role in ["landlord", "tenant", "caretaker", "prospect", "admin"]:
        users_by_role[role] = await db["users"].count_documents({"role": role})

    properties = await db["properties"].count_documents({})
    units = await db["units"].count_documents({})
    occupied = await db["units"].count_documents({"occupied": True})

    # Gross volume processed (successful payments)
    pipeline = [
        {"$match": {"status": "succeeded"}},
        {
            "$group": {
                "_id": None,
                "gross": {"$sum": "$amount"},
                "commission": {"$sum": "$commission_amount"},
                "net": {"$sum": "$net_to_landlord"},
                "count": {"$sum": 1},
            }
        },
    ]
    agg = await db["payments"].aggregate(pipeline).to_list(1)
    totals = agg[0] if agg else {"gross": 0, "commission": 0, "net": 0, "count": 0}

    # By purpose (rent bills vs viewing fees)
    purpose_pipe = [
        {"$match": {"status": "succeeded"}},
        {
            "$group": {
                "_id": "$purpose",
                "gross": {"$sum": "$amount"},
                "commission": {"$sum": "$commission_amount"},
                "count": {"$sum": 1},
            }
        },
    ]
    by_purpose = await db["payments"].aggregate(purpose_pipe).to_list(10)

    open_issues = await db["issues"].count_documents(
        {"status": {"$in": ["open", "in_progress"]}}
    )
    pending_viewings = await db["viewings"].count_documents({"status": "pending_payment"})

    # Pending approvals across resources
    pending_properties = await db["properties"].count_documents({"approval_status": "pending"})
    pending_tenants = await db["users"].count_documents(
        {"role": "tenant", "approval_status": "pending"}
    )
    pending_caretakers = await db["users"].count_documents(
        {"role": "caretaker", "approval_status": "pending"}
    )

    # Total arrears across the platform
    arrears_pipe = [
        {"$match": {"status": {"$in": ["pending", "partial", "overdue"]}}},
        {"$group": {"_id": None, "total": {"$sum": {"$subtract": ["$amount", "$amount_paid"]}}}},
    ]
    arrears_agg = await db["bills"].aggregate(arrears_pipe).to_list(1)
    total_arrears = arrears_agg[0]["total"] if arrears_agg else 0

    return {
        "users_by_role": users_by_role,
        "total_users": sum(users_by_role.values()),
        "properties": properties,
        "units": units,
        "occupied_units": occupied,
        "vacant_units": units - occupied,
        "total_gross_processed": totals.get("gross", 0),
        "total_commission_earned": totals.get("commission", 0),
        "total_net_to_landlords": totals.get("net", 0),
        "successful_payments_count": totals.get("count", 0),
        "open_issues": open_issues,
        "pending_viewings": pending_viewings,
        "pending_property_approvals": pending_properties,
        "pending_tenant_approvals": pending_tenants,
        "pending_caretaker_approvals": pending_caretakers,
        "pending_approvals_total": pending_properties + pending_tenants + pending_caretakers,
        "total_arrears": total_arrears,
        "by_purpose": by_purpose,
        "current_commission_rate": await get_commission_rate(),
    }


# ============ Users ============

@router.get("/users")
async def list_users(
    role: str | None = None, _: dict = Depends(require_role("admin"))
):
    db = get_db()
    query: dict = {}
    if role:
        query["role"] = role
    users = await db["users"].find(
        query, {"_id": 0, "password_hash": 0}
    ).sort("created_at", -1).to_list(1000)
    return users


class UserSuspendUpdate(BaseModel):
    suspended: bool


@router.patch("/users/{user_id}/suspend")
async def suspend_user(
    user_id: str,
    payload: UserSuspendUpdate,
    admin: dict = Depends(require_role("admin")),
):
    db = get_db()
    if user_id == admin["id"]:
        raise HTTPException(400, "Cannot suspend your own admin account")
    user = await db["users"].find_one({"id": user_id})
    if not user:
        raise HTTPException(404, "User not found")
    await db["users"].update_one(
        {"id": user_id},
        {"$set": {"suspended": payload.suspended, "updated_at": now_iso()}},
    )
    return {"ok": True, "suspended": payload.suspended}


# ============ Payments view ============

@router.get("/payments")
async def list_all_payments(
    status: str | None = None,
    purpose: str | None = None,
    _: dict = Depends(require_role("admin")),
):
    db = get_db()
    query: dict = {}
    if status:
        query["status"] = status
    if purpose:
        query["purpose"] = purpose
    payments = await db["payments"].find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)

    # enrich with landlord & tenant names
    landlord_ids = list({p.get("landlord_id") for p in payments if p.get("landlord_id")})
    if landlord_ids:
        landlords = await db["users"].find(
            {"id": {"$in": landlord_ids}}, {"_id": 0, "id": 1, "full_name": 1}
        ).to_list(500)
        l_map = {ld["id"]: ld["full_name"] for ld in landlords}
        for p in payments:
            p["landlord_name"] = l_map.get(p.get("landlord_id"), "")
    return payments


class RefundRequest(BaseModel):
    reason: str = ""


@router.post("/payments/{payment_id}/refund")
async def mark_payment_refunded(
    payment_id: str,
    payload: RefundRequest,
    _: dict = Depends(require_role("admin")),
):
    db = get_db()
    payment = await db["payments"].find_one({"id": payment_id})
    if not payment:
        raise HTTPException(404, "Payment not found")
    if payment["status"] != "succeeded":
        raise HTTPException(400, "Only succeeded payments can be refunded")

    await db["payments"].update_one(
        {"id": payment_id},
        {
            "$set": {
                "status": "refunded",
                "refund_reason": payload.reason,
                "refunded_at": now_iso(),
                "updated_at": now_iso(),
            }
        },
    )

    # roll back bill or viewing
    if payment.get("bill_id"):
        bill = await db["bills"].find_one({"id": payment["bill_id"]})
        if bill:
            new_paid = max(0.0, bill["amount_paid"] - payment["amount"])
            new_status = "paid" if new_paid >= bill["amount"] else ("partial" if new_paid > 0 else "pending")
            await db["bills"].update_one(
                {"id": bill["id"]},
                {"$set": {"amount_paid": new_paid, "status": new_status}},
            )
    elif payment.get("viewing_id"):
        await db["viewings"].update_one(
            {"id": payment["viewing_id"]},
            {"$set": {"status": "cancelled", "updated_at": now_iso()}},
        )

    return {"ok": True}


# ============ Payouts ============

@router.get("/payouts")
async def landlord_payouts(_: dict = Depends(require_role("admin"))):
    """Compute per-landlord payout balances (net unpaid)."""
    db = get_db()
    pipeline = [
        {"$match": {"status": "succeeded"}},
        {
            "$group": {
                "_id": "$landlord_id",
                "gross_earned": {"$sum": "$amount"},
                "commission_taken": {"$sum": "$commission_amount"},
                "net_owed": {"$sum": "$net_to_landlord"},
                "transactions": {"$sum": 1},
            }
        },
    ]
    rows = await db["payments"].aggregate(pipeline).to_list(500)
    # exclude None landlord rows (shouldn't happen but defensive)
    rows = [r for r in rows if r.get("_id")]

    # subtract previously paid out
    paid_pipeline = [
        {"$group": {"_id": "$landlord_id", "paid_out": {"$sum": "$amount"}}}
    ]
    paid_rows = await db["payouts"].aggregate(paid_pipeline).to_list(500)
    paid_map = {r["_id"]: r["paid_out"] for r in paid_rows}

    landlord_ids = [r["_id"] for r in rows]
    landlords = await db["users"].find(
        {"id": {"$in": landlord_ids}}, {"_id": 0, "id": 1, "full_name": 1, "phone": 1, "email": 1}
    ).to_list(500)
    l_map = {ld["id"]: ld for ld in landlords}

    result = []
    for r in rows:
        landlord = l_map.get(r["_id"], {})
        already_paid = paid_map.get(r["_id"], 0)
        balance_owed = round(r["net_owed"] - already_paid, 2)
        result.append({
            "landlord_id": r["_id"],
            "landlord_name": landlord.get("full_name", ""),
            "landlord_phone": landlord.get("phone", ""),
            "landlord_email": landlord.get("email", ""),
            "gross_earned": round(r["gross_earned"], 2),
            "commission_taken": round(r["commission_taken"], 2),
            "net_owed_total": round(r["net_owed"], 2),
            "already_paid_out": round(already_paid, 2),
            "balance_owed": balance_owed,
            "transactions": r["transactions"],
        })
    # sort by balance desc
    result.sort(key=lambda x: -x["balance_owed"])
    return result


class PayoutMarkPaid(BaseModel):
    amount: float
    note: str = ""


@router.post("/payouts/{landlord_id}/mark-paid")
async def mark_payout_paid(
    landlord_id: str,
    payload: PayoutMarkPaid,
    admin: dict = Depends(require_role("admin")),
):
    db = get_db()
    landlord = await db["users"].find_one(
        {"id": landlord_id, "role": "landlord"}, {"_id": 0, "id": 1}
    )
    if not landlord:
        raise HTTPException(404, "Landlord not found")
    if payload.amount <= 0:
        raise HTTPException(400, "Amount must be positive")

    import uuid
    payout = {
        "id": str(uuid.uuid4()),
        "landlord_id": landlord_id,
        "amount": float(payload.amount),
        "note": payload.note,
        "status": "paid",
        "recorded_by": admin["id"],
        "created_at": now_iso(),
    }
    await db["payouts"].insert_one(payout)
    payout.pop("_id", None)
    return payout


@router.get("/payouts/history")
async def payout_history(_: dict = Depends(require_role("admin"))):
    db = get_db()
    rows = await db["payouts"].find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    if rows:
        landlord_ids = list({r["landlord_id"] for r in rows})
        landlords = await db["users"].find(
            {"id": {"$in": landlord_ids}}, {"_id": 0, "id": 1, "full_name": 1}
        ).to_list(500)
        l_map = {ld["id"]: ld["full_name"] for ld in landlords}
        for r in rows:
            r["landlord_name"] = l_map.get(r["landlord_id"], "")
    return rows


# ============ Properties view ============

@router.get("/properties")
async def list_all_properties(_: dict = Depends(require_role("admin"))):
    db = get_db()
    props = await db["properties"].find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    if props:
        landlord_ids = list({p["landlord_id"] for p in props})
        landlords = await db["users"].find(
            {"id": {"$in": landlord_ids}}, {"_id": 0, "id": 1, "full_name": 1}
        ).to_list(500)
        l_map = {ld["id"]: ld["full_name"] for ld in landlords}
        for p in props:
            p["landlord_name"] = l_map.get(p["landlord_id"], "")
            p["units_count"] = await db["units"].count_documents({"property_id": p["id"]})
    return props
