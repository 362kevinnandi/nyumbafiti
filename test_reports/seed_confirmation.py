"""Seed one bill into awaiting_landlord_confirmation for mary's tenant1"""
import os, sys, uuid
from datetime import datetime, timezone
from pymongo import MongoClient

env = {}
for line in open("/app/backend/.env"):
    if "=" in line:
        k, v = line.strip().split("=", 1)
        env[k] = v.strip('"')

client = MongoClient(env["MONGO_URL"])
db = client[env["DB_NAME"]]

tenant = db.users.find_one({"email": "tenant1@demo.nyumba"})
ll = db.users.find_one({"email": "mary@demo.nyumba"})
unit = db.units.find_one({"id": tenant["unit_id"]})
print("tenant", tenant["id"], "ll", ll["id"], "unit", unit["id"], "prop", unit["property_id"])

now = datetime.now(timezone.utc).isoformat()
bill = {
    "id": str(uuid.uuid4()),
    "tenant_id": tenant["id"],
    "landlord_id": ll["id"],
    "unit_id": unit["id"],
    "property_id": unit["property_id"],
    "bill_type": "rent",
    "amount": 25000.0,
    "amount_paid": 0,
    "period": "2026-01",
    "due_date": "2026-01-25",
    "description": "TEST_SEED_R7 awaiting confirmation",
    "status": "awaiting_landlord_confirmation",
    "service_fee_paid_at": now,
    "rent_receipt_code": "SEEDUITEST",
    "rent_receipt_amount": 25000.0,
    "rent_receipt_submitted_at": now,
    "created_at": now,
}
db.bills.insert_one(bill)
print("Inserted bill", bill["id"])
client.close()
