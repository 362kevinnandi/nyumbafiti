"""End-to-end backend tests for Nairobi Rental Management."""
import os
import time
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # try frontend .env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")
API = f"{BASE_URL}/api"

UNIQ = uuid.uuid4().hex[:8]
LANDLORD_EMAIL = f"TEST_landlord_{UNIQ}@demo.com"
LANDLORD_PASS = "demo123"
TENANT_EMAIL = f"TEST_tenant_{UNIQ}@demo.com"
TENANT_PASS = "tenpass1"
CARETAKER_EMAIL = f"TEST_caretaker_{UNIQ}@demo.com"
CARETAKER_PASS = "ctpass1"

state = {}


def h(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ============ AUTH ============
def test_root():
    r = requests.get(f"{API}/")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_register_landlord():
    r = requests.post(f"{API}/auth/register", json={
        "email": LANDLORD_EMAIL,
        "full_name": "Test Landlord",
        "phone": "0712345678",
        "role": "landlord",
        "password": LANDLORD_PASS,
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert "access_token" in data
    assert data["user"]["role"] == "landlord"
    assert data["user"]["email"] == LANDLORD_EMAIL.lower()
    assert "_id" not in data["user"]
    state["landlord_token"] = data["access_token"]
    state["landlord_id"] = data["user"]["id"]


def test_register_tenant_rejected():
    r = requests.post(f"{API}/auth/register", json={
        "email": f"TEST_rej_{UNIQ}@x.com",
        "full_name": "X", "phone": "0712345678",
        "role": "tenant", "password": "pass123",
    })
    assert r.status_code == 400
    assert "landlord" in r.json()["detail"].lower()


def test_register_caretaker_rejected():
    r = requests.post(f"{API}/auth/register", json={
        "email": f"TEST_rej2_{UNIQ}@x.com",
        "full_name": "X", "phone": "0712345678",
        "role": "caretaker", "password": "pass123",
    })
    assert r.status_code == 400


def test_login_landlord():
    r = requests.post(f"{API}/auth/login", json={
        "email": LANDLORD_EMAIL, "password": LANDLORD_PASS,
    })
    assert r.status_code == 200
    state["landlord_token"] = r.json()["access_token"]


def test_login_invalid():
    r = requests.post(f"{API}/auth/login", json={
        "email": LANDLORD_EMAIL, "password": "wrong",
    })
    assert r.status_code == 401


def test_me():
    r = requests.get(f"{API}/auth/me", headers=h(state["landlord_token"]))
    assert r.status_code == 200
    assert r.json()["role"] == "landlord"
    assert "_id" not in r.json()


# ============ PROPERTIES / UNITS ============
def test_create_property():
    r = requests.post(f"{API}/properties", headers=h(state["landlord_token"]), json={
        "name": "TEST Sunrise Apts", "address": "Westlands, Nairobi",
        "description": "Test property", "image_url": "",
    })
    assert r.status_code == 200, r.text
    state["property_id"] = r.json()["id"]
    assert r.json()["landlord_id"] == state["landlord_id"]


def test_list_properties():
    r = requests.get(f"{API}/properties", headers=h(state["landlord_token"]))
    assert r.status_code == 200
    assert any(p["id"] == state["property_id"] for p in r.json())


def test_create_unit():
    r = requests.post(f"{API}/units", headers=h(state["landlord_token"]), json={
        "property_id": state["property_id"], "unit_number": "A1",
        "rent_amount": 15000, "bedrooms": 1, "description": "Bedsitter",
    })
    assert r.status_code == 200, r.text
    state["unit_id"] = r.json()["id"]
    assert r.json()["occupied"] is False


# ============ TENANT / CARETAKER ============
def test_create_tenant_assigns_unit():
    r = requests.post(f"{API}/tenants", headers=h(state["landlord_token"]), json={
        "email": TENANT_EMAIL, "full_name": "Test Tenant",
        "phone": "0723456789", "password": TENANT_PASS,
        "unit_id": state["unit_id"],
    })
    assert r.status_code == 200, r.text
    state["tenant_id"] = r.json()["id"]
    # verify unit now occupied
    units = requests.get(f"{API}/units", headers=h(state["landlord_token"])).json()
    u = next(u for u in units if u["id"] == state["unit_id"])
    assert u["occupied"] is True
    assert u["tenant_id"] == state["tenant_id"]


def test_tenant_login():
    r = requests.post(f"{API}/auth/login", json={
        "email": TENANT_EMAIL, "password": TENANT_PASS,
    })
    assert r.status_code == 200, r.text
    state["tenant_token"] = r.json()["access_token"]
    assert r.json()["user"]["role"] == "tenant"
    assert r.json()["user"]["unit_id"] == state["unit_id"]


def test_create_caretaker():
    r = requests.post(f"{API}/caretakers", headers=h(state["landlord_token"]), json={
        "email": CARETAKER_EMAIL, "full_name": "Test Caretaker",
        "phone": "0734567890", "password": CARETAKER_PASS,
    })
    assert r.status_code == 200, r.text
    state["caretaker_id"] = r.json()["id"]


def test_caretaker_login():
    r = requests.post(f"{API}/auth/login", json={
        "email": CARETAKER_EMAIL, "password": CARETAKER_PASS,
    })
    assert r.status_code == 200
    state["caretaker_token"] = r.json()["access_token"]
    assert r.json()["user"]["role"] == "caretaker"


# ============ ADMIN APPROVES TEST ENTITIES (so payments/issues can flow) ============
def test_admin_approves_test_entities():
    r = requests.post(f"{API}/auth/login", json={
        "email": "admin@nyumbaos.co.ke", "password": "admin123",
    })
    assert r.status_code == 200, r.text
    state["admin_token"] = r.json()["access_token"]
    # approve property
    r = requests.post(
        f"{API}/admin/approvals/property/{state['property_id']}",
        json={"approve": True}, headers=h(state["admin_token"]),
    )
    assert r.status_code == 200, r.text
    # approve tenant
    r = requests.post(
        f"{API}/admin/approvals/user/{state['tenant_id']}",
        json={"approve": True}, headers=h(state["admin_token"]),
    )
    assert r.status_code == 200, r.text
    # approve caretaker
    r = requests.post(
        f"{API}/admin/approvals/user/{state['caretaker_id']}",
        json={"approve": True}, headers=h(state["admin_token"]),
    )
    assert r.status_code == 200, r.text


# ============ BILLS ============
def test_create_manual_bill():
    r = requests.post(f"{API}/bills", headers=h(state["landlord_token"]), json={
        "tenant_id": state["tenant_id"], "unit_id": state["unit_id"],
        "bill_type": "water", "amount": 500,
        "period": "2026-01", "due_date": "2026-02-05T00:00:00+00:00",
        "description": "Test water bill",
    })
    assert r.status_code == 200, r.text
    state["water_bill_id"] = r.json()["id"]
    assert r.json()["amount"] == 500
    assert r.json()["status"] == "pending"


def test_generate_monthly_rent():
    r = requests.post(f"{API}/bills/generate-monthly", headers=h(state["landlord_token"]))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["created"] >= 1


def test_generate_monthly_idempotent():
    r = requests.post(f"{API}/bills/generate-monthly", headers=h(state["landlord_token"]))
    assert r.status_code == 200
    assert r.json()["created"] == 0  # all already exist
    assert r.json()["skipped"] >= 1


def test_tenant_lists_own_bills():
    r = requests.get(f"{API}/bills", headers=h(state["tenant_token"]))
    assert r.status_code == 200
    bills = r.json()
    assert len(bills) >= 2  # water + rent
    assert all(b["tenant_id"] == state["tenant_id"] for b in bills)
    # find rent bill
    rent = next((b for b in bills if b["bill_type"] == "rent"), None)
    assert rent is not None
    state["rent_bill_id"] = rent["id"]
    state["rent_amount"] = rent["amount"]


# ============ PAYMENTS / M-Pesa ============
def test_mpesa_stk_push_demo_mode():
    r = requests.post(f"{API}/payments/mpesa/stk-push", headers=h(state["tenant_token"]), json={
        "bill_id": state["rent_bill_id"],
        "phone_number": "0712345678",  # test phone normalization
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["demo_mode"] is True
    assert data["status"] == "pending"
    assert "payment_id" in data
    state["payment_id"] = data["payment_id"]


def test_payment_auto_callback_succeeds():
    # wait for auto-callback (~4-5s)
    success = False
    for _ in range(12):
        time.sleep(1)
        r = requests.get(f"{API}/payments/{state['payment_id']}",
                         headers=h(state["tenant_token"]))
        assert r.status_code == 200
        if r.json()["status"] == "succeeded":
            success = True
            break
    assert success, f"Payment did not succeed in time. Last: {r.json()}"
    assert r.json()["mpesa_receipt"].startswith(("DEMO", "ws_"))


def test_bill_updated_after_payment():
    r = requests.get(f"{API}/bills", headers=h(state["tenant_token"]))
    rent = next(b for b in r.json() if b["id"] == state["rent_bill_id"])
    assert rent["amount_paid"] >= state["rent_amount"], rent
    assert rent["status"] == "paid"


def test_phone_normalization_invalid():
    r = requests.post(f"{API}/payments/mpesa/stk-push", headers=h(state["tenant_token"]), json={
        "bill_id": state["water_bill_id"], "phone_number": "12345",
    })
    assert r.status_code == 400


# ============ ISSUES ============
def test_tenant_creates_issue():
    r = requests.post(f"{API}/issues", headers=h(state["tenant_token"]), json={
        "title": "TEST Leaky tap", "description": "Tap is leaking", "priority": "high",
    })
    assert r.status_code == 200, r.text
    state["issue_id"] = r.json()["id"]
    assert r.json()["status"] == "open"


def test_landlord_lists_issues_with_enrichment():
    r = requests.get(f"{API}/issues", headers=h(state["landlord_token"]))
    assert r.status_code == 200
    issue = next(i for i in r.json() if i["id"] == state["issue_id"])
    assert issue.get("tenant_name") == "Test Tenant"
    assert issue.get("unit_number") == "A1"


def test_landlord_assigns_caretaker():
    r = requests.patch(f"{API}/issues/{state['issue_id']}",
                       headers=h(state["landlord_token"]),
                       json={"assigned_to": state["caretaker_id"]})
    assert r.status_code == 200, r.text
    assert r.json()["assigned_to"] == state["caretaker_id"]


def test_caretaker_updates_status():
    r = requests.patch(f"{API}/issues/{state['issue_id']}",
                       headers=h(state["caretaker_token"]),
                       json={"status": "in_progress"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "in_progress"


def test_tenant_cannot_update_issue():
    r = requests.patch(f"{API}/issues/{state['issue_id']}",
                       headers=h(state["tenant_token"]),
                       json={"status": "resolved"})
    assert r.status_code == 403


def test_issue_messages_thread():
    # tenant posts
    r = requests.post(f"{API}/issues/{state['issue_id']}/messages",
                      headers=h(state["tenant_token"]), json={"body": "Please help"})
    assert r.status_code == 200
    # landlord posts
    r = requests.post(f"{API}/issues/{state['issue_id']}/messages",
                      headers=h(state["landlord_token"]),
                      json={"body": "On it"})
    assert r.status_code == 200
    # caretaker posts
    r = requests.post(f"{API}/issues/{state['issue_id']}/messages",
                      headers=h(state["caretaker_token"]),
                      json={"body": "Will fix today"})
    assert r.status_code == 200
    # all read
    r = requests.get(f"{API}/issues/{state['issue_id']}/messages",
                     headers=h(state["tenant_token"]))
    assert r.status_code == 200
    msgs = r.json()
    assert len(msgs) == 3
    roles = {m["author_role"] for m in msgs}
    assert roles == {"tenant", "landlord", "caretaker"}


def test_caretaker_resolves_issue():
    r = requests.patch(f"{API}/issues/{state['issue_id']}",
                       headers=h(state["caretaker_token"]),
                       json={"status": "resolved"})
    assert r.status_code == 200
    assert r.json()["status"] == "resolved"


# ============ ACCESS CONTROL ============
def test_another_tenant_cannot_see_bills():
    # create 2nd landlord+tenant
    r = requests.post(f"{API}/auth/register", json={
        "email": f"TEST_l2_{UNIQ}@x.com", "full_name": "L2", "phone": "0700000000",
        "role": "landlord", "password": "pass123",
    })
    assert r.status_code == 200
    l2_tok = r.json()["access_token"]
    # property + unit
    p = requests.post(f"{API}/properties", headers=h(l2_tok),
                      json={"name": "P2", "address": "X"}).json()
    u = requests.post(f"{API}/units", headers=h(l2_tok), json={
        "property_id": p["id"], "unit_number": "B1", "rent_amount": 10000,
    }).json()
    t2 = requests.post(f"{API}/tenants", headers=h(l2_tok), json={
        "email": f"TEST_t2_{UNIQ}@x.com", "full_name": "T2", "phone": "0700000001",
        "password": "pass123", "unit_id": u["id"],
    }).json()
    t2_login = requests.post(f"{API}/auth/login", json={
        "email": f"TEST_t2_{UNIQ}@x.com", "password": "pass123",
    }).json()
    t2_tok = t2_login["access_token"]
    # t2 should see no bills (none created yet)
    r = requests.get(f"{API}/bills", headers=h(t2_tok))
    assert r.status_code == 200
    bill_ids = [b["id"] for b in r.json()]
    assert state["rent_bill_id"] not in bill_ids
    assert state["water_bill_id"] not in bill_ids


# ============ DASHBOARD ============
def test_dashboard_landlord():
    r = requests.get(f"{API}/dashboard/stats", headers=h(state["landlord_token"]))
    assert r.status_code == 200
    d = r.json()
    assert d["properties"] >= 1
    assert d["units"] >= 1
    assert d["tenants"] >= 1
    assert d["total_collected"] >= state["rent_amount"]


def test_dashboard_tenant():
    r = requests.get(f"{API}/dashboard/stats", headers=h(state["tenant_token"]))
    assert r.status_code == 200
    d = r.json()
    assert "arrears" in d
    assert "pending_bills" in d
    assert d["paid_bills"] >= 1


def test_dashboard_caretaker():
    r = requests.get(f"{API}/dashboard/stats", headers=h(state["caretaker_token"]))
    assert r.status_code == 200
    d = r.json()
    assert "assigned_open" in d
    assert "resolved" in d


# ============ CLEANUP ============
def test_zz_cleanup():
    """Best effort cleanup."""
    try:
        requests.delete(f"{API}/bills/{state['water_bill_id']}", headers=h(state["landlord_token"]))
        requests.delete(f"{API}/bills/{state['rent_bill_id']}", headers=h(state["landlord_token"]))
        requests.delete(f"{API}/tenants/{state['tenant_id']}", headers=h(state["landlord_token"]))
        requests.delete(f"{API}/caretakers/{state['caretaker_id']}", headers=h(state["landlord_token"]))
        requests.delete(f"{API}/units/{state['unit_id']}", headers=h(state["landlord_token"]))
        requests.delete(f"{API}/properties/{state['property_id']}", headers=h(state["landlord_token"]))
    except Exception as exc:
        print(f"cleanup error: {exc}")
