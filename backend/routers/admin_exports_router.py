"""Phase 6 — Admin exports: CSV, XLSX, PDF for users / payments / payouts / properties / bills / issues / viewings / leases."""
import csv
import io
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from auth import require_role
from db import get_db

router = APIRouter(prefix="/admin/export", tags=["admin-exports"])


# ====================== Data fetchers ======================

async def _fetch_users(role: Optional[str] = None) -> List[Dict[str, Any]]:
    db = get_db()
    q = {"role": role} if role else {}
    rows = await db["users"].find(q, {"_id": 0, "password_hash": 0}).sort("created_at", -1).to_list(10000)
    return [{
        "id": r["id"],
        "full_name": r.get("full_name", ""),
        "email": r.get("email", ""),
        "phone": r.get("phone", ""),
        "role": r.get("role", ""),
        "tenancy_type": r.get("tenancy_type", ""),
        "approval_status": r.get("approval_status", ""),
        "suspended": r.get("suspended", False),
        "landlord_id": r.get("landlord_id") or "",
        "created_at": r.get("created_at", ""),
    } for r in rows]


async def _fetch_payments() -> List[Dict[str, Any]]:
    db = get_db()
    rows = await db["payments"].find({}, {"_id": 0}).sort("created_at", -1).to_list(10000)
    landlord_ids = list({r.get("landlord_id") for r in rows if r.get("landlord_id")})
    landlords = await db["users"].find({"id": {"$in": landlord_ids}}, {"_id": 0, "id": 1, "full_name": 1}).to_list(500) if landlord_ids else []
    l_map = {ld["id"]: ld["full_name"] for ld in landlords}
    return [{
        "id": r["id"],
        "mpesa_receipt": r.get("mpesa_receipt", ""),
        "amount": r.get("amount", 0),
        "commission_amount": r.get("commission_amount", 0),
        "net_to_landlord": r.get("net_to_landlord", 0),
        "phone_number": r.get("phone_number", ""),
        "status": r.get("status", ""),
        "purpose": r.get("purpose", ""),
        "landlord_name": l_map.get(r.get("landlord_id"), ""),
        "created_at": r.get("created_at", ""),
    } for r in rows]


async def _fetch_payouts() -> List[Dict[str, Any]]:
    db = get_db()
    rows = await db["payouts"].find({}, {"_id": 0}).sort("created_at", -1).to_list(10000)
    landlord_ids = list({r["landlord_id"] for r in rows})
    landlords = await db["users"].find({"id": {"$in": landlord_ids}}, {"_id": 0, "id": 1, "full_name": 1}).to_list(500) if landlord_ids else []
    l_map = {ld["id"]: ld["full_name"] for ld in landlords}
    return [{
        "id": r["id"],
        "landlord_name": l_map.get(r["landlord_id"], ""),
        "amount": r.get("amount", 0),
        "status": r.get("status", ""),
        "note": r.get("note", ""),
        "created_at": r.get("created_at", ""),
    } for r in rows]


async def _fetch_properties() -> List[Dict[str, Any]]:
    db = get_db()
    rows = await db["properties"].find({}, {"_id": 0}).sort("created_at", -1).to_list(10000)
    landlord_ids = list({r["landlord_id"] for r in rows})
    landlords = await db["users"].find({"id": {"$in": landlord_ids}}, {"_id": 0, "id": 1, "full_name": 1}).to_list(500) if landlord_ids else []
    l_map = {ld["id"]: ld["full_name"] for ld in landlords}
    return [{
        "id": r["id"],
        "name": r.get("name", ""),
        "address": r.get("address", ""),
        "category": r.get("category", ""),
        "sub_type": r.get("sub_type", ""),
        "tenancy_types": ",".join(r.get("tenancy_types") or []),
        "approval_status": r.get("approval_status", ""),
        "featured": r.get("featured", False),
        "landlord_name": l_map.get(r["landlord_id"], ""),
        "created_at": r.get("created_at", ""),
    } for r in rows]


async def _fetch_bills() -> List[Dict[str, Any]]:
    db = get_db()
    rows = await db["bills"].find({}, {"_id": 0}).sort("created_at", -1).to_list(10000)
    return [{
        "id": r["id"],
        "tenant_id": r.get("tenant_id", ""),
        "amount": r.get("amount", 0),
        "amount_paid": r.get("amount_paid", 0),
        "status": r.get("status", ""),
        "purpose": r.get("purpose", ""),
        "due_date": r.get("due_date", ""),
        "created_at": r.get("created_at", ""),
    } for r in rows]


