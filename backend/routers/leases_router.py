"""Phase 4 — Digital Lease Agreements with PDF generation + tenant e-sign."""
import io
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from auth import get_current_user, require_role
from db import get_db
from models import LeaseCreate, new_id, now_iso
from notifications import notify_user

router = APIRouter(tags=["leases"])

UPLOAD_DIR = "uploads/leases"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _build_pdf(lease: dict, landlord: dict, tenant: dict, prop: dict, unit: dict) -> bytes:
    """Render a tidy single-page PDF for the lease."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    )
    from reportlab.lib import colors

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=20, spaceAfter=10, textColor=colors.black)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=12, spaceAfter=6, textColor=colors.HexColor("#444"))
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=10, leading=14)

    is_rental = (lease.get("agreement_type") or "lease") == "rental"
    title = "RENTAL AGREEMENT" if is_rental else "RESIDENTIAL LEASE AGREEMENT"
    story = [
        Paragraph(title, h1),
        Paragraph(f"Document ID: <b>{lease['id'][:8]}</b> · Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", body),
        Spacer(1, 12),
        Paragraph("PARTIES", h2),
    ]
    parties = [
        ["Landlord", f"{landlord.get('full_name','')} · {landlord.get('phone','')} · {landlord.get('email','')}"],
        ["Tenant", f"{tenant.get('full_name','')} · {tenant.get('phone','')} · {tenant.get('email','')}"],
    ]
    story.append(Table(parties, colWidths=[3*cm, 13*cm], style=TableStyle([
        ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#f4f4f5")),
        ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 10),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("INNERGRID", (0,0), (-1,-1), 0.4, colors.HexColor("#ddd")),
        ("BOX", (0,0), (-1,-1), 0.4, colors.HexColor("#ddd")),
        ("LEFTPADDING", (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 8),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ])))
    story.append(Spacer(1, 14))

    story.append(Paragraph("PROPERTY", h2))
    property_rows = [
        ["Property", f"{prop.get('name','')}"],
        ["Address", f"{prop.get('address','')}"],
        ["Unit", f"{unit.get('unit_number','')} · {unit.get('bedrooms','?')} bed"],
    ]
    story.append(Table(property_rows, colWidths=[3*cm, 13*cm], style=TableStyle([
        ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#f4f4f5")),
        ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 10),
        ("INNERGRID", (0,0), (-1,-1), 0.4, colors.HexColor("#ddd")),
        ("BOX", (0,0), (-1,-1), 0.4, colors.HexColor("#ddd")),
        ("LEFTPADDING", (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 8),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ])))
    story.append(Spacer(1, 14))

    story.append(Paragraph("TERMS", h2))
    terms_rows = [
        ["Monthly Rent", f"KES {lease['rent_amount']:,.0f}"],
        ["Security Deposit", f"KES {lease['deposit_amount']:,.0f}"],
        ["Start Date", lease["start_date"]],
        ["End Date", lease["end_date"]],
    ]
    story.append(Table(terms_rows, colWidths=[5*cm, 11*cm], style=TableStyle([
        ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#f4f4f5")),
        ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 10),
        ("INNERGRID", (0,0), (-1,-1), 0.4, colors.HexColor("#ddd")),
        ("BOX", (0,0), (-1,-1), 0.4, colors.HexColor("#ddd")),
        ("LEFTPADDING", (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 8),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ])))
    story.append(Spacer(1, 14))

    story.append(Paragraph("ADDITIONAL TERMS & CONDITIONS", h2))
    raw_terms = (lease.get("terms") or "Standard residential tenancy terms apply under the Laws of Kenya. The tenant shall pay rent on or before the 5th of each month via M-Pesa through the NyumbaOS platform. The landlord shall maintain the property in good repair.").replace("\n", "<br/>")
    story.append(Paragraph(raw_terms, body))
    story.append(Spacer(1, 16))

    story.append(Paragraph("E-SIGNATURE", h2))
    if lease.get("status") == "signed":
        story.append(Paragraph(
            f"<b>Signed by Tenant:</b> {tenant.get('full_name','')}<br/>"
            f"<b>Signed at:</b> {lease.get('signed_at','')}<br/>"
            f"<b>From IP:</b> {lease.get('signed_ip','')}", body))
    else:
        story.append(Paragraph(
            "Awaiting tenant electronic signature via the NYUMBA FITI app.", body))

    doc.build(story)
    return buf.getvalue()


@router.post("/leases")
async def create_lease(payload: LeaseCreate, user: dict = Depends(require_role("landlord"))):
    db = get_db()
    unit = await db["units"].find_one({"id": payload.unit_id, "landlord_id": user["id"]})
    if not unit:
        raise HTTPException(404, "Unit not found or not owned by you")
    tenant = await db["users"].find_one({"id": payload.tenant_id, "role": "tenant"})
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    prop = await db["properties"].find_one({"id": unit["property_id"]})

    # Validate agreement_type matches property's tenancy_types
    if prop:
        allowed = prop.get("tenancy_types") or ["rental"]
        if payload.agreement_type not in allowed:
            raise HTTPException(
                400,
                f"This property only supports: {', '.join(allowed)}. "
                f"You picked agreement_type='{payload.agreement_type}'.",
            )

    lease_id = new_id()
    lease_doc = {
        "id": lease_id,
        "landlord_id": user["id"],
        "tenant_id": payload.tenant_id,
        "tenant_name": tenant["full_name"],
        "unit_id": payload.unit_id,
        "property_id": unit["property_id"],
        "agreement_type": payload.agreement_type,
        "rent_amount": payload.rent_amount,
        "deposit_amount": payload.deposit_amount,
        "start_date": payload.start_date,
        "end_date": payload.end_date,
        "terms": payload.terms or "",
        "pdf_path": None,
        "status": "sent",
        "signed_at": None,
        "signed_ip": None,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    pdf_bytes = _build_pdf(lease_doc, user, tenant, prop or {}, unit)
    pdf_filename = f"lease_{lease_id}.pdf"
    pdf_path = f"{UPLOAD_DIR}/{pdf_filename}"
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)
    lease_doc["pdf_path"] = pdf_path
    await db["leases"].insert_one(lease_doc)
    lease_doc.pop("_id", None)

    doc_label = "Rental Agreement" if payload.agreement_type == "rental" else "Lease Agreement"
    await notify_user(
        payload.tenant_id, "lease_pending",
        f"New {doc_label.lower()} awaiting your e-signature",
        f"Your landlord has sent a {doc_label.lower()} for unit {unit.get('unit_number','')}. Open and sign in-app.",
        link="/leases",
    )
    return lease_doc


@router.get("/leases")
async def list_leases(user: dict = Depends(get_current_user)):
    db = get_db()
    if user["role"] == "landlord":
        query = {"landlord_id": user["id"]}
    elif user["role"] == "tenant":
        query = {"tenant_id": user["id"]}
    elif user["role"] == "admin":
        query = {}
    else:
        return []
    items = await db["leases"].find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return items


@router.get("/leases/{lease_id}")
async def get_lease(lease_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    lease = await db["leases"].find_one({"id": lease_id}, {"_id": 0})
    if not lease:
        raise HTTPException(404, "Lease not found")
    if user["role"] == "landlord" and lease["landlord_id"] != user["id"]:
        raise HTTPException(403, "Forbidden")
    if user["role"] == "tenant" and lease["tenant_id"] != user["id"]:
        raise HTTPException(403, "Forbidden")
    return lease


@router.post("/leases/{lease_id}/sign")
async def sign_lease(lease_id: str, request: Request, user: dict = Depends(require_role("tenant"))):
    db = get_db()
    lease = await db["leases"].find_one({"id": lease_id})
    if not lease:
        raise HTTPException(404, "Lease not found")
    if lease["tenant_id"] != user["id"]:
        raise HTTPException(403, "Forbidden")
    if lease["status"] == "signed":
        raise HTTPException(400, "Already signed")
    if lease["status"] == "cancelled":
        raise HTTPException(400, "Lease cancelled")

    ip = (request.client.host if request.client else "") or request.headers.get("x-forwarded-for", "")
    signed_at = now_iso()
    lease_doc = {**lease, "status": "signed", "signed_at": signed_at, "signed_ip": ip, "updated_at": signed_at}

    # Re-render PDF with signature info
    landlord = await db["users"].find_one({"id": lease["landlord_id"]}) or {}
    tenant = await db["users"].find_one({"id": user["id"]}) or {}
    prop = await db["properties"].find_one({"id": lease["property_id"]}) or {}
    unit = await db["units"].find_one({"id": lease["unit_id"]}) or {}
    pdf_bytes = _build_pdf(lease_doc, landlord, tenant, prop, unit)
    pdf_path = lease.get("pdf_path") or f"{UPLOAD_DIR}/lease_{lease_id}.pdf"
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)

    await db["leases"].update_one(
        {"id": lease_id},
        {"$set": {
            "status": "signed", "signed_at": signed_at, "signed_ip": ip,
            "pdf_path": pdf_path, "updated_at": signed_at,
        }},
    )
    await notify_user(
        lease["landlord_id"], "lease_signed",
        f"{user['full_name']} signed their lease",
        f"Tenant signed at {signed_at}. Download the signed PDF from /leases.",
        link="/leases",
    )
    return {"ok": True, "signed_at": signed_at}


@router.delete("/leases/{lease_id}")
async def cancel_lease(lease_id: str, user: dict = Depends(get_current_user)):
    db = get_db()
    lease = await db["leases"].find_one({"id": lease_id})
    if not lease:
        raise HTTPException(404, "Lease not found")
    if user["role"] != "admin" and lease["landlord_id"] != user["id"]:
        raise HTTPException(403, "Forbidden")
    if lease["status"] == "signed":
        raise HTTPException(400, "Cannot cancel a signed lease — keep it as record")
    await db["leases"].update_one(
        {"id": lease_id}, {"$set": {"status": "cancelled", "updated_at": now_iso()}}
    )
    return {"ok": True}
