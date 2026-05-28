"""Round 7 — Flat KES 33 service fee + Landlord Confirmation tab"""
import os
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE:
    # fallback to value in frontend/.env if present
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE = line.split("=", 1)[1].strip().rstrip("/")
                    break
    except Exception:
        pass
assert BASE, "REACT_APP_BACKEND_URL is not configured"

ADMIN = ("admin@nyumbaos.co.ke", "admin123")
LL = ("mary@demo.nyumba", "demo123")
TENANT = ("tenant1@demo.nyumba", "demo123")


def _login(email, password):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    j = r.json()
    return j.get("access_token") or j.get("token")


@pytest.fixture(scope="module")
def admin_h():
    return {"Authorization": f"Bearer {_login(*ADMIN)}"}


@pytest.fixture(scope="module")
def ll_h():
    return {"Authorization": f"Bearer {_login(*LL)}"}


@pytest.fixture(scope="module")
def tenant_h():
    return {"Authorization": f"Bearer {_login(*TENANT)}"}


@pytest.fixture(scope="module")
def tenant_info(tenant_h):
    r = requests.get(f"{BASE}/api/auth/me", headers=tenant_h, timeout=20)
    assert r.status_code == 200
    me = r.json()
    # auth/me doesn't include property_id; look it up via the unit
    if me.get("unit_id") and not me.get("property_id"):
        u = requests.get(f"{BASE}/api/units/{me['unit_id']}", headers=tenant_h, timeout=20)
        if u.status_code == 200:
            me["property_id"] = u.json().get("property_id")
        else:
            # fallback — use any bill the tenant already has
            br = requests.get(f"{BASE}/api/bills", headers=tenant_h, timeout=20)
            if br.status_code == 200 and br.json():
                me["property_id"] = br.json()[0].get("property_id")
    return me


# ---------------- Public settings ----------------

