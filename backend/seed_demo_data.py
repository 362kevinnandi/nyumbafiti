"""Demo data seeder for NYUMBA FITI.

Usage:
  cd /app/backend && python3 seed_demo_data.py [--reset]

--reset wipes (most) demo collections before reseeding. Admin user is preserved.
"""
import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auth import hash_password
from db import get_db
from motor.motor_asyncio import AsyncIOMotorClient
import models as m

RESET = "--reset" in sys.argv


def iso_now():
    return datetime.now(timezone.utc).isoformat()


async def main():
    # Bootstrap DB client (mimic server.py)
    client = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    db_name = os.environ.get("DB_NAME", "rental_management")
    db = client[db_name]

    if RESET:
        print("Wiping demo collections (keeping admin + platform_settings)...")
        for coll in ["properties", "units", "users_temp", "bills", "payments",
                     "viewings", "issues", "leases", "visitor_passes",
                     "yard_sale", "announcements", "forum_threads", "forum_replies",
                     "reactions", "announcement_views", "ai_conversations",
                     "notifications", "payouts"]:
            await db[coll].delete_many({})
        # Delete non-admin users
        await db["users"].delete_many({"role": {"$ne": "admin"}})
        print("Wiped.")

    # ---- Landlords ----
    landlords = []
    LL_DATA = [
        ("Mary Wanjiku", "mary@demo.nyumba", "254712345001"),
        ("James Otieno", "james@demo.nyumba", "254712345002"),
    ]
    for name, email, phone in LL_DATA:
        u = await db["users"].find_one({"email": email})
        if u:
            landlords.append(u)
            continue
        doc = {
            "id": m.new_id(), "email": email, "full_name": name, "phone": phone,
            "role": "landlord", "password_hash": hash_password("demo123"),
            "approval_status": "approved", "created_at": iso_now(),
            "landlord_id": None, "unit_id": None,
        }
        await db["users"].insert_one(doc)
        landlords.append(doc)
        print(f"+ Landlord: {email} / demo123")

    # ---- Properties + units (6 properties, mix lease/rental) ----
    AREAS = [
        ("Westlands Park Apartments", "Westlands, Nairobi", "apartment", "2br", ["rental"]),
        ("Kilimani Heights", "Kilimani, Nairobi", "apartment", "1br", ["rental", "lease"]),
        ("Karen Villas", "Karen, Nairobi", "own_compound", "4br", ["lease"]),
        ("Lavington Maisonettes", "Lavington, Nairobi", "own_compound", "3br", ["lease", "rental"]),
        ("Roysambu Bedsitters", "Roysambu, Nairobi", "apartment", "bedsitter", ["rental"]),
        ("South B Studios", "South B, Nairobi", "apartment", "single_room", ["rental"]),
    ]
    properties = []
    for idx, (name, addr, category, sub, tts) in enumerate(AREAS):
        ll = landlords[idx % len(landlords)]
        existing = await db["properties"].find_one({"name": name})
        if existing:
            properties.append(existing)
            continue
        doc = {
            "id": m.new_id(), "name": name, "address": addr,
            "description": f"Modern {sub} units in {addr.split(',')[0]}.",
            "category": category, "sub_type": sub, "tenancy_types": tts,
            "landlord_id": ll["id"], "approval_status": "approved",
            "featured": idx < 2, "images": [],
            "created_at": iso_now(),
        }
        await db["properties"].insert_one(doc)
        properties.append(doc)
        print(f"+ Property: {name} ({category}/{sub}) {tts}")

    # ---- Units (2 per property) ----
    units = []
    for p in properties:
        existing_units = await db["units"].count_documents({"property_id": p["id"]})
        if existing_units >= 2:
            units.extend(await db["units"].find({"property_id": p["id"]}).to_list(10))
            continue
        for i in range(2):
            doc = {
                "id": m.new_id(),
                "property_id": p["id"],
                "landlord_id": p["landlord_id"],
                "unit_number": f"{i + 1}A",
                "rent_amount": 25000 + (i * 7000) + (hash(p["name"]) % 15000),
                "bedrooms": 2 if "2br" in p.get("sub_type", "") else 1,
                "description": f"Unit {i + 1}A — fresh paint, water tank, parking.",
                "occupied": False, "tenant_id": None,
                "created_at": iso_now(),
            }
            await db["units"].insert_one(doc)
            units.append(doc)
    print(f"+ Units total: {len(units)}")

    # ---- Caretakers + Security (1 each per landlord) ----
    for idx, ll in enumerate(landlords):
        for role, mail in [("caretaker", f"ck{idx + 1}@demo.nyumba"),
                           ("security", f"sg{idx + 1}@demo.nyumba")]:
            existing = await db["users"].find_one({"email": mail})
            if existing:
                continue
            doc = {
                "id": m.new_id(), "email": mail,
                "full_name": f"{role.title()} {idx + 1}",
                "phone": f"254711000{idx}0{role[0]}",
                "role": role, "password_hash": hash_password("demo123"),
                "landlord_id": ll["id"], "unit_id": None,
                "approval_status": "approved",
                "created_at": iso_now(),
            }
            await db["users"].insert_one(doc)
            print(f"+ {role.title()}: {mail} / demo123 (landlord={ll['email']})")

    # ---- Tenants (assign to first 4 units, mix tenancy_type) ----
    tenant_emails = []
    for i, u in enumerate(units[:4]):
        prop = next((p for p in properties if p["id"] == u["property_id"]), None)
        if not prop:
            continue
        # Pick a tenancy_type compatible with the property
        tts = prop.get("tenancy_types") or ["rental"]
        ttype = tts[i % len(tts)]
        email = f"tenant{i + 1}@demo.nyumba"
        tenant_emails.append((email, ttype))
        existing = await db["users"].find_one({"email": email})
        if existing:
            continue
        doc = {
            "id": m.new_id(), "email": email,
            "full_name": f"Tenant {i + 1}",
            "phone": f"25470{i + 1}000000",
            "role": "tenant", "password_hash": hash_password("demo123"),
            "tenancy_type": ttype,
            "landlord_id": u["landlord_id"], "unit_id": u["id"],
            "approval_status": "approved",
            "created_at": iso_now(),
        }
        await db["users"].insert_one(doc)
        await db["units"].update_one({"id": u["id"]}, {"$set": {"tenant_id": doc["id"], "occupied": True}})
        print(f"+ Tenant: {email} / demo123 ({ttype} @ {prop['name']})")

    # ---- Announcements (4) ----
    for i, txt in enumerate([
        ("Water shutdown Saturday 9am-12pm", "global", "Nairobi Water has scheduled maintenance. Stock up tonight."),
        ("Welcome to NYUMBA FITI 🎉", "global", "Pay rent via M-Pesa in 3 taps, raise issues, find verified units."),
        ("Garbage day shifted to Wednesday", "property", "Bins at the back gate by 6am sharp."),
        ("Reminder: lease renewals due Feb 28", "property", "Please confirm via the Agreements tab."),
    ]):
        title, scope, body = txt
        existing = await db["announcements"].find_one({"title": title})
        if existing:
            continue
        ll = landlords[i % len(landlords)]
        ann = {
            "id": m.new_id(), "title": title, "body": body,
            "scope": scope,
            "property_id": properties[i % len(properties)]["id"] if scope == "property" else None,
            "author_id": ll["id"] if scope == "property" else "admin",
            "author_name": ll["full_name"] if scope == "property" else "Platform Admin",
            "author_role": "landlord" if scope == "property" else "admin",
            "landlord_id": ll["id"] if scope == "property" else None,
            "pinned": i == 0, "attachments": [],
            "created_at": iso_now(),
        }
        await db["announcements"].insert_one(ann)
        print(f"+ Announcement: {title}")

    # ---- Yard sale: 2 active (paid), 2 pending_payment, 1 broadcast ----
    seller_email = tenant_emails[0][0] if tenant_emails else None
    seller = await db["users"].find_one({"email": seller_email}) if seller_email else None
    YS = [
        ("Solar lamp 30W", 1500, "electronics", "active", True, "property"),
        ("Used microwave Haier", 3500, "appliances", "active", True, "property"),
        ("Office chair", 2000, "furniture", "pending_payment", False, "property"),
        ("Kids' bicycle", 4500, "sports", "pending_payment", False, "property"),
        ("Brand new toaster", 2800, "kitchen", "active", True, "all"),
    ]
    if seller:
        prop = await db["properties"].find_one({"id": seller["unit_id"] and (await db["units"].find_one({"id": seller["unit_id"]}))["property_id"] if seller.get("unit_id") else None})
        for title, price, cat, status, unlocked, scope in YS:
            existing = await db["yard_sale"].find_one({"title": title, "seller_id": seller["id"]})
            if existing:
                continue
            doc = {
                "id": m.new_id(), "seller_id": seller["id"], "seller_name": seller["full_name"],
                "seller_phone": seller["phone"], "seller_email": seller["email"],
                "landlord_id": seller["landlord_id"], "property_id": prop["id"] if prop else None,
                "title": title, "description": f"Demo {title}.", "price": float(price),
                "category": cat, "images": [], "featured": False, "featured_until": None,
                "contact_unlocked": unlocked, "scope": scope, "status": status,
                "created_at": iso_now(), "updated_at": iso_now(),
            }
            await db["yard_sale"].insert_one(doc)
            print(f"+ Yard sale: {title} ({status}, unlocked={unlocked})")

    # ---- Visitor passes: 1 active per landlord, 1 used ----
    import secrets
    for idx, ll in enumerate(landlords):
        existing_active = await db["visitor_passes"].count_documents({"landlord_id": ll["id"], "status": "active"})
        if existing_active >= 1:
            continue
        # Find any unit
        ll_units = [u for u in units if u["landlord_id"] == ll["id"]]
        if not ll_units:
            continue
        unit = ll_units[0]
        tenant = await db["users"].find_one({"unit_id": unit["id"], "role": "tenant"})
        if not tenant:
            continue
        expires = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
        expected = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        doc = {
            "id": m.new_id(), "token": secrets.token_urlsafe(20),
            "tenant_id": tenant["id"], "tenant_name": tenant["full_name"],
            "landlord_id": ll["id"], "property_id": unit["property_id"],
            "unit_id": unit["id"], "visitor_name": f"Guest of {tenant['full_name']}",
            "visitor_phone": "254700123456",
            "expected_time": expected, "notes": "Sample visitor pass — demo data.",
            "status": "active", "used_at": None, "used_by_caretaker_id": None,
            "used_by_caretaker_name": None,
            "expires_at": expires, "created_at": iso_now(),
        }
        await db["visitor_passes"].insert_one(doc)
        print(f"+ Visitor pass for {tenant['full_name']}")

    # ---- Issues: 3 (1 open, 1 in_progress, 1 resolved) ----
    if tenant_emails:
        tenant = await db["users"].find_one({"email": tenant_emails[0][0]})
        if tenant:
            ll = await db["users"].find_one({"id": tenant["landlord_id"]})
            ISSUES = [
                ("Leaky kitchen tap", "plumbing", "medium", "open"),
                ("Lift stuck on 3rd floor", "common_area", "high", "in_progress"),
                ("Bulb out in stairwell", "electrical", "low", "resolved"),
            ]
            for title, cat, sev, status in ISSUES:
                existing = await db["issues"].find_one({"title": title, "reported_by": tenant["id"]})
                if existing:
                    continue
                doc = {
                    "id": m.new_id(), "title": title, "description": f"Demo issue: {title}.",
                    "category": cat, "severity": sev, "status": status,
                    "tenant_id": tenant["id"],
                    "reported_by": tenant["id"], "reported_by_name": tenant["full_name"],
                    "landlord_id": tenant["landlord_id"],
                    "property_id": (await db["units"].find_one({"id": tenant["unit_id"]}))["property_id"],
                    "unit_id": tenant["unit_id"], "messages": [],
                    "created_at": iso_now(),
                }
                if status == "resolved":
                    doc["resolved_at"] = iso_now()
                    doc["resolved_by_role"] = "caretaker"
                await db["issues"].insert_one(doc)
                print(f"+ Issue: {title} ({status})")

    print("\n=== Demo data seed complete ===")
    print("Test credentials (all password=demo123 unless noted):")
    print("  Admin:    admin@nyumbaos.co.ke / admin123")
    print("  Landlord: mary@demo.nyumba, james@demo.nyumba")
    print("  Tenants:  tenant1@demo.nyumba ... tenant4@demo.nyumba")
    print("  Caretakers: ck1@demo.nyumba, ck2@demo.nyumba")
    print("  Security:   sg1@demo.nyumba, sg2@demo.nyumba")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
    asyncio.run(main())
