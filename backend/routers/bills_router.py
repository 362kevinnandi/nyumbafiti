"""Bill management & monthly auto-generation."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_user, require_role
from db import get_db
from models import Bill, BillCreate, new_id, now_iso
from notifications import notify_user

router = APIRouter(tags=["bills"])


def _current_period() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _compute_status(bill: dict) -> str:
    if bill["amount_paid"] >= bill["amount"]:
        return "paid"
    if bill["amount_paid"] > 0:
        return "partial"
    # check if overdue
    try:
        due = datetime.fromisoformat(bill["due_date"].replace("Z", "+00:00"))
        if due < datetime.now(timezone.utc):
            return "overdue"
    except Exception:
        pass
    return "pending"


@router.get("/bills")
async def list_bills(user: dict = Depends(get_current_user)):
    db = get_db()
    if user["role"] == "landlord":
        query = {"landlord_id": user["id"]}
    elif user["role"] == "tenant":
        query = {"tenant_id": user["id"]}
    else:
        return []  # caretakers don't see bills
    bills = await db["bills"].find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    # update overdue status on read
    for b in bills:
        new_status = _compute_status(b)
        if new_status != b["status"]:
            await db["bills"].update_one({"id": b["id"]}, {"$set": {"status": new_status}})
            b["status"] = new_status
    # Attach landlord paybill info from the property — tenants need it to pay rent manually
    if bills:
        prop_ids = list({b["property_id"] for b in bills})
        props = await db["properties"].find(
            {"id": {"$in": prop_ids}}, {"_id": 0, "id": 1, "landlord_paybill": 1, "landlord_account_number": 1, "name": 1}
        ).to_list(1000)
        p_map = {p["id"]: p for p in props}
        for b in bills:
            p = p_map.get(b["property_id"], {})
            b["landlord_paybill"] = p.get("landlord_paybill", "")
            b["landlord_account_number"] = p.get("landlord_account_number", "")
            b["property_name"] = p.get("name", "")
    # attach unit / tenant info for landlord view
    if user["role"] == "landlord" and bills:
        unit_ids = list({b["unit_id"] for b in bills})
        tenant_ids = list({b["tenant_id"] for b in bills})
        units = await db["units"].find({"id": {"$in": unit_ids}}, {"_id": 0}).to_list(1000)
        tenants = await db["users"].find(
            {"id": {"$in": tenant_ids}}, {"_id": 0, "password_hash": 0}
        ).to_list(1000)
        u_map = {u["id"]: u for u in units}
        t_map = {t["id"]: t for t in tenants}
        for b in bills:
            u = u_map.get(b["unit_id"])
            t = t_map.get(b["tenant_id"])
            if u:
                b["unit_number"] = u["unit_number"]
            if t:
                b["tenant_name"] = t["full_name"]
    return bills


@router.post("/bills", response_model=Bill)
async def create_bill(
    payload: BillCreate, user: dict = Depends(require_role("landlord"))
):
    db = get_db()
    tenant = await db["users"].find_one(
        {"id": payload.tenant_id, "landlord_id": user["id"], "role": "tenant"}
    )
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    unit = await db["units"].find_one(
        {"id": payload.unit_id, "landlord_id": user["id"]}
    )
    if not unit:
        raise HTTPException(404, "Unit not found")

    doc = {
        "id": new_id(),
        "landlord_id": user["id"],
        "property_id": unit["property_id"],
        "unit_id": payload.unit_id,
        "tenant_id": payload.tenant_id,
        "bill_type": payload.bill_type,
        "amount": payload.amount,
        "amount_paid": 0,
        "period": payload.period,
        "due_date": payload.due_date,
        "status": "pending",
        "description": payload.description or "",
        "created_at": now_iso(),
    }
    await db["bills"].insert_one(doc)
    doc.pop("_id", None)
    await notify_user(
        payload.tenant_id, "bill_due",
        f"New bill: {payload.bill_type.title()} · {payload.period}",
        f"KES {payload.amount:,.0f} due by {payload.due_date}.",
        link="/bills",
    )
    return Bill(**doc)


@router.post("/bills/generate-monthly")
async def generate_monthly_bills(user: dict = Depends(require_role("landlord"))):
    """Auto-generate rent bills for all occupied units for the current month."""
    db = get_db()
    period = _current_period()
    units = await db["units"].find(
        {"landlord_id": user["id"], "occupied": True}, {"_id": 0}
    ).to_list(1000)

    created = 0
    skipped = 0
    for unit in units:
        # check if bill already exists for this period
        existing = await db["bills"].find_one({
            "unit_id": unit["id"],
            "period": period,
            "bill_type": "rent",
        })
        if existing:
            skipped += 1
            continue
        # set due date to 5th of next month
        now = datetime.now(timezone.utc)
        if now.month == 12:
            due_date = datetime(now.year + 1, 1, 5, tzinfo=timezone.utc)
        else:
            due_date = datetime(now.year, now.month + 1, 5, tzinfo=timezone.utc)
        doc = {
            "id": new_id(),
            "landlord_id": user["id"],
            "property_id": unit["property_id"],
            "unit_id": unit["id"],
            "tenant_id": unit["tenant_id"],
            "bill_type": "rent",
            "amount": unit["rent_amount"],
            "amount_paid": 0,
            "period": period,
            "due_date": due_date.isoformat(),
            "status": "pending",
            "description": f"Monthly rent for {period}",
            "created_at": now_iso(),
        }
        await db["bills"].insert_one(doc)
        created += 1
        await notify_user(
            unit["tenant_id"], "bill_due",
            f"Rent bill for {period}",
            f"KES {unit['rent_amount']:,.0f} due by {due_date.strftime('%Y-%m-%d')}.",
            link="/bills",
        )
    return {"created": created, "skipped": skipped, "period": period}


@router.delete("/bills/{bill_id}")
async def delete_bill(bill_id: str, user: dict = Depends(require_role("landlord"))):
    db = get_db()
    res = await db["bills"].delete_one({"id": bill_id, "landlord_id": user["id"]})
    if res.deleted_count == 0:
        raise HTTPException(404, "Bill not found")
    return {"ok": True}