async def _fetch_issues() -> List[Dict[str, Any]]:
    db = get_db()
    rows = await db["issues"].find({}, {"_id": 0}).sort("created_at", -1).to_list(10000)
    return [{
        "id": r["id"],
        "title": r.get("title", ""),
        "category": r.get("category", ""),
        "severity": r.get("severity", ""),
        "status": r.get("status", ""),
        "reported_by": r.get("reported_by_name", ""),
        "assigned_to": r.get("assigned_to_name", ""),
        "resolved_by_role": r.get("resolved_by_role", ""),
        "created_at": r.get("created_at", ""),
    } for r in rows]


async def _fetch_viewings() -> List[Dict[str, Any]]:
    db = get_db()
    rows = await db["viewings"].find({}, {"_id": 0}).sort("created_at", -1).to_list(10000)
    return [{
        "id": r["id"],
        "prospect_name": r.get("prospect_name", ""),
        "prospect_email": r.get("prospect_email", ""),
        "prospect_phone": r.get("prospect_phone", ""),
        "scheduled_date": r.get("scheduled_date", ""),
        "scheduled_time": r.get("scheduled_time", ""),
        "status": r.get("status", ""),
        "viewing_fee": r.get("viewing_fee", 0),
        "created_at": r.get("created_at", ""),
    } for r in rows]


async def _fetch_leases() -> List[Dict[str, Any]]:
    db = get_db()
    rows = await db["leases"].find({}, {"_id": 0}).sort("created_at", -1).to_list(10000)
    return [{
        "id": r["id"],
        "tenant_id": r.get("tenant_id", ""),
        "landlord_id": r.get("landlord_id", ""),
        "agreement_type": r.get("agreement_type", ""),
        "monthly_rent": r.get("monthly_rent", 0),
        "deposit": r.get("deposit", 0),
        "status": r.get("status", ""),
        "start_date": r.get("start_date", ""),
        "signed_at": r.get("signed_at", ""),
        "created_at": r.get("created_at", ""),
    } for r in rows]


RESOURCES = {
    "users": _fetch_users,
    "payments": _fetch_payments,
    "payouts": _fetch_payouts,
    "properties": _fetch_properties,
    "bills": _fetch_bills,
    "issues": _fetch_issues,
    "viewings": _fetch_viewings,
    "leases": _fetch_leases,
}


# ====================== Renderers ======================

def _to_csv(rows: List[Dict[str, Any]]) -> bytes:
    if not rows:
        return b"(no records)\n"
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    for r in rows:
        writer.writerow({k: ("" if v is None else v) for k, v in r.items()})
    return buf.getvalue().encode("utf-8")


def _to_xlsx(rows: List[Dict[str, Any]], sheet_name: str = "Sheet1") -> bytes:
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name[:31] or "Sheet1"
    if not rows:
        ws.append(["(no records)"])
    else:
        headers = list(rows[0].keys())
        ws.append(headers)
        for r in rows:
            ws.append([r.get(h, "") for h in headers])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _to_pdf(rows: List[Dict[str, Any]], title: str = "Nyumba OS Export") -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=24, rightMargin=24, topMargin=28, bottomMargin=24)
    styles = getSampleStyleSheet()
    story = [Paragraph(f"<b>{title}</b>", styles["Title"]), Spacer(1, 8)]
    if not rows:
        story.append(Paragraph("(no records)", styles["Normal"]))
    else:
        headers = list(rows[0].keys())
        data = [headers] + [[str(r.get(h, ""))[:48] for h in headers] for r in rows[:500]]
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#18181b")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d4d4d8")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafafa")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(table)
        if len(rows) > 500:
            story.append(Spacer(1, 8))
            story.append(Paragraph(f"<i>...truncated to first 500 of {len(rows)} rows. Use CSV/XLSX for the full set.</i>", styles["Normal"]))
    doc.build(story)
    return buf.getvalue()


# ====================== Endpoint ======================

@router.get("/{resource}.{ext}")
async def export_resource(
    resource: str,
    ext: str,
    user: dict = Depends(require_role("admin")),
):
    if resource not in RESOURCES:
        raise HTTPException(404, f"Unknown resource. Allowed: {', '.join(RESOURCES)}")
    if ext not in ("csv", "xlsx", "pdf"):
        raise HTTPException(400, "ext must be one of: csv, xlsx, pdf")

    rows = await RESOURCES[resource]()
    filename = f"nyumbaos_{resource}.{ext}"

    if ext == "csv":
        return StreamingResponse(
            io.BytesIO(_to_csv(rows)),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    if ext == "xlsx":
        return StreamingResponse(
            io.BytesIO(_to_xlsx(rows, sheet_name=resource)),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    # pdf
    return StreamingResponse(
        io.BytesIO(_to_pdf(rows, title=f"Nyumba OS — {resource.title()}")),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
