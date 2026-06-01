"""Round 1 fine-tuning tests - NYUMBA FITI
Covers: bills notification labels, property category/sub_type/tenancy_types,
tenant.tenancy_type, lease.agreement_type + PDF title, Security CRUD,
visitor pass scan by security, issue resolved_by_role attribution, public listings.
"""
import io
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

LANDLORD = {"email": "land@demo.com", "password": "demo123"}
CARETAKER = {"email": "ck@demo.com", "password": "care123"}
ADMIN = {"email": "admin@nyumbaos.co.ke", "password": "admin123"}

UNIQ = uuid.uuid4().hex[:6]


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, f"login failed for {creds['email']}: {r.text}"
    return r.json()["access_token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def _extract_pdf_text(path: str) -> str:
    from pypdf import PdfReader
    reader = PdfReader(path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _approve_user(admin_tok, email):
    """Approve a tenant/caretaker/security via oversight endpoint, fallback to direct DB."""
    users = requests.get(f"{API}/admin/users", headers=_h(admin_tok)).json()
    u = next((x for x in users if x["email"].lower() == email.lower()), None)
    if not u:
        return False
    r = requests.post(f"{API}/admin/approvals/user/{u['id']}",
                      json={"approve": True}, headers=_h(admin_tok))
    if r.status_code == 200:
        return True
    # Fallback for roles oversight does not support (e.g. security): direct DB
    try:
        from pymongo import MongoClient
        mongo_url = os.environ.get("MONGO_URL") or "mongodb://localhost:27017"
        db_name = os.environ.get("DB_NAME") or "nyumba_os"
        MongoClient(mongo_url)[db_name]["users"].update_one(
            {"id": u["id"]}, {"$set": {"approval_status": "approved"}}
        )
        return True
    except Exception:
        return False


def _approve_property(admin_tok, prop_id):
    r = requests.post(f"{API}/admin/approvals/property/{prop_id}",
                      json={"approve": True}, headers=_h(admin_tok))
    return r.status_code == 200


@pytest.fixture(scope="session")
def landlord_token():
    return _login(LANDLORD)


@pytest.fixture(scope="session")
def caretaker_token():
    return _login(CARETAKER)


@pytest.fixture(scope="session")
def admin_token():
    return _login(ADMIN)


# ============ PROPERTY: category / sub_type / tenancy_types ============

@pytest.fixture(scope="session")
def created_property(landlord_token):
    """Create a property with category=apartment, sub_type=2br, tenancy=rental,lease."""
    files = {"images": ("", b"", "application/octet-stream")}
    data = {
        "name": f"TEST_R1_{UNIQ}",
        "address": "Kilimani, Nairobi",
        "description": "Round1 test",
        "category": "apartment",
        "sub_type": "2br",
        "tenancy_types": "rental,lease",
    }
    r = requests.post(f"{API}/properties", data=data, headers=_h(landlord_token), timeout=15)
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["category"] == "apartment"
    assert p["sub_type"] == "2br"
    assert set(p["tenancy_types"]) == {"rental", "lease"}
    # Auto-approve so it appears in public listings
    return p


class TestPropertyValidation:
    def test_invalid_category(self, landlord_token):
        data = {"name": "X", "address": "Y", "category": "bedsitter", "sub_type": "1br", "tenancy_types": "rental"}
        r = requests.post(f"{API}/properties", data=data, headers=_h(landlord_token), timeout=10)
        assert r.status_code == 400
        assert "category" in r.text.lower()

    def test_invalid_sub_type(self, landlord_token):
        data = {"name": "X", "address": "Y", "category": "apartment", "sub_type": "mansion", "tenancy_types": "rental"}
        r = requests.post(f"{API}/properties", data=data, headers=_h(landlord_token), timeout=10)
        assert r.status_code == 400
        assert "sub_type" in r.text.lower()

    def test_invalid_tenancy_types(self, landlord_token):
        data = {"name": "X", "address": "Y", "category": "apartment", "tenancy_types": "monthly"}
        r = requests.post(f"{API}/properties", data=data, headers=_h(landlord_token), timeout=10)
        assert r.status_code == 400

    def test_valid_own_compound_no_sub_type(self, landlord_token):
        data = {"name": f"TEST_R1_oc_{UNIQ}", "address": "Karen", "category": "own_compound", "tenancy_types": "lease"}
        r = requests.post(f"{API}/properties", data=data, headers=_h(landlord_token), timeout=10)
        assert r.status_code == 200
        p = r.json()
        assert p["category"] == "own_compound"
        assert p["sub_type"] in (None, "")
        assert p["tenancy_types"] == ["lease"]
        # cleanup
        requests.delete(f"{API}/properties/{p['id']}", headers=_h(landlord_token))

    def test_patch_update_sub_type_and_tenancy(self, landlord_token, created_property):
        pid = created_property["id"]
        r = requests.patch(f"{API}/properties/{pid}", json={"sub_type": "3br", "tenancy_types": ["rental"]},
                           headers=_h(landlord_token), timeout=10)
        assert r.status_code == 200, r.text
        assert r.json()["sub_type"] == "3br"
        assert r.json()["tenancy_types"] == ["rental"]
        # restore for downstream
        requests.patch(f"{API}/properties/{pid}", json={"sub_type": "2br", "tenancy_types": ["rental", "lease"]},
                       headers=_h(landlord_token))

    def test_patch_empty_tenancy_rejected(self, landlord_token, created_property):
        pid = created_property["id"]
        r = requests.patch(f"{API}/properties/{pid}", json={"tenancy_types": []},
                           headers=_h(landlord_token), timeout=10)
        assert r.status_code == 400


# ============ UNIT + TENANT (tenancy_type validation) ============

@pytest.fixture(scope="session")
def created_unit(landlord_token, created_property):
    r = requests.post(f"{API}/units", json={
        "property_id": created_property["id"],
        "unit_number": f"TR1-{UNIQ}",
        "rent_amount": 25000,
        "bedrooms": 2,
        "description": "Round1 unit",
    }, headers=_h(landlord_token), timeout=10)
    assert r.status_code == 200, r.text
    return r.json()


class TestTenantTenancyType:
    def test_tenant_create_with_invalid_tenancy_type(self, landlord_token, created_unit):
        r = requests.post(f"{API}/tenants", json={
            "email": f"TEST_tenbad_{UNIQ}@demo.com",
            "full_name": "Bad",
            "phone": "0712000099",
            "password": "tenant123",
            "unit_id": created_unit["id"],
            "tenancy_type": "monthly",
        }, headers=_h(landlord_token), timeout=10)
        # Pydantic Literal validation -> 422; helpful message route guard -> 400
        assert r.status_code in (400, 422), r.text

    def test_tenant_create_with_valid_tenancy_type(self, landlord_token, created_unit):
        email = f"TEST_ten_{UNIQ}@demo.com".lower()
        r = requests.post(f"{API}/tenants", json={
            "email": email,
            "full_name": "Round1 Tenant",
            "phone": "0712000088",
            "password": "tenant123",
            "unit_id": created_unit["id"],
            "tenancy_type": "rental",
        }, headers=_h(landlord_token), timeout=10)
        assert r.status_code == 200, r.text
        assert r.json()["tenancy_type"] == "rental"
        # verify stored via GET (emails are lowercased server-side)
        lr = requests.get(f"{API}/tenants", headers=_h(landlord_token))
        ten = next((t for t in lr.json() if t["email"].lower() == email), None)
        assert ten and ten["tenancy_type"] == "rental"
        pytest.tenant_email = email
        pytest.tenant_id = r.json()["id"]


# ============ LEASE: agreement_type + PDF title ============

class TestLeaseAgreementType:
    def test_lease_invalid_agreement_type(self, landlord_token, created_property, created_unit):
        # Property supports rental,lease — invalid value should 400/422
        # First we need a tenant — reuse via list
        tenants = requests.get(f"{API}/tenants", headers=_h(landlord_token)).json()
        tenant = next((t for t in tenants if t["unit_id"] == created_unit["id"]), None)
        if not tenant:
            pytest.skip("No tenant for lease test")
        r = requests.post(f"{API}/leases", json={
            "tenant_id": tenant["id"],
            "unit_id": created_unit["id"],
            "agreement_type": "monthly",
            "rent_amount": 25000,
            "deposit_amount": 25000,
            "start_date": "2026-02-01",
            "end_date": "2027-01-31",
            "terms": "TEST",
        }, headers=_h(landlord_token), timeout=15)
        assert r.status_code in (400, 422)

    def test_lease_rental_pdf_title(self, landlord_token, created_unit):
        tenants = requests.get(f"{API}/tenants", headers=_h(landlord_token)).json()
        tenant = next((t for t in tenants if t["unit_id"] == created_unit["id"]), None)
        assert tenant
        r = requests.post(f"{API}/leases", json={
            "tenant_id": tenant["id"],
            "unit_id": created_unit["id"],
            "agreement_type": "rental",
            "rent_amount": 25000,
            "deposit_amount": 25000,
            "start_date": "2026-02-01",
            "end_date": "2027-01-31",
            "terms": "Round1 rental",
        }, headers=_h(landlord_token), timeout=15)
        assert r.status_code == 200, r.text
        lease = r.json()
        assert lease["agreement_type"] == "rental"
        assert lease["pdf_path"]
        # Inspect PDF on disk
        pdf_full = f"/app/backend/{lease['pdf_path']}"
        assert os.path.exists(pdf_full), pdf_full
        text = _extract_pdf_text(pdf_full)
        assert "RENTAL AGREEMENT" in text
        assert "RESIDENTIAL LEASE AGREEMENT" not in text

    def test_lease_lease_pdf_title(self, landlord_token, created_property, landlord_token2=None):
        # Need a fresh unit for second lease (one unit -> one tenant -> one active lease is fine actually).
        # Create another unit + tenant for the lease test.
        unit = requests.post(f"{API}/units", json={
            "property_id": created_property["id"],
            "unit_number": f"TR1-L-{UNIQ}",
            "rent_amount": 30000, "bedrooms": 2, "description": "lease test",
        }, headers=_h(landlord_token)).json()
        tenant = requests.post(f"{API}/tenants", json={
            "email": f"TEST_lten_{UNIQ}@demo.com",
            "full_name": "Lease Tenant", "phone": "0712000077",
            "password": "tenant123", "unit_id": unit["id"], "tenancy_type": "lease",
        }, headers=_h(landlord_token)).json()
        r = requests.post(f"{API}/leases", json={
            "tenant_id": tenant["id"], "unit_id": unit["id"],
            "agreement_type": "lease", "rent_amount": 30000, "deposit_amount": 30000,
            "start_date": "2026-02-01", "end_date": "2027-01-31", "terms": "Round1 lease",
        }, headers=_h(landlord_token), timeout=15)
        assert r.status_code == 200, r.text
        lease = r.json()
        assert lease["agreement_type"] == "lease"
        pdf_full = f"/app/backend/{lease['pdf_path']}"
        text = _extract_pdf_text(pdf_full)
        assert "RESIDENTIAL LEASE AGREEMENT" in text


# ============ SECURITY CRUD ============

class TestSecurityCRUD:
    def test_create_security(self, landlord_token):
        email = f"TEST_sec_{UNIQ}@demo.com".lower()
        r = requests.post(f"{API}/security", json={
            "email": email, "full_name": "Round1 Sec",
            "phone": "0712000066", "password": "sec123",
        }, headers=_h(landlord_token), timeout=10)
        assert r.status_code == 200, r.text
        assert r.json()["role"] == "security"
        pytest.sec_email = email
        pytest.sec_id = r.json()["id"]

    def test_list_security(self, landlord_token):
        r = requests.get(f"{API}/security", headers=_h(landlord_token))
        assert r.status_code == 200
        assert any(s["email"].lower() == pytest.sec_email for s in r.json())

    def test_duplicate_email_400(self, landlord_token):
        r = requests.post(f"{API}/security", json={
            "email": pytest.sec_email, "full_name": "Dup",
            "phone": "0712000065", "password": "sec123",
        }, headers=_h(landlord_token), timeout=10)
        assert r.status_code == 400

    def test_caretaker_cannot_create_security(self, caretaker_token):
        r = requests.post(f"{API}/security", json={
            "email": f"TEST_secNO_{UNIQ}@demo.com", "full_name": "NO",
            "phone": "0712000064", "password": "sec123",
        }, headers=_h(caretaker_token), timeout=10)
        assert r.status_code == 403


# ============ SECURITY: visitor-pass scan + issue resolve ============

class TestSecurityActions:
    def test_security_scan_visitor_pass_and_role_attribution(self, landlord_token, admin_token):
        sec_tok = _login({"email": pytest.sec_email, "password": "sec123"})
        # Approve tenant so they can create a pass
        _approve_user(admin_token, pytest.tenant_email)
        tenant_tok = _login({"email": pytest.tenant_email, "password": "tenant123"})
        pr = requests.post(f"{API}/visitor-passes", json={
            "visitor_name": "Round1 Visitor", "visitor_phone": "0700000000",
            "expected_time": "Today 6pm", "notes": "",
        }, headers=_h(tenant_tok), timeout=10)
        assert pr.status_code == 200, pr.text
        token = pr.json()["token"]
        sr = requests.post(f"{API}/visitor-passes/scan/{token}", headers=_h(sec_tok), timeout=10)
        assert sr.status_code == 200, sr.text
        scanned = sr.json()
        assert scanned["status"] == "used"
        assert scanned.get("used_by_role") == "security"

    def test_security_list_passes(self, landlord_token):
        sec_tok = _login({"email": pytest.sec_email, "password": "sec123"})
        r = requests.get(f"{API}/visitor-passes", headers=_h(sec_tok), timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert len(r.json()) >= 1

    def test_security_resolves_issue(self, landlord_token, admin_token):
        tenant_tok = _login({"email": pytest.tenant_email, "password": "tenant123"})
        ic = requests.post(f"{API}/issues", json={
            "title": f"TEST_R1_iss_{UNIQ}", "description": "test",
            "priority": "medium",
        }, headers=_h(tenant_tok), timeout=10)
        assert ic.status_code == 200, ic.text
        issue_id = ic.json()["id"]
        # Approve security user (uses DB fallback since oversight doesn't support security)
        assert _approve_user(admin_token, pytest.sec_email), "could not approve security"
        sec_tok = _login({"email": pytest.sec_email, "password": "sec123"})
        ur = requests.patch(f"{API}/issues/{issue_id}", json={"status": "resolved"},
                            headers=_h(sec_tok), timeout=10)
        assert ur.status_code == 200, ur.text
        body = ur.json()
        assert body.get("resolved_by_role") == "security"
        assert body.get("resolved_at")
        assert body.get("resolved_by_id")


# ============ BILLS NOTIFICATIONS (label uses bill_type) ============

class TestBillNotificationLabels:
    def test_water_bill_notification_label(self, landlord_token):
        # Need an existing tenant with a unit
        tenants = requests.get(f"{API}/tenants", headers=_h(landlord_token)).json()
        tenant = next((t for t in tenants if t["email"] == pytest.tenant_email), None)
        assert tenant
        # Create water bill
        br = requests.post(f"{API}/bills", json={
            "tenant_id": tenant["id"], "unit_id": tenant["unit_id"],
            "bill_type": "water", "amount": 500, "period": "2026-01", "due_date": "2026-01-15",
        }, headers=_h(landlord_token), timeout=10)
        assert br.status_code == 200, br.text
        bill_id = br.json()["id"]
        # tenant initiates STK push (demo)
        tenant_tok = _login({"email": pytest.tenant_email, "password": "tenant123"})
        pr = requests.post(f"{API}/payments/mpesa/stk-push", json={
            "bill_id": bill_id, "phone_number": "254700000000", "amount": 500,
        }, headers=_h(tenant_tok), timeout=10)
        assert pr.status_code == 200, pr.text
        # Wait for demo callback (~4s)
        time.sleep(7)
        # Tenant notifications
        nr = requests.get(f"{API}/notifications", headers=_h(tenant_tok))
        assert nr.status_code == 200
        titles = [n["title"] for n in nr.json()["items"]]
        assert any("Water bill paid" in t for t in titles), titles
        # Landlord notifications
        ln = requests.get(f"{API}/notifications", headers=_h(landlord_token))
        l_titles = [n["title"] for n in ln.json()["items"]]
        assert any("Water payment received" in t for t in l_titles), l_titles


# ============ PUBLIC LISTINGS surface new fields ============

class TestPublicListings:
    def test_listings_have_sub_type_and_tenancy(self, admin_token, landlord_token, created_property, created_unit):
        # Approve property via oversight endpoint
        _approve_property(admin_token, created_property["id"])
        # Need a vacant unit — created_unit may now be occupied by tenant fixture
        prop = requests.post(f"{API}/units", json={
            "property_id": created_property["id"],
            "unit_number": f"TR1-PUB-{UNIQ}", "rent_amount": 28000,
            "bedrooms": 2, "description": "public",
        }, headers=_h(landlord_token)).json()
        time.sleep(1)
        r = requests.get(f"{API}/public/listings", timeout=15)
        assert r.status_code == 200
        listings = r.json()
        match = next((l for l in listings if l["id"] == prop["id"]), None)
        assert match, f"new listing not in public list (found {len(listings)})"
        # sub_type at top level
        assert "sub_type" in match
        # tenancy_types in property block
        assert "tenancy_types" in match["property"]
        assert match["property"]["sub_type"] == "2br"


# ============ MIGRATION ============

class TestMigration:
    def test_existing_properties_have_new_fields(self, landlord_token):
        r = requests.get(f"{API}/properties", headers=_h(landlord_token))
        assert r.status_code == 200
        for p in r.json():
            assert "category" in p
            assert p["category"] in ("apartment", "own_compound")
            assert "tenancy_types" in p
            assert isinstance(p["tenancy_types"], list)
            assert len(p["tenancy_types"]) >= 1
