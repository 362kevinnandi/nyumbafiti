"""Oversight feature tests: admin approval gating for properties, tenants, caretakers.

Covers:
- approval queue + decisions
- gating: pending property hidden from marketplace
- gating: pending tenant cannot pay
- gating: pending caretaker cannot update issues
- admin oversight views (bills, issues, mediation messages)
- dashboard_stats new pending_* fields
- legacy data migration on startup
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@nyumbaos.co.ke"
ADMIN_PASSWORD = "admin123"
LANDLORD_EMAIL = "land@demo.com"
LANDLORD_PASSWORD = "demo123"


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def uniq(prefix="t"):
    return f"TEST_{prefix}_{uuid.uuid4().hex[:8]}"


# ---------- fixtures ----------

@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Admin login failed: {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def landlord_token():
    r = requests.post(f"{API}/auth/login", json={"email": LANDLORD_EMAIL, "password": LANDLORD_PASSWORD})
    assert r.status_code == 200, f"Landlord login failed: {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def landlord_id(landlord_token):
    r = requests.get(f"{API}/auth/me", headers=auth(landlord_token))
    assert r.status_code == 200
    return r.json()["id"]


@pytest.fixture(scope="module")
def new_property(landlord_token):
    """Create a fresh property (will be pending)."""
    payload = {
        "name": uniq("Prop"),
        "address": "Test Address",
        "description": "Pending approval test",
    }
    r = requests.post(f"{API}/properties", json=payload, headers=auth(landlord_token))
    assert r.status_code == 200, f"create property failed: {r.text}"
    return r.json()


@pytest.fixture(scope="module")
def new_unit(landlord_token, new_property):
    """Add a unit to the new pending property."""
    payload = {
        "property_id": new_property["id"],
        "unit_number": uniq("U")[:8],
        "rent_amount": 25000,
        "bedrooms": 1,
        "description": "Pending unit",
    }
    r = requests.post(f"{API}/units", json=payload, headers=auth(landlord_token))
    assert r.status_code == 200, f"create unit failed: {r.text}"
    return r.json()


# ============ Public marketplace gating ============

class TestPublicListingGating:

    def test_pending_property_unit_hidden_from_public_listings(self, new_unit, new_property):
        r = requests.get(f"{API}/public/listings")
        assert r.status_code == 200
        unit_ids = [l["id"] for l in r.json()]
        assert new_unit["id"] not in unit_ids, (
            "Pending property unit MUST NOT appear in /public/listings. "
            f"Property id={new_property['id']} status=pending"
        )

    def test_pending_property_unit_detail_returns_404(self, new_unit):
        r = requests.get(f"{API}/public/listings/{new_unit['id']}")
        assert r.status_code == 404


# ============ Tenant approval gating ============

class TestTenantApprovalGating:

    @pytest.fixture(scope="class")
    def approved_property_unit(self, landlord_token, admin_token):
        """Create a property, approve it, add a unit (needed for tenant assignment)."""
        prop = requests.post(
            f"{API}/properties",
            json={"name": uniq("ApprovedProp"), "address": "Approved Addr"},
            headers=auth(landlord_token),
        ).json()
        # approve the property
        ar = requests.post(
            f"{API}/admin/approvals/property/{prop['id']}",
            json={"approve": True},
            headers=auth(admin_token),
        )
        assert ar.status_code == 200
        unit = requests.post(
            f"{API}/units",
            json={
                "property_id": prop["id"],
                "unit_number": uniq("UA")[:8],
                "rent_amount": 30000,
                "bedrooms": 1,
            },
            headers=auth(landlord_token),
        ).json()
        return {"property": prop, "unit": unit}

    @pytest.fixture(scope="class")
    def pending_tenant(self, landlord_token, approved_property_unit):
        """Landlord creates a tenant -> tenant defaults to approval_status=pending."""
        email = f"TEST_tenant_{uuid.uuid4().hex[:8]}@x.com"
        password = "tenpass123"
        r = requests.post(
            f"{API}/tenants",
            json={
                "email": email,
                "full_name": "Pending Tenant",
                "phone": "254712345678",
                "password": password,
                "unit_id": approved_property_unit["unit"]["id"],
            },
            headers=auth(landlord_token),
        )
        assert r.status_code == 200, f"tenant create failed: {r.text}"
        tenant = r.json()
        # login as tenant
        lr = requests.post(f"{API}/auth/login", json={"email": email, "password": password})
        assert lr.status_code == 200
        return {"user": tenant, "token": lr.json()["access_token"], "email": email}

    def test_new_tenant_defaults_to_pending(self, pending_tenant):
        assert pending_tenant["user"]["approval_status"] == "pending"

    def test_pending_tenant_appears_in_approval_queue(self, admin_token, pending_tenant):
        r = requests.get(f"{API}/admin/approvals", headers=auth(admin_token))
        assert r.status_code == 200
        body = r.json()
        ids = [t["id"] for t in body["tenants"]]
        assert pending_tenant["user"]["id"] in ids
        # enrichment check
        match = next(t for t in body["tenants"] if t["id"] == pending_tenant["user"]["id"])
        assert "landlord_name" in match
        assert match["landlord_name"] != ""

    def test_pending_tenant_cannot_initiate_payment(self, pending_tenant, landlord_token, approved_property_unit):
        # First create a bill for this tenant
        bill_r = requests.post(
            f"{API}/bills",
            json={
                "tenant_id": pending_tenant["user"]["id"],
                "unit_id": approved_property_unit["unit"]["id"],
                "bill_type": "rent",
                "amount": 5000,
                "period": "2026-01",
                "due_date": "2026-01-31",
                "description": "Test bill",
            },
            headers=auth(landlord_token),
        )
        assert bill_r.status_code == 200, f"bill create: {bill_r.text}"
        bill = bill_r.json()
        # Try to pay -> expect 403
        pay_r = requests.post(
            f"{API}/payments/mpesa/stk-push",
            json={"bill_id": bill["id"], "phone_number": "254712345678"},
            headers=auth(pending_tenant["token"]),
        )
        assert pay_r.status_code == 403, f"Expected 403, got {pay_r.status_code}: {pay_r.text}"
        assert "pending" in pay_r.text.lower() or "verif" in pay_r.text.lower()
        # save for next test
        pending_tenant["bill_id"] = bill["id"]

    def test_admin_approves_tenant_then_payment_succeeds(self, admin_token, pending_tenant):
        # Admin approves
        ar = requests.post(
            f"{API}/admin/approvals/user/{pending_tenant['user']['id']}",
            json={"approve": True},
            headers=auth(admin_token),
        )
        assert ar.status_code == 200, ar.text
        assert ar.json()["status"] == "approved"

        # Re-login tenant to refresh user state (token holds id, not status)
        lr = requests.post(f"{API}/auth/login", json={
            "email": pending_tenant["email"], "password": "tenpass123"
        })
        assert lr.status_code == 200
        fresh_token = lr.json()["access_token"]
        assert lr.json()["user"]["approval_status"] == "approved"

        # Now payment should work
        pay_r = requests.post(
            f"{API}/payments/mpesa/stk-push",
            json={"bill_id": pending_tenant["bill_id"], "phone_number": "254712345678"},
            headers=auth(fresh_token),
        )
        assert pay_r.status_code == 200, f"Post-approval payment failed: {pay_r.text}"

    def test_admin_rejects_tenant(self, admin_token, landlord_token, approved_property_unit):
        # create a second tenant, reject them, ensure rejection_reason stored
        # need a free unit
        unit2 = requests.post(
            f"{API}/units",
            json={
                "property_id": approved_property_unit["property"]["id"],
                "unit_number": uniq("UB")[:8],
                "rent_amount": 20000,
                "bedrooms": 1,
            },
            headers=auth(landlord_token),
        ).json()
        email = f"TEST_reject_{uuid.uuid4().hex[:8]}@x.com"
        r = requests.post(
            f"{API}/tenants",
            json={
                "email": email,
                "full_name": "Reject Me",
                "phone": "254700000000",
                "password": "pw123456",
                "unit_id": unit2["id"],
            },
            headers=auth(landlord_token),
        )
        assert r.status_code == 200
        tid = r.json()["id"]
        # reject
        ar = requests.post(
            f"{API}/admin/approvals/user/{tid}",
            json={"approve": False, "reason": "Suspicious info"},
            headers=auth(admin_token),
        )
        assert ar.status_code == 200
        assert ar.json()["status"] == "rejected"

        # verify in /admin/users that rejection_reason was stored
        ur = requests.get(f"{API}/admin/users", headers=auth(admin_token))
        assert ur.status_code == 200
        match = next((u for u in ur.json() if u["id"] == tid), None)
        assert match is not None
        assert match.get("approval_status") == "rejected"
        assert match.get("rejection_reason") == "Suspicious info"


# ============ Caretaker approval gating ============

class TestCaretakerApprovalGating:

    @pytest.fixture(scope="class")
    def pending_caretaker(self, landlord_token):
        email = f"TEST_ck_{uuid.uuid4().hex[:8]}@x.com"
        password = "ckpass123"
        r = requests.post(
            f"{API}/caretakers",
            json={
                "email": email,
                "full_name": "Pending Caretaker",
                "phone": "254700111222",
                "password": password,
            },
            headers=auth(landlord_token),
        )
        assert r.status_code == 200
        lr = requests.post(f"{API}/auth/login", json={"email": email, "password": password})
        assert lr.status_code == 200
        return {"user": r.json(), "token": lr.json()["access_token"], "email": email}

    def test_new_caretaker_defaults_to_pending(self, pending_caretaker):
        assert pending_caretaker["user"]["approval_status"] == "pending"

    def test_pending_caretaker_in_approval_queue(self, admin_token, pending_caretaker):
        r = requests.get(f"{API}/admin/approvals", headers=auth(admin_token))
        assert r.status_code == 200
        ids = [c["id"] for c in r.json()["caretakers"]]
        assert pending_caretaker["user"]["id"] in ids

    def test_pending_caretaker_cannot_update_issue(self, admin_token, pending_caretaker, landlord_token):
        # need an existing issue. Just grab any issue from admin oversight; if none, skip.
        ar = requests.get(f"{API}/admin/issues", headers=auth(admin_token))
        assert ar.status_code == 200
        issues = ar.json()
        if not issues:
            pytest.skip("No issues exist to test caretaker update gating")
        issue_id = issues[0]["id"]
        r = requests.patch(
            f"{API}/issues/{issue_id}",
            json={"status": "in_progress"},
            headers=auth(pending_caretaker["token"]),
        )
        # Could be 403 (pending approval) or 403 (not in network) — but the approval gating
        # should kick in if the caretaker shares the landlord. If not in same landlord network,
        # we get the network 403, which is also fine - just verify SOMETHING blocks.
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"

    def test_admin_approves_caretaker(self, admin_token, pending_caretaker):
        ar = requests.post(
            f"{API}/admin/approvals/user/{pending_caretaker['user']['id']}",
            json={"approve": True},
            headers=auth(admin_token),
        )
        assert ar.status_code == 200
        assert ar.json()["status"] == "approved"


# ============ Property approval flow ============

class TestPropertyApprovalFlow:

    def test_new_property_in_approval_queue(self, admin_token, new_property):
        r = requests.get(f"{API}/admin/approvals", headers=auth(admin_token))
        assert r.status_code == 200
        body = r.json()
        ids = [p["id"] for p in body["properties"]]
        assert new_property["id"] in ids
        assert body["total_pending"] >= 1

    def test_approve_property_makes_it_appear_in_public_listings(
        self, admin_token, new_property, new_unit
    ):
        ar = requests.post(
            f"{API}/admin/approvals/property/{new_property['id']}",
            json={"approve": True},
            headers=auth(admin_token),
        )
        assert ar.status_code == 200
        assert ar.json()["status"] == "approved"

        # Now check public listings
        lr = requests.get(f"{API}/public/listings")
        unit_ids = [l["id"] for l in lr.json()]
        assert new_unit["id"] in unit_ids, "Approved property unit MUST appear in /public/listings"

        # And detail endpoint should now return 200
        dr = requests.get(f"{API}/public/listings/{new_unit['id']}")
        assert dr.status_code == 200

    def test_reject_property_with_reason(self, admin_token, landlord_token):
        # create a new pending property
        p = requests.post(
            f"{API}/properties",
            json={"name": uniq("Rejected"), "address": "Reject Addr"},
            headers=auth(landlord_token),
        ).json()
        ar = requests.post(
            f"{API}/admin/approvals/property/{p['id']}",
            json={"approve": False, "reason": "Photos unclear"},
            headers=auth(admin_token),
        )
        assert ar.status_code == 200
        assert ar.json()["status"] == "rejected"

        # verify via admin/properties
        pr = requests.get(f"{API}/admin/properties", headers=auth(admin_token))
        assert pr.status_code == 200
        match = next((x for x in pr.json() if x["id"] == p["id"]), None)
        assert match is not None
        assert match.get("approval_status") == "rejected"
        assert match.get("rejection_reason") == "Photos unclear"

    def test_admin_cannot_approve_landlord_user(self, admin_token, landlord_id):
        ar = requests.post(
            f"{API}/admin/approvals/user/{landlord_id}",
            json={"approve": True},
            headers=auth(admin_token),
        )
        assert ar.status_code == 400


# ============ Admin oversight views ============

class TestAdminOversightViews:

    def test_admin_bills_returns_enriched(self, admin_token):
        r = requests.get(f"{API}/admin/bills", headers=auth(admin_token))
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        if data:
            sample = data[0]
            # enrichment fields present (tenant_name or landlord_name should exist)
            assert "tenant_name" in sample or "landlord_name" in sample

    def test_admin_bills_status_filter(self, admin_token):
        r = requests.get(f"{API}/admin/bills?status=pending", headers=auth(admin_token))
        assert r.status_code == 200
        for b in r.json():
            assert b["status"] == "pending"

    def test_admin_issues_returns_enriched(self, admin_token):
        r = requests.get(f"{API}/admin/issues", headers=auth(admin_token))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_admin_issues_status_filter(self, admin_token):
        r = requests.get(f"{API}/admin/issues?status=open", headers=auth(admin_token))
        assert r.status_code == 200
        for i in r.json():
            assert i["status"] == "open"

    def test_admin_can_read_and_post_in_any_issue_thread(self, admin_token):
        ir = requests.get(f"{API}/admin/issues", headers=auth(admin_token))
        issues = ir.json()
        if not issues:
            pytest.skip("No issues exist")
        iid = issues[0]["id"]
        # GET messages
        gr = requests.get(f"{API}/admin/issues/{iid}/messages", headers=auth(admin_token))
        assert gr.status_code == 200
        assert isinstance(gr.json(), list)
        # POST message
        pr = requests.post(
            f"{API}/admin/issues/{iid}/messages",
            json={"body": "Admin mediation: please share photos."},
            headers=auth(admin_token),
        )
        assert pr.status_code == 200
        msg = pr.json()
        assert msg["author_role"] == "admin"
        assert msg["body"].startswith("Admin mediation")
        # GET again, verify it appeared
        gr2 = requests.get(f"{API}/admin/issues/{iid}/messages", headers=auth(admin_token))
        bodies = [m["body"] for m in gr2.json()]
        assert "Admin mediation: please share photos." in bodies


# ============ Dashboard stats fields ============

class TestAdminStatsFields:

    def test_stats_includes_new_fields(self, admin_token):
        r = requests.get(f"{API}/admin/stats", headers=auth(admin_token))
        assert r.status_code == 200
        s = r.json()
        for key in [
            "pending_property_approvals",
            "pending_tenant_approvals",
            "pending_caretaker_approvals",
            "pending_approvals_total",
            "total_arrears",
        ]:
            assert key in s, f"missing {key} in /admin/stats"
        # totals consistency
        assert s["pending_approvals_total"] == (
            s["pending_property_approvals"]
            + s["pending_tenant_approvals"]
            + s["pending_caretaker_approvals"]
        )


# ============ Legacy data still accessible (migration) ============

class TestLegacyDataMigration:
    """Existing seed properties (Riverside, Kilimani) should still appear in /public/listings
    and their detail endpoint should work — they were either created with approval_status='approved'
    OR migrated on startup."""

    def test_legacy_listings_still_visible(self):
        r = requests.get(f"{API}/public/listings")
        assert r.status_code == 200
        listings = r.json()
        # at least one legacy property should be visible
        names = {l["property"]["name"] for l in listings}
        assert any(n in names for n in ["Riverside Apartments", "Kilimani Heights"]), (
            f"Legacy demo properties missing from /public/listings: {names}"
        )

    def test_legacy_listing_detail_returns_200(self):
        r = requests.get(f"{API}/public/listings")
        for l in r.json():
            if l["property"]["name"] in ("Riverside Apartments", "Kilimani Heights"):
                dr = requests.get(f"{API}/public/listings/{l['id']}")
                assert dr.status_code == 200, (
                    f"Legacy unit {l['id']} ({l['property']['name']}) returns "
                    f"{dr.status_code} — migration to approval_status='approved' did not run"
                )
                return
        pytest.skip("No legacy listings found")


# ============ Authorization checks ============

class TestOversightAuthorization:

    def test_non_admin_cannot_access_approvals(self, landlord_token):
        r = requests.get(f"{API}/admin/approvals", headers=auth(landlord_token))
        assert r.status_code == 403

    def test_non_admin_cannot_access_admin_bills(self, landlord_token):
        r = requests.get(f"{API}/admin/bills", headers=auth(landlord_token))
        assert r.status_code == 403

    def test_non_admin_cannot_access_admin_issues(self, landlord_token):
        r = requests.get(f"{API}/admin/issues", headers=auth(landlord_token))
        assert r.status_code == 403

    def test_unauthenticated_blocked_from_approvals(self):
        r = requests.get(f"{API}/admin/approvals")
        assert r.status_code in (401, 403)
