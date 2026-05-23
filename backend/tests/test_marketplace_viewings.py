"""End-to-end tests for the public marketplace + viewing booking flow.

Covers:
- Public listings (no auth)
- Listing detail + viewing fee
- max_rent filter
- POST /public/viewings (auto-creates prospect, payment, M-Pesa STK push in demo mode)
- Demo callback transitions viewing -> 'scheduled'
- Polling endpoint sanitizes vs. reveals contact info based on status
- Prospect login + /my-viewings
- Landlord /viewings
- /auth/register with role=prospect rejected
- Re-booking same email reuses prospect (no password returned 2nd time)
- Booking on occupied unit returns 404
- /dashboard/stats for prospect
"""
import os
import time
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")
API = f"{BASE_URL}/api"

UNIQ = uuid.uuid4().hex[:8]
LANDLORD_EMAIL = f"TEST_mkt_land_{UNIQ}@demo.com"
LANDLORD_PASS = "demo123"
PROSPECT_EMAIL = f"TEST_prospect_{UNIQ}@demo.com"
PROSPECT2_EMAIL = f"TEST_prospect2_{UNIQ}@demo.com"

state = {}


def h(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ----- Setup landlord with vacant + occupied units -----
def test_setup_landlord_and_units():
    r = requests.post(f"{API}/auth/register", json={
        "email": LANDLORD_EMAIL,
        "full_name": "Mkt Landlord",
        "phone": "0712345678",
        "role": "landlord",
        "password": LANDLORD_PASS,
    })
    assert r.status_code == 200, r.text
    state["landlord_token"] = r.json()["access_token"]
    state["landlord_id"] = r.json()["user"]["id"]

    # caretaker
    r = requests.post(f"{API}/caretakers", json={
        "email": f"TEST_ct_{UNIQ}@demo.com",
        "full_name": "Mkt Caretaker",
        "phone": "0722000111",
        "password": "ctpass1",
    }, headers=h(state["landlord_token"]))
    assert r.status_code == 200, r.text

    # property
    r = requests.post(f"{API}/properties", json={
        "name": f"TEST Riverside {UNIQ}",
        "address": "Riverside, Nairobi",
        "description": "Test property",
    }, headers=h(state["landlord_token"]))
    assert r.status_code == 200, r.text
    state["property_id"] = r.json()["id"]

    # vacant unit (cheap)
    r = requests.post(f"{API}/units", json={
        "property_id": state["property_id"],
        "unit_number": f"V1-{UNIQ}",
        "rent_amount": 15000,
        "bedrooms": 1,
    }, headers=h(state["landlord_token"]))
    assert r.status_code == 200, r.text
    state["vacant_unit_id"] = r.json()["id"]

    # vacant unit (expensive) - for max_rent filter
    r = requests.post(f"{API}/units", json={
        "property_id": state["property_id"],
        "unit_number": f"V2-{UNIQ}",
        "rent_amount": 60000,
        "bedrooms": 3,
    }, headers=h(state["landlord_token"]))
    assert r.status_code == 200, r.text
    state["expensive_unit_id"] = r.json()["id"]

    # vacant unit that we will occupy via tenant create
    r = requests.post(f"{API}/units", json={
        "property_id": state["property_id"],
        "unit_number": f"O1-{UNIQ}",
        "rent_amount": 20000,
        "bedrooms": 2,
    }, headers=h(state["landlord_token"]))
    assert r.status_code == 200, r.text
    state["occupied_unit_id"] = r.json()["id"]

    # create tenant on that unit -> occupies it
    r = requests.post(f"{API}/tenants", json={
        "email": f"TEST_ten_{UNIQ}@demo.com",
        "full_name": "Mkt Tenant",
        "phone": "0733000222",
        "password": "tenpass1",
        "unit_id": state["occupied_unit_id"],
    }, headers=h(state["landlord_token"]))
    assert r.status_code == 200, r.text


# ----- Public listings -----
def test_public_listings_no_auth():
    r = requests.get(f"{API}/public/listings")
    assert r.status_code == 200
    listings = r.json()
    assert isinstance(listings, list)
    ids = [u["id"] for u in listings]
    assert state["vacant_unit_id"] in ids
    assert state["expensive_unit_id"] in ids
    # occupied must not appear
    assert state["occupied_unit_id"] not in ids
    # spot-check schema
    item = next(x for x in listings if x["id"] == state["vacant_unit_id"])
    assert item["property"]["name"].startswith("TEST Riverside")
    assert item["property"]["address"] == "Riverside, Nairobi"
    assert item["landlord_name"] == "Mkt Landlord"
    assert item["rent_amount"] == 15000


def test_public_listings_max_rent_filter():
    r = requests.get(f"{API}/public/listings", params={"max_rent": 30000})
    assert r.status_code == 200
    ids = [u["id"] for u in r.json()]
    assert state["vacant_unit_id"] in ids
    assert state["expensive_unit_id"] not in ids


def test_public_listing_detail_vacant():
    r = requests.get(f"{API}/public/listings/{state['vacant_unit_id']}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == state["vacant_unit_id"]
    assert data["viewing_fee"] == 200
    assert data["property"]["name"].startswith("TEST Riverside")


def test_public_listing_detail_occupied_404():
    r = requests.get(f"{API}/public/listings/{state['occupied_unit_id']}")
    assert r.status_code == 404


# ----- Registration rejection for prospect role -----
def test_register_prospect_role_rejected():
    """Public registration with role='prospect' should be rejected/forbidden.
    Prospects are auto-created via the booking flow only."""
    r = requests.post(f"{API}/auth/register", json={
        "email": f"TEST_pubprospect_{UNIQ}@demo.com",
        "full_name": "Should Fail",
        "phone": "0712345670",
        "role": "prospect",
        "password": "demo123",
    })
    # Either 400/403/422 acceptable; success would be a leak
    assert r.status_code != 200, (
        "Public registration of role=prospect was accepted. "
        "Per spec, prospects must only be created via booking flow."
    )


# ----- Book viewing -----
def test_book_viewing_creates_prospect_and_payment():
    payload = {
        "unit_id": state["vacant_unit_id"],
        "prospect_name": "Test Prospect",
        "prospect_email": PROSPECT_EMAIL,
        "prospect_phone": "0712345601",
        "scheduled_date": "2026-02-15",
        "scheduled_time": "10:00",
        "notes": "Eager to see this unit",
    }
    r = requests.post(f"{API}/public/viewings", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["viewing_id"]
    assert data["payment_id"]
    assert data["prospect_email"] == PROSPECT_EMAIL.lower()
    assert data["prospect_password"], "new prospect should get an auto-generated password"
    assert data["demo_mode"] is True
    state["viewing_id"] = data["viewing_id"]
    state["payment_id"] = data["payment_id"]
    state["prospect_password"] = data["prospect_password"]


def test_viewing_status_before_payment_hides_contact():
    r = requests.get(f"{API}/public/viewings/{state['viewing_id']}")
    assert r.status_code == 200
    data = r.json()
    # Either pending_payment or already scheduled (callback fires after ~4s)
    assert data["status"] in ("pending_payment", "scheduled")
    assert data["viewing_fee"] == 200
    if data["status"] == "pending_payment":
        # contact info must NOT be present
        assert "caretaker_contact" not in data or data.get("caretaker_contact") is None
        assert "landlord_contact" not in data or data.get("landlord_contact") is None


def test_demo_callback_marks_viewing_scheduled():
    # demo callback fires ~4s after stk_push
    deadline = time.time() + 20
    final = None
    while time.time() < deadline:
        r = requests.get(f"{API}/public/viewings/{state['viewing_id']}")
        assert r.status_code == 200
        data = r.json()
        if data["status"] == "scheduled":
            final = data
            break
        time.sleep(1.0)
    assert final, "Viewing never transitioned to 'scheduled' within 20s"
    assert final["payment_status"] == "succeeded"
    assert final["mpesa_receipt"], "M-Pesa receipt missing after success"
    assert final["property_name"]
    assert final["property_address"]
    assert final["unit_number"]
    # caretaker_contact + landlord_contact revealed
    assert final.get("caretaker_contact"), "Caretaker contact must be revealed after payment"
    assert final["caretaker_contact"].get("phone")
    assert final.get("landlord_contact"), "Landlord contact must be revealed after payment"
    assert final["landlord_contact"].get("phone")


# ----- Prospect login -----
def test_prospect_can_login():
    r = requests.post(f"{API}/auth/login", json={
        "email": PROSPECT_EMAIL.lower(),
        "password": state["prospect_password"],
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["user"]["role"] == "prospect"
    state["prospect_token"] = data["access_token"]
    state["prospect_id"] = data["user"]["id"]


def test_prospect_my_viewings():
    r = requests.get(f"{API}/my-viewings", headers=h(state["prospect_token"]))
    assert r.status_code == 200
    vs = r.json()
    assert any(v["id"] == state["viewing_id"] for v in vs)
    v = next(v for v in vs if v["id"] == state["viewing_id"])
    assert v["status"] == "scheduled"
    assert v.get("unit_number")
    assert v.get("property_name")


def test_landlord_sees_viewing_on_their_properties():
    r = requests.get(f"{API}/viewings", headers=h(state["landlord_token"]))
    assert r.status_code == 200
    vs = r.json()
    assert any(v["id"] == state["viewing_id"] for v in vs)


def test_landlord_my_viewings_forbidden():
    r = requests.get(f"{API}/my-viewings", headers=h(state["landlord_token"]))
    assert r.status_code in (401, 403)


def test_prospect_landlord_viewings_forbidden():
    r = requests.get(f"{API}/viewings", headers=h(state["prospect_token"]))
    assert r.status_code in (401, 403)


# ----- Re-booking same email -----
def test_rebook_same_email_reuses_prospect_no_password():
    payload = {
        "unit_id": state["expensive_unit_id"],
        "prospect_name": "Test Prospect",
        "prospect_email": PROSPECT_EMAIL,
        "prospect_phone": "0712345601",
        "scheduled_date": "2026-02-20",
        "scheduled_time": "14:00",
    }
    r = requests.post(f"{API}/public/viewings", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["prospect_password"] in (None, ""), (
        f"Re-booking should NOT return a password (got {data['prospect_password']!r})"
    )
    state["second_viewing_id"] = data["viewing_id"]


# ----- Booking on occupied unit -----
def test_book_on_occupied_unit_returns_404():
    payload = {
        "unit_id": state["occupied_unit_id"],
        "prospect_name": "X",
        "prospect_email": f"TEST_should_not_create_{UNIQ}@demo.com",
        "prospect_phone": "0712345602",
        "scheduled_date": "2026-02-21",
        "scheduled_time": "11:00",
    }
    r = requests.post(f"{API}/public/viewings", json=payload)
    assert r.status_code == 404


def test_book_invalid_phone_returns_400():
    payload = {
        "unit_id": state["vacant_unit_id"],
        "prospect_name": "X",
        "prospect_email": f"TEST_badphone_{UNIQ}@demo.com",
        "prospect_phone": "not-a-phone",
        "scheduled_date": "2026-02-21",
        "scheduled_time": "11:00",
    }
    r = requests.post(f"{API}/public/viewings", json=payload)
    assert r.status_code in (400, 422)


# ----- Prospect dashboard stats -----
def test_prospect_dashboard_stats():
    r = requests.get(f"{API}/dashboard/stats", headers=h(state["prospect_token"]))
    assert r.status_code == 200
    data = r.json()
    # prospect-shaped stats (NOT properties/units/tenants)
    assert "total_viewings" in data
    assert "scheduled" in data
    assert "pending" in data
    assert "completed" in data
    assert "properties" not in data
    assert data["total_viewings"] >= 1


# ----- Booking with an email registered as another role should fail -----
def test_book_with_landlord_email_rejected():
    payload = {
        "unit_id": state["vacant_unit_id"],
        "prospect_name": "Conflict",
        "prospect_email": LANDLORD_EMAIL,  # already a landlord
        "prospect_phone": "0712345699",
        "scheduled_date": "2026-02-22",
        "scheduled_time": "09:00",
    }
    r = requests.post(f"{API}/public/viewings", json=payload)
    assert r.status_code == 400


# ----- Cleanup -----
def test_zz_cleanup():
    # best-effort delete created test data
    from pymongo import MongoClient
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not (mongo_url and db_name):
        # read backend .env
        with open("/app/backend/.env") as f:
            for line in f:
                if line.startswith("MONGO_URL="):
                    mongo_url = line.split("=", 1)[1].strip().strip('"')
                elif line.startswith("DB_NAME="):
                    db_name = line.split("=", 1)[1].strip().strip('"')
    if not (mongo_url and db_name):
        pytest.skip("No mongo config to cleanup")
    client = MongoClient(mongo_url)
    db = client[db_name]
    for coll in ("users", "properties", "units", "bills", "payments", "viewings", "issues"):
        db[coll].delete_many({"$or": [
            {"email": {"$regex": f"TEST_.*_{UNIQ}"}},
            {"name": {"$regex": f"TEST.*{UNIQ}"}},
            {"unit_number": {"$regex": f".*-{UNIQ}"}},
        ]})
    # delete landlord-owned data
    if state.get("landlord_id"):
        for coll in ("properties", "units", "bills", "payments", "viewings", "issues"):
            db[coll].delete_many({"landlord_id": state["landlord_id"]})
        db["users"].delete_many({"landlord_id": state["landlord_id"]})
        db["users"].delete_one({"id": state["landlord_id"]})
    if state.get("prospect_id"):
        db["users"].delete_one({"id": state["prospect_id"]})
    client.close()
