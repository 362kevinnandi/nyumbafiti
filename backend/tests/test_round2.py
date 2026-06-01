"""Round 2 fine-tuning tests - Yard Sale monetization (Nyumba FITI).

Covers:
- POST /api/yard-sale/listings starts scope='property', contact_unlocked=false,
  and seller_phone/seller_email masked for non-owner viewers.
- GET masking + scope visibility (in-network YES masked, admin YES unmasked,
  cross-landlord NO, seller YES unmasked).
- POST /unlock-contact -> KES 35 STK, after ~5s callback contact_unlocked=true.
- POST /broadcast -> KES 50 STK, after ~5s callback scope='all', visible to
  cross-landlord tenant.
- POST /feature -> KES 100 STK still works.
- Permission: another seller's listing -> 403 on monetization endpoints.
- Migration: legacy yard_sale docs get scope='property' + contact_unlocked=false.
"""
import io
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

LANDLORD_A = {"email": "land@demo.com", "password": "demo123"}
ADMIN = {"email": "admin@nyumbaos.co.ke", "password": "admin123"}

UNIQ = uuid.uuid4().hex[:6]


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, f"login failed for {creds['email']}: {r.text}"
    return r.json()["access_token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def _approve_user_db(email):
    """Approve a user directly via Mongo (oversight only supports tenant/caretaker)."""
    from pymongo import MongoClient
    mongo_url = os.environ.get("MONGO_URL") or "mongodb://localhost:27017"
    db_name = os.environ.get("DB_NAME") or "nyumba_os"
    res = MongoClient(mongo_url)[db_name]["users"].update_one(
        {"email": email.lower()}, {"$set": {"approval_status": "approved", "suspended": False}}
    )
    return res.matched_count > 0


def _approve_user_via_admin(admin_tok, email):
    users = requests.get(f"{API}/admin/users", headers=_h(admin_tok)).json()
    u = next((x for x in users if x["email"].lower() == email.lower()), None)
    if not u:
        return False
    r = requests.post(
        f"{API}/admin/approvals/user/{u['id']}",
        json={"approve": True},
        headers=_h(admin_tok),
        timeout=10,
    )
    if r.status_code == 200:
        return True
    return _approve_user_db(email)


# ============ FIXTURES: tokens, tenants, listing ============

@pytest.fixture(scope="session")
def admin_tok():
    return _login(ADMIN)


@pytest.fixture(scope="session")
def landlord_a_tok():
    return _login(LANDLORD_A)


@pytest.fixture(scope="session")
def tenant_a(landlord_a_tok, admin_tok):
    """A tenant under landlord A (in same property)."""
    # Pick or create a property + vacant unit
    props = requests.get(f"{API}/properties", headers=_h(landlord_a_tok)).json()
    prop = props[0] if props else None
    if not prop:
        # create one
        data = {
            "name": f"TEST_R2_{UNIQ}",
            "address": "Kilimani",
            "category": "apartment",
            "sub_type": "2br",
            "tenancy_types": "rental",
        }
        r = requests.post(f"{API}/properties", data=data, headers=_h(landlord_a_tok))
        prop = r.json()
    # create a unit
    unit = requests.post(f"{API}/units", json={
        "property_id": prop["id"],
        "unit_number": f"R2-{UNIQ}",
        "rent_amount": 25000,
        "bedrooms": 1,
        "description": "r2",
    }, headers=_h(landlord_a_tok)).json()
    email = f"test_r2_tenA_{UNIQ}@demo.com".lower()
    r = requests.post(f"{API}/tenants", json={
        "email": email, "full_name": "TenantA R2", "phone": "0712000111",
        "password": "tenant123", "unit_id": unit["id"], "tenancy_type": "rental",
    }, headers=_h(landlord_a_tok), timeout=10)
    assert r.status_code == 200, r.text
    _approve_user_via_admin(_login(ADMIN), email)
    tok = _login({"email": email, "password": "tenant123"})
    return {"email": email, "token": tok, "id": r.json()["id"], "landlord_id": prop["landlord_id"]}


@pytest.fixture(scope="session")
def landlord_b(admin_tok):
    """Brand new landlord (different network) for cross-network isolation."""
    email = f"test_r2_landB_{UNIQ}@demo.com".lower()
    r = requests.post(f"{API}/auth/register", json={
        "email": email, "full_name": "LandB R2", "phone": "0712000222",
        "password": "land123", "role": "landlord",
    }, timeout=10)
    assert r.status_code in (200, 201), r.text
    _approve_user_via_admin(admin_tok, email)
    tok = _login({"email": email, "password": "land123"})
    return {"email": email, "token": tok}


@pytest.fixture(scope="session")
def tenant_b(landlord_b, admin_tok):
    """Tenant under landlord B (different network)."""
    # Landlord B needs a property + unit
    data = {
        "name": f"TEST_R2B_{UNIQ}", "address": "Westlands",
        "category": "apartment", "sub_type": "1br", "tenancy_types": "rental",
    }
    prop = requests.post(
        f"{API}/properties", data=data, headers=_h(landlord_b["token"]), timeout=10
    ).json()
    unit = requests.post(f"{API}/units", json={
        "property_id": prop["id"], "unit_number": f"B-{UNIQ}",
        "rent_amount": 20000, "bedrooms": 1, "description": "b",
    }, headers=_h(landlord_b["token"])).json()
    email = f"test_r2_tenB_{UNIQ}@demo.com".lower()
    r = requests.post(f"{API}/tenants", json={
        "email": email, "full_name": "TenantB R2", "phone": "0712000333",
        "password": "tenant123", "unit_id": unit["id"], "tenancy_type": "rental",
    }, headers=_h(landlord_b["token"]), timeout=10)
    assert r.status_code == 200, r.text
    _approve_user_via_admin(admin_tok, email)
    tok = _login({"email": email, "password": "tenant123"})
    return {"email": email, "token": tok, "id": r.json()["id"]}


@pytest.fixture(scope="session")
def listing_a(tenant_a):
    """Tenant A creates a yard sale listing (default scope=property)."""
    files = [("images", ("", b"", "application/octet-stream"))]
    data = {"title": f"TEST_R2_listing_{UNIQ}", "description": "round2", "price": 500, "category": "other"}
    r = requests.post(f"{API}/yard-sale/listings", data=data, files=files, headers=_h(tenant_a["token"]), timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


# ============ TESTS ============

class TestCreateListingDefaults:
    def test_new_listing_defaults(self, listing_a, tenant_a):
        assert listing_a["scope"] == "property"
        assert listing_a["contact_unlocked"] is False
        # Owner sees own contact unmasked
        assert listing_a["seller_phone"]  # owner viewing -> unmasked
        # Listing belongs to tenant A
        assert listing_a["seller_id"] == tenant_a["id"]

    def test_invalid_scope_rejected(self, tenant_a):
        data = {"title": "X", "description": "x", "price": 10, "category": "other", "scope": "moon"}
        r = requests.post(
            f"{API}/yard-sale/listings", data=data, headers=_h(tenant_a["token"]), timeout=10
        )
        assert r.status_code == 400


class TestMasking:
    def test_admin_sees_phone(self, admin_tok, listing_a):
        r = requests.get(f"{API}/yard-sale/listings/{listing_a['id']}", headers=_h(admin_tok))
        assert r.status_code == 200, r.text
        assert r.json()["seller_phone"]  # admin sees unmasked

    def test_owner_sees_phone(self, tenant_a, listing_a):
        r = requests.get(f"{API}/yard-sale/listings/{listing_a['id']}", headers=_h(tenant_a["token"]))
        assert r.status_code == 200
        assert r.json()["seller_phone"]

    def test_landlord_a_sees_listing_masked(self, landlord_a_tok, listing_a):
        # Landlord A is "in network" for tenant A
        r = requests.get(f"{API}/yard-sale/listings/{listing_a['id']}", headers=_h(landlord_a_tok))
        assert r.status_code == 200, r.text
        body = r.json()
        # contact_unlocked=False, viewer is not owner/admin => masked
        assert body["seller_phone"] == ""
        assert body["seller_email"] == ""

    def test_cross_landlord_tenant_cannot_see(self, tenant_b, listing_a):
        # Property-scoped, tenant B is different network -> 403
        r = requests.get(f"{API}/yard-sale/listings/{listing_a['id']}", headers=_h(tenant_b["token"]))
        assert r.status_code == 403

    def test_cross_landlord_tenant_not_in_list(self, tenant_b, listing_a):
        r = requests.get(f"{API}/yard-sale/listings", headers=_h(tenant_b["token"]))
        assert r.status_code == 200
        ids = [it["id"] for it in r.json()]
        assert listing_a["id"] not in ids


class TestUnlockContact:
    def test_other_user_cannot_unlock(self, tenant_b, listing_a):
        r = requests.post(
            f"{API}/yard-sale/listings/{listing_a['id']}/unlock-contact",
            data={"phone_number": "0712345678"},
            headers=_h(tenant_b["token"]),
            timeout=10,
        )
        assert r.status_code == 403

    def test_unlock_flow(self, tenant_a, landlord_a_tok, listing_a):
        r = requests.post(
            f"{API}/yard-sale/listings/{listing_a['id']}/unlock-contact",
            data={"phone_number": "0712345678"},
            headers=_h(tenant_a["token"]),
            timeout=15,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["amount"] == 35
        assert body["payment_id"]
        assert "demo_mode" in body
        # Wait for demo callback
        time.sleep(7)
        # Re-fetch as in-network landlord viewer; phone should now appear (unlocked globally)
        r2 = requests.get(
            f"{API}/yard-sale/listings/{listing_a['id']}", headers=_h(landlord_a_tok)
        )
        assert r2.status_code == 200, r2.text
        body2 = r2.json()
        assert body2["contact_unlocked"] is True, body2
        assert body2["seller_phone"], "phone should be exposed after unlock"

    def test_already_unlocked_400(self, tenant_a, listing_a):
        r = requests.post(
            f"{API}/yard-sale/listings/{listing_a['id']}/unlock-contact",
            data={"phone_number": "0712345678"},
            headers=_h(tenant_a["token"]),
            timeout=10,
        )
        assert r.status_code == 400


class TestBroadcast:
    def test_aa_other_user_cannot_broadcast(self, tenant_b, listing_a):
        # Run before broadcast happens so listing is still scope='property'
        r = requests.post(
            f"{API}/yard-sale/listings/{listing_a['id']}/broadcast",
            data={"phone_number": "0712345678"},
            headers=_h(tenant_b["token"]),
            timeout=10,
        )
        assert r.status_code == 403

    def test_broadcast_flow(self, tenant_a, tenant_b, listing_a):
        # Pre: tenant B can NOT see it (already covered)
        r = requests.post(
            f"{API}/yard-sale/listings/{listing_a['id']}/broadcast",
            data={"phone_number": "0712345678"},
            headers=_h(tenant_a["token"]),
            timeout=15,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["amount"] == 50
        time.sleep(7)
        # Now tenant B (cross-network) should see it (scope='all')
        r2 = requests.get(f"{API}/yard-sale/listings/{listing_a['id']}", headers=_h(tenant_b["token"]))
        assert r2.status_code == 200, r2.text
        assert r2.json()["scope"] == "all"

    def test_already_broadcast_400(self, tenant_a, listing_a):
        r = requests.post(
            f"{API}/yard-sale/listings/{listing_a['id']}/broadcast",
            data={"phone_number": "0712345678"},
            headers=_h(tenant_a["token"]),
            timeout=10,
        )
        assert r.status_code == 400


class TestFeature:
    def test_feature_flow(self, tenant_a, listing_a):
        r = requests.post(
            f"{API}/yard-sale/listings/{listing_a['id']}/feature",
            data={"phone_number": "0712345678"},
            headers=_h(tenant_a["token"]),
            timeout=15,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["amount"] == 100
        time.sleep(7)
        r2 = requests.get(
            f"{API}/yard-sale/listings/{listing_a['id']}", headers=_h(tenant_a["token"])
        )
        assert r2.status_code == 200
        body2 = r2.json()
        assert body2["featured"] is True
        assert body2["featured_until"]

    def test_other_user_cannot_feature(self, tenant_b, listing_a):
        r = requests.post(
            f"{API}/yard-sale/listings/{listing_a['id']}/feature",
            data={"phone_number": "0712345678"},
            headers=_h(tenant_b["token"]),
            timeout=10,
        )
        assert r.status_code == 403


class TestMigration:
    def test_all_listings_have_scope_and_contact_unlocked(self, admin_tok):
        r = requests.get(f"{API}/yard-sale/listings", headers=_h(admin_tok))
        assert r.status_code == 200, r.text
        for it in r.json():
            assert "scope" in it
            assert it["scope"] in ("property", "all")
            assert "contact_unlocked" in it
            assert isinstance(it["contact_unlocked"], bool)
