"""Round 4 regression tests:
- Security auto-approve
- Admin reset-credentials + audit log
- Yard-sale forced KES 35 contact-unlock + STK callback flow
- Public visitor pass viewer /pass/{token}
- Marketplace lease vs rental filter
- Admin CSV/XLSX/PDF exports across 8 resources
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://property-caretaker-3.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@nyumbaos.co.ke"
ADMIN_PASS = "admin123"
LANDLORD_EMAIL = "mary@demo.nyumba"
LANDLORD_PASS = "demo123"
TENANT_RENTAL_EMAIL = "tenant1@demo.nyumba"
TENANT_LEASE_EMAIL = "tenant4@demo.nyumba"
TENANT_PASS = "demo123"
SECURITY_EMAIL = "sg1@demo.nyumba"
SECURITY_PASS = "demo123"


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text}"
    body = r.json()
    return body.get("access_token") or body.get("token")


def _h(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def landlord_token():
    return _login(LANDLORD_EMAIL, LANDLORD_PASS)


@pytest.fixture(scope="module")
def tenant_token():
    return _login(TENANT_RENTAL_EMAIL, TENANT_PASS)


# ============== 1. Security auto-approve ==============
class TestSecurityAutoApprove:
    def test_seeded_security_can_login(self):
        token = _login(SECURITY_EMAIL, SECURITY_PASS)
        assert token

    def test_create_security_auto_approved(self, landlord_token):
        suffix = uuid.uuid4().hex[:6]
        payload = {
            "full_name": f"TEST_SG_{suffix}",
            "email": f"test_sg_{suffix}@demo.nyumba",
            "phone": "+254700111222",
            "password": "TestPass123",
            "role": "security",
        }
        r = requests.post(f"{API}/security", json=payload, headers=_h(landlord_token), timeout=30)
        assert r.status_code in (200, 201), r.text
        body = r.json()
        # Find user record
        user = body.get("user") or body
        assert user.get("approval_status") == "approved", f"Expected approved, got: {user}"
        # Verify they can log in immediately
        t = _login(payload["email"], payload["password"])
        assert t

    def test_admin_approvals_security_empty(self, admin_token):
        r = requests.get(f"{API}/admin/approvals", headers=_h(admin_token), timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        # security should be empty array
        sec = data.get("security", [])
        assert isinstance(sec, list)
        assert len(sec) == 0, f"Security queue should be empty (auto-approved), got {sec}"


# ============== 2. Admin reset-credentials ==============
class TestAdminResetCredentials:
    def test_reset_empty_body_400(self, admin_token):
        # Create a throwaway target so we don't break demo creds when this fails
        l_token = _login(LANDLORD_EMAIL, LANDLORD_PASS)
        suffix = uuid.uuid4().hex[:6]
        email = f"empty_body_{suffix}@demo.nyumba"
        r = requests.post(f"{API}/security", json={
            "full_name": f"TEST_EB_{suffix}",
            "email": email,
            "phone": "+254700987654",
            "password": "InitPass123",
        }, headers=_h(l_token), timeout=30)
        assert r.status_code in (200, 201), r.text
        user = (r.json().get("user") or r.json())
        uid = user.get("id") or user.get("_id")
        r = requests.post(f"{API}/admin/users/{uid}/reset-credentials", json={}, headers=_h(admin_token), timeout=30)
        assert r.status_code == 400, f"Expected 400 for empty body, got {r.status_code}: {r.text}"

    def test_reset_password_returns_new_password(self, admin_token):
        # Create a throwaway user via landlord (use security path)
        l_token = _login(LANDLORD_EMAIL, LANDLORD_PASS)
        suffix = uuid.uuid4().hex[:6]
        email = f"reset_target_{suffix}@demo.nyumba"
        r = requests.post(f"{API}/security", json={
            "full_name": f"TEST_RT_{suffix}",
            "email": email,
            "phone": "+254700333444",
            "password": "InitialPass123",
        }, headers=_h(l_token), timeout=30)
        assert r.status_code in (200, 201), r.text
        user = (r.json().get("user") or r.json())
        uid = user.get("id") or user.get("_id")

        # Reset with generate flag (no new_password)
        r2 = requests.post(f"{API}/admin/users/{uid}/reset-credentials",
                           json={"reset_password": True}, headers=_h(admin_token), timeout=30)
        assert r2.status_code == 200, r2.text
        body = r2.json()
        new_pwd = body.get("new_password") or body.get("password")
        assert new_pwd and len(new_pwd) >= 6, f"Expected generated password, got: {body}"

        # Verify new password works
        t = _login(email, new_pwd)
        assert t

    def test_reset_email_changes_email(self, admin_token):
        # Create throwaway user
        l_token = _login(LANDLORD_EMAIL, LANDLORD_PASS)
        suffix = uuid.uuid4().hex[:6]
        old_email = f"oldmail_{suffix}@demo.nyumba"
        r = requests.post(f"{API}/security", json={
            "full_name": f"TEST_EM_{suffix}",
            "email": old_email,
            "phone": "+254700555666",
            "password": "Pass123456",
        }, headers=_h(l_token), timeout=30)
        assert r.status_code in (200, 201)
        user = (r.json().get("user") or r.json())
        uid = user.get("id") or user.get("_id")
        new_email = f"newmail_{suffix}@demo.nyumba"
        r2 = requests.post(f"{API}/admin/users/{uid}/reset-credentials",
                           json={"new_email": new_email}, headers=_h(admin_token), timeout=30)
        assert r2.status_code == 200, r2.text
        # Verify login with new email and old password works
        t = _login(new_email, "Pass123456")
        assert t

    def test_reset_non_admin_403(self, landlord_token, admin_token):
        # Get any user id
        r = requests.get(f"{API}/admin/users", headers=_h(admin_token), timeout=30)
        users = r.json()
        uid = users[0].get("id") or users[0].get("_id")
        r2 = requests.post(f"{API}/admin/users/{uid}/reset-credentials",
                           json={"reset_password": True}, headers=_h(landlord_token), timeout=30)
        assert r2.status_code == 403, f"Expected 403 for non-admin, got {r2.status_code}"

    def test_reset_self_400(self, admin_token):
        r = requests.get(f"{API}/auth/me", headers=_h(admin_token), timeout=30)
        assert r.status_code == 200
        me = r.json()
        uid = me.get("id") or me.get("_id")
        r2 = requests.post(f"{API}/admin/users/{uid}/reset-credentials",
                           json={"reset_password": True}, headers=_h(admin_token), timeout=30)
        assert r2.status_code == 400, f"Expected 400 for self-reset, got {r2.status_code}"

    def test_audit_log_admin_only(self, admin_token, landlord_token):
        r = requests.get(f"{API}/admin/audit-log", headers=_h(admin_token), timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list) or isinstance(data, dict)
        # Non-admin returns 403
        r2 = requests.get(f"{API}/admin/audit-log", headers=_h(landlord_token), timeout=30)
        assert r2.status_code == 403


# ============== 3. Yard-sale forced KES 35 ==============
class TestYardSalePayment:
    def test_create_listing_requires_phone(self, tenant_token):
        # Multipart form without phone_number → 422
        r = requests.post(f"{API}/yard-sale/listings",
                          data={"title": f"TEST {uuid.uuid4().hex[:6]}", "price": "1000", "scope": "property"},
                          headers={"Authorization": f"Bearer {tenant_token}"}, timeout=30)
        assert r.status_code in (400, 422), f"Expected 400/422 without phone, got {r.status_code}: {r.text}"

    def test_create_listing_with_phone_pending_payment(self, tenant_token):
        suffix = uuid.uuid4().hex[:6]
        r = requests.post(f"{API}/yard-sale/listings",
                          data={
                              "title": f"TEST YS {suffix}",
                              "description": "Test yard sale item",
                              "price": "1500",
                              "phone_number": "+254700777888",
                              "scope": "property",
                          },
                          headers={"Authorization": f"Bearer {tenant_token}"}, timeout=30)
        assert r.status_code in (200, 201), r.text
        body = r.json()
        listing = body.get("listing") or {}
        payment = body.get("payment") or {}
        assert listing.get("status") == "pending_payment", f"status: {listing.get('status')}"
        assert listing.get("contact_unlocked") is False
        assert payment.get("amount") == 35
        assert payment.get("payment_id")

    def test_pending_listing_hidden_from_others(self, tenant_token):
        suffix = uuid.uuid4().hex[:6]
        r = requests.post(f"{API}/yard-sale/listings",
                          data={
                              "title": f"TEST Hidden {suffix}",
                              "description": "Should be hidden",
                              "price": "500",
                              "phone_number": "+254700999000",
                              "scope": "property",
                          },
                          headers={"Authorization": f"Bearer {tenant_token}"}, timeout=30)
        assert r.status_code in (200, 201), r.text
        listing_id = (r.json().get("listing") or {}).get("id")
        assert listing_id

        # View as another tenant
        other_tok = _login("tenant2@demo.nyumba", TENANT_PASS)
        r2 = requests.get(f"{API}/yard-sale/listings", headers=_h(other_tok), timeout=30)
        assert r2.status_code == 200
        ids = [l.get("id") for l in r2.json()]
        assert listing_id not in ids, "Pending payment listing leaked to other tenant"

    def test_callback_flips_to_active(self, tenant_token):
        suffix = uuid.uuid4().hex[:6]
        r = requests.post(f"{API}/yard-sale/listings",
                          data={
                              "title": f"TEST Callback {suffix}",
                              "description": "Will flip to active",
                              "price": "2000",
                              "phone_number": "+254700111000",
                              "scope": "property",
                          },
                          headers={"Authorization": f"Bearer {tenant_token}"}, timeout=30)
        assert r.status_code in (200, 201), r.text
        body = r.json()
        listing_id = body["listing"]["id"]

        # Poll listing for up to 25s for status==active
        deadline = time.time() + 25
        final_status = None
        unlocked = None
        while time.time() < deadline:
            time.sleep(2)
            # Owner can see their own
            r2 = requests.get(f"{API}/yard-sale/listings", headers=_h(tenant_token), timeout=30)
            if r2.status_code == 200:
                for l in r2.json():
                    if l.get("id") == listing_id:
                        final_status = l.get("status")
                        unlocked = l.get("contact_unlocked")
                        break
            if final_status == "active":
                break
        assert final_status == "active", f"Listing did not flip to active in 25s; last status={final_status}"
        assert unlocked is True


# ============== 4. Public pass viewer ==============
class TestPublicPassViewer:
    def test_invalid_token_404(self):
        r = requests.get(f"{API}/public/pass/INVALID_TOKEN_XYZ", timeout=30)
        assert r.status_code == 404

    def test_valid_pass_returns_qr(self, tenant_token):
        # Create a visitor pass as tenant
        suffix = uuid.uuid4().hex[:6]
        payload = {
            "visitor_name": f"TEST Guest {suffix}",
            "visitor_phone": "+254700000111",
            "expected_time": "2026-02-15T10:00:00",
        }
        r = requests.post(f"{API}/visitor-passes", json=payload, headers=_h(tenant_token), timeout=30)
        assert r.status_code in (200, 201), r.text
        body = r.json()
        token = body.get("token") or body.get("pass_token") or body.get("pass", {}).get("token")
        assert token, f"No pass token in response: {body}"

        # Public no-auth GET
        r2 = requests.get(f"{API}/public/pass/{token}", timeout=30)
        assert r2.status_code == 200, r2.text
        data = r2.json()
        assert "visitor_name" in data
        assert "host_name" in data
        assert "property_name" in data
        assert "qr_data_url" in data
        assert data["qr_data_url"].startswith("data:image"), f"qr_data_url not a data URL: {data.get('qr_data_url', '')[:80]}"


# ============== 5. Marketplace lease/rental filter ==============
class TestMarketplaceFilter:
    def test_lease_filter(self):
        r = requests.get(f"{API}/public/listings", params={"tenancy_type": "lease"}, timeout=30)
        assert r.status_code == 200, r.text
        listings = r.json()
        assert isinstance(listings, list)
        for l in listings:
            tt = l.get("tenancy_types") or (l.get("property", {}).get("tenancy_types")) or []
            assert "lease" in tt, f"Listing without 'lease' in tenancy_types: {l}"

    def test_rental_filter(self):
        r = requests.get(f"{API}/public/listings", params={"tenancy_type": "rental"}, timeout=30)
        assert r.status_code == 200, r.text
        listings = r.json()
        for l in listings:
            tt = l.get("tenancy_types") or (l.get("property", {}).get("tenancy_types")) or []
            assert "rental" in tt, f"Listing without 'rental' in tenancy_types: {l}"


# ============== 6. Admin exports ==============
class TestAdminExports:
    RESOURCES = ["users", "payments", "payouts", "properties", "bills", "issues", "viewings", "leases"]
    FORMATS = ["csv", "xlsx", "pdf"]

    def test_all_export_combinations_admin(self, admin_token):
        failures = []
        for res in self.RESOURCES:
            for fmt in self.FORMATS:
                url = f"{API}/admin/export/{res}.{fmt}"
                r = requests.get(url, headers=_h(admin_token), timeout=60)
                if r.status_code != 200:
                    failures.append(f"{res}.{fmt} -> {r.status_code}: {r.text[:200]}")
        assert not failures, "Export failures:\n" + "\n".join(failures)

    def test_export_non_admin_403(self, landlord_token):
        r = requests.get(f"{API}/admin/export/users.csv", headers=_h(landlord_token), timeout=30)
        assert r.status_code == 403, f"Expected 403, got {r.status_code}"