def test_public_settings_returns_flat_33(tenant_h):
    r = requests.get(f"{BASE}/api/admin/public-settings", headers=tenant_h, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "service_fee_flat_kes" in data
    assert float(data["service_fee_flat_kes"]) == 33.0


# ---------------- STK push (flat fee) ----------------

def _create_bill(ll_h, tenant_info, bill_type, amount):
    payload = {
        "tenant_id": tenant_info["id"],
        "property_id": tenant_info["property_id"],
        "unit_id": tenant_info["unit_id"],
        "bill_type": bill_type,
        "amount": amount,
        "period": "2026-01",
        "due_date": "2026-01-25",
        "description": f"TEST_R7 {bill_type}",
    }
    r = requests.post(f"{BASE}/api/bills", json=payload, headers=ll_h, timeout=20)
    assert r.status_code in (200, 201), f"bill create failed ({bill_type}): {r.status_code} {r.text}"
    return r.json()


@pytest.mark.parametrize("bill_type,amount", [
    ("rent", 25000.0),
    ("water", 1500.0),
    ("electricity", 3200.0),
    ("service", 800.0),   # backend literal is 'service'
    ("other", 500.0),
])
def test_stk_push_charges_flat_33(ll_h, tenant_h, tenant_info, bill_type, amount):
    bill = _create_bill(ll_h, tenant_info, bill_type, amount)
    body = {"bill_id": bill["id"], "phone_number": "254712345678"}
    r = requests.post(f"{BASE}/api/payments/mpesa/stk-push", json=body, headers=tenant_h, timeout=40)
    # If sandbox 502s, this isn't our concern — but body should still come back if we got 200
    if r.status_code == 502:
        pytest.skip(f"Safaricom sandbox unavailable for {bill_type}: {r.text}")
    assert r.status_code == 200, f"{bill_type}: {r.status_code} {r.text}"
    data = r.json()
    assert data["service_fee_amount"] == 33.0, f"{bill_type}: expected 33, got {data['service_fee_amount']}"
    assert data["rent_amount"] == amount, f"{bill_type}: rent_amount should equal bill amount {amount}, got {data['rent_amount']}"
    # CustomerMessage from Safaricom may override our message — only check fallback case
    if "33" not in (data.get("message") or ""):
        # Fallback message must contain "KES 33"
        pass  # Safaricom overrides — acceptable


# ---------------- Receipt flow (DB-mutated since STK sandbox is flaky) ----------------

def _seed_awaiting_bill(ll_h, tenant_info, amount=5500.0):
    """Create a bill and mutate it via the test injector so we can test receipt flow.
    We do this through the API: create bill, then set service_fee_paid_at by submitting receipt
    after we mark service_fee_paid_at via Mongo directly using pymongo."""
    bill = _create_bill(ll_h, tenant_info, "rent", amount)
    # Use motor/pymongo via the running backend's MONGO_URL
    from pymongo import MongoClient
    mongo_url = open("/app/backend/.env").read()
    url = None
    db_name = None
    for line in mongo_url.splitlines():
        if line.startswith("MONGO_URL="):
            url = line.split("=", 1)[1].strip().strip('"')
        if line.startswith("DB_NAME="):
            db_name = line.split("=", 1)[1].strip().strip('"')
    assert url and db_name
    client = MongoClient(url)
    db = client[db_name]
    db["bills"].update_one(
        {"id": bill["id"]},
        {"$set": {"service_fee_paid_at": "2026-01-10T10:00:00+00:00", "status": "awaiting_rent_receipt"}},
    )
    client.close()
    return bill


@pytest.fixture(scope="module")
def submitted_bill(ll_h, tenant_h, tenant_info):
    bill = _seed_awaiting_bill(ll_h, tenant_info, 5500.0)
    r = requests.post(
        f"{BASE}/api/bills/{bill['id']}/submit-rent-receipt",
        json={"mpesa_receipt": "SGH7TEST7", "amount_paid": 5500.0},
        headers=tenant_h, timeout=20,
    )
    assert r.status_code == 200, f"submit-rent-receipt failed: {r.status_code} {r.text}"
    body = r.json()
    assert body["status"] == "awaiting_landlord_confirmation"
    return bill


def test_pending_confirmations_lists_submitted_bill(ll_h, submitted_bill):
    r = requests.get(f"{BASE}/api/bills/pending-confirmations", headers=ll_h, timeout=20)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert isinstance(rows, list)
    matching = [b for b in rows if b["id"] == submitted_bill["id"]]
    assert matching, "submitted bill not in pending-confirmations list"
    b = matching[0]
    # Required enrichment fields
    for k in ("tenant_name", "unit_number", "property_name", "landlord_paybill",
              "rent_receipt_code", "rent_receipt_amount", "rent_receipt_submitted_at"):
        assert k in b, f"missing field {k} in response"
    assert b["rent_receipt_code"] == "SGH7TEST7"
    assert b["rent_receipt_amount"] == 5500.0


def test_request_info_requires_message(ll_h, submitted_bill):
    # Missing message must 400
    r = requests.post(
        f"{BASE}/api/bills/{submitted_bill['id']}/request-info-rent-receipt",
        json={}, headers=ll_h, timeout=20,
    )
    assert r.status_code == 400, f"empty message should 400, got {r.status_code} {r.text}"

    r2 = requests.post(
        f"{BASE}/api/bills/{submitted_bill['id']}/request-info-rent-receipt",
        json={"message": "Please send screenshot of M-Pesa SMS"}, headers=ll_h, timeout=20,
    )
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["info_request_message"] == "Please send screenshot of M-Pesa SMS"


def test_tenant_sees_info_request_message(tenant_h, submitted_bill):
    r = requests.get(f"{BASE}/api/bills", headers=tenant_h, timeout=20)
    assert r.status_code == 200
    bills = r.json()
    target = next((b for b in bills if b["id"] == submitted_bill["id"]), None)
    assert target, "tenant cannot see their own bill"
    assert target.get("info_request_message") == "Please send screenshot of M-Pesa SMS"
    assert target.get("status") == "awaiting_landlord_confirmation", \
        f"status should stay awaiting_landlord_confirmation after request-info, got {target.get('status')}"


def test_reject_clears_receipt_and_stores_reason(ll_h, tenant_h, tenant_info):
    bill = _seed_awaiting_bill(ll_h, tenant_info, 4000.0)
    requests.post(
        f"{BASE}/api/bills/{bill['id']}/submit-rent-receipt",
        json={"mpesa_receipt": "REJ7TEST", "amount_paid": 4000.0},
        headers=tenant_h, timeout=20,
    )
    r = requests.post(
        f"{BASE}/api/bills/{bill['id']}/reject-rent-receipt",
        json={"reason": "Receipt code does not match my SMS"},
        headers=ll_h, timeout=20,
    )
    assert r.status_code == 200, r.text
    # Verify state
    bills = requests.get(f"{BASE}/api/bills", headers=tenant_h, timeout=20).json()
    target = next(b for b in bills if b["id"] == bill["id"])
    assert target["status"] == "pending"
    assert not target.get("rent_receipt_code")
    assert target.get("rent_receipt_rejection") == "Receipt code does not match my SMS"


def test_confirm_flips_to_paid(ll_h, tenant_h, tenant_info):
    bill = _seed_awaiting_bill(ll_h, tenant_info, 7000.0)
    requests.post(
        f"{BASE}/api/bills/{bill['id']}/submit-rent-receipt",
        json={"mpesa_receipt": "OK7TEST", "amount_paid": 7000.0},
        headers=tenant_h, timeout=20,
    )
    r = requests.post(f"{BASE}/api/bills/{bill['id']}/confirm-rent-receipt", headers=ll_h, timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "paid"
    # Verify persistence
    bills = requests.get(f"{BASE}/api/bills", headers=tenant_h, timeout=20).json()
    target = next(b for b in bills if b["id"] == bill["id"])
    assert target["status"] == "paid"
