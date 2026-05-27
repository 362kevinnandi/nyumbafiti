"""Round 5 regression tests: 2-step rent flow, disbursements, settings, security scan."""
import math
import os
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://property-caretaker-3.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


# ---------- helpers ----------

def login(email: str, password: str) -> str:
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json()["access_token"]


def H(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


# ---------- fixtures ----------

@pytest.fixture(scope="session")
def admin_tok() -> str:
    return login("admin@nyumbaos.co.ke", "admin123")


@pytest.fixture(scope="session")
def mary_tok() -> str:
    return login("mary@demo.nyumba", "demo123")


@pytest.fixture(scope="session")
def james_tok() -> str:
    return login("james@demo.nyumba", "demo123")


@pytest.fixture(scope="session")
def ck1_tok() -> str:
    return login("ck1@demo.nyumba", "demo123")


@pytest.fixture(scope="session")
def ck2_tok() -> str:
    return login("ck2@demo.nyumba", "demo123")


@pytest.fixture(scope="session")
def sg1_tok() -> str:
    return login("sg1@demo.nyumba", "demo123")


@pytest.fixture(scope="session")
def t1_tok() -> str:
    return login("tenant1@demo.nyumba", "demo123")


@pytest.fixture(scope="session")
def t3_tok() -> str:
    return login("tenant3@demo.nyumba", "demo123")


@pytest.fixture(scope="session")
def mary_property_id(mary_tok) -> str:
    r = requests.get(f"{API}/properties", headers=H(mary_tok), timeout=30)
    assert r.status_code == 200
    props = r.json()
    assert len(props) > 0
    # Find tenant1's property
    t1_h = H(login("tenant1@demo.nyumba", "demo123"))
    bills_r = requests.get(f"{API}/bills", headers=t1_h, timeout=30)
    assert bills_r.status_code == 200
    bills = bills_r.json()
    if bills:
        pid = bills[0]["property_id"]
        if any(p["id"] == pid for p in props):
            return pid
    return props[0]["id"]


@pytest.fixture(scope="session", autouse=True)
def set_mary_paybill(mary_tok, mary_property_id):
    """Make sure mary's property has paybill set + at least one pending bill exists."""
    r = requests.patch(
        f"{API}/properties/{mary_property_id}",
        headers=H(mary_tok),
        json={"landlord_paybill": "522522", "landlord_account_number": "WESTLANDS-1A"},
        timeout=30,
    )
    assert r.status_code in (200, 204), f"patch property failed: {r.status_code} {r.text}"
    # Generate monthly bills so tenants have something to pay (idempotent)
    requests.post(f"{API}/bills/generate-monthly", headers=H(mary_tok), timeout=30)
    james = login("james@demo.nyumba", "demo123")
    requests.post(f"{API}/bills/generate-monthly", headers={"Authorization": f"Bearer {james}"}, timeout=30)
    return r.json() if r.status_code == 200 else None


# ============ Admin settings ============

class TestAdminSettings:
    def test_get_settings_returns_all_new_fields(self, admin_tok):
        r = requests.get(f"{API}/admin/settings", headers=H(admin_tok), timeout=30)
        assert r.status_code == 200
        s = r.json()
        for key in [
            "platform_paybill", "platform_account", "service_fee_pct",
            "viewing_caretaker_share", "viewing_platform_share", "commission_rate",
        ]:
            assert key in s, f"missing settings key: {key}"
        assert isinstance(s["service_fee_pct"], (int, float))

    def test_patch_partial_update(self, admin_tok):
        r = requests.patch(
            f"{API}/admin/settings",
            headers=H(admin_tok),
            json={"platform_paybill": "247247", "service_fee_pct": 0.025},
            timeout=30,
        )
        assert r.status_code == 200
        s = r.json()
        assert s["platform_paybill"] == "247247"
        assert abs(s["service_fee_pct"] - 0.025) < 1e-9

    def test_get_settings_admin_only(self, t1_tok):
        r = requests.get(f"{API}/admin/settings", headers=H(t1_tok), timeout=30)
        assert r.status_code in (401, 403)

    def test_public_settings_no_secrets(self, t1_tok):
        r = requests.get(f"{API}/admin/public-settings", headers=H(t1_tok), timeout=30)
        assert r.status_code == 200
        ps = r.json()
        assert set(ps.keys()) == {"platform_paybill", "platform_account", "service_fee_pct"}


# ============ Properties paybill fields ============

class TestPropertyPaybill:
    def test_get_properties_returns_paybill(self, mary_tok, mary_property_id):
        r = requests.get(f"{API}/properties", headers=H(mary_tok), timeout=30)
        assert r.status_code == 200
        props = r.json()
        target = next(p for p in props if p["id"] == mary_property_id)
        assert target.get("landlord_paybill") == "522522"
        assert target.get("landlord_account_number") == "WESTLANDS-1A"

    def test_patch_property_paybill(self, mary_tok, mary_property_id):
        r = requests.patch(
            f"{API}/properties/{mary_property_id}",
            headers=H(mary_tok),
            json={"landlord_paybill": "522522", "landlord_account_number": "WESTLANDS-1A-UPDATED"},
            timeout=30,
        )
        assert r.status_code == 200
        # GET to verify persistence
        g = requests.get(f"{API}/properties", headers=H(mary_tok), timeout=30)
        target = next(p for p in g.json() if p["id"] == mary_property_id)
        assert target["landlord_account_number"] == "WESTLANDS-1A-UPDATED"
        # restore
        requests.patch(
            f"{API}/properties/{mary_property_id}",
            headers=H(mary_tok),
            json={"landlord_paybill": "522522", "landlord_account_number": "WESTLANDS-1A"},
            timeout=30,
        )


# ============ Visitor scan security access ============

class TestVisitorPassScan:
    def test_security_can_scan_own_landlord_pass(self, t1_tok, sg1_tok):
        # tenant1 (mary) creates a pass
        create = requests.post(
            f"{API}/visitor-passes",
            headers=H(t1_tok),
            json={"visitor_name": "TEST_R5_Guest", "expected_time": "2030-12-31T10:00:00Z"},
            timeout=30,
        )
        assert create.status_code in (200, 201), f"{create.status_code} {create.text}"
        token = create.json()["token"]
        # sg1 (mary's security) scans
        scan = requests.post(f"{API}/visitor-passes/scan/{token}", headers=H(sg1_tok), timeout=30)
        assert scan.status_code == 200, f"sg1 scan failed: {scan.status_code} {scan.text}"

    def test_security_cannot_scan_other_landlord_pass(self, t3_tok, sg1_tok):
        # tenant3 (james) creates a pass
        create = requests.post(
            f"{API}/visitor-passes",
            headers=H(t3_tok),
            json={"visitor_name": "TEST_R5_CrossGuest", "expected_time": "2030-12-31T10:00:00Z"},
            timeout=30,
        )
        assert create.status_code in (200, 201)
        token = create.json()["token"]
        scan = requests.post(f"{API}/visitor-passes/scan/{token}", headers=H(sg1_tok), timeout=30)
        assert scan.status_code == 403, f"expected 403 cross-landlord, got {scan.status_code} {scan.text}"


# ============ Two-step rent payment flow ============

def _find_pending_bill(t_tok: str) -> dict | None:
    r = requests.get(f"{API}/bills", headers=H(t_tok), timeout=30)
    assert r.status_code == 200
    bills = r.json()
    for b in bills:
        if b["status"] in ("pending", "partial") and not b.get("service_fee_paid_at"):
            return b
    return None


class TestTwoStepRentFlow:
    def test_stk_push_only_service_fee(self, t1_tok):
        bill = _find_pending_bill(t1_tok)
        if not bill:
            pytest.skip("No pending bill for tenant1")
        payload = {"bill_id": bill["id"], "phone_number": "254708374149"}
        r = requests.post(f"{API}/payments/mpesa/stk-push", headers=H(t1_tok), json=payload, timeout=60)
        assert r.status_code == 200, f"stk-push failed: {r.status_code} {r.text}"
        data = r.json()
        # Validate required response fields
        for k in [
            "payment_id", "service_fee_amount", "rent_amount", "total_cost_to_tenant",
            "landlord_paybill", "landlord_account_number", "platform_paybill", "platform_account",
        ]:
            assert k in data, f"missing field: {k}"
        # Math: service_fee = ceil(rent * 0.025 / 10) * 10
        expected_fee = math.ceil(data["rent_amount"] * 0.025 / 10) * 10
        assert data["service_fee_amount"] == expected_fee, (
            f"expected fee {expected_fee} got {data['service_fee_amount']} for rent {data['rent_amount']}"
        )
        assert data["total_cost_to_tenant"] == data["rent_amount"] + data["service_fee_amount"]
        assert data["landlord_paybill"] == "522522"
        assert data["landlord_account_number"] == "WESTLANDS-1A"
        # Save state for next test via class attribute
        TestTwoStepRentFlow.bill_id = bill["id"]
        TestTwoStepRentFlow.checkout_id = data["checkout_request_id"]
        TestTwoStepRentFlow.fee_amount = data["service_fee_amount"]
        # Immediately fire a SUCCESS callback to beat sandbox's "DS timeout" failure.
        # This is the only deterministic way to test the bill state-machine since real
        # sandbox cannot reach test phone numbers.
        if data.get("checkout_request_id"):
            secret = os.environ.get("MPESA_CALLBACK_SECRET", "nrm-callback-secret")
            cb = {
                "Body": {
                    "stkCallback": {
                        "MerchantRequestID": "TEST_R5_MR",
                        "CheckoutRequestID": data["checkout_request_id"],
                        "ResultCode": 0,
                        "ResultDesc": "TEST_R5 forced success",
                        "CallbackMetadata": {
                            "Item": [
                                {"Name": "Amount", "Value": data["service_fee_amount"]},
                                {"Name": "MpesaReceiptNumber", "Value": "TESTR5FEE01"},
                                {"Name": "PhoneNumber", "Value": 254708374149},
                            ]
                        },
                    }
                }
            }
            requests.post(f"{API}/payments/mpesa/callback/{secret}", json=cb, timeout=30)

    def test_callback_settles_to_awaiting_rent_receipt(self, t1_tok):
        bill_id = getattr(TestTwoStepRentFlow, "bill_id", None)
        if not bill_id:
            pytest.skip("no bill from prior test")
        # Poll up to 25s — forced callback should beat sandbox, but allow time
        deadline = time.time() + 25
        bill = None
        while time.time() < deadline:
            r = requests.get(f"{API}/bills", headers=H(t1_tok), timeout=30)
            bill = next((b for b in r.json() if b["id"] == bill_id), None)
            if bill and bill.get("status") == "awaiting_rent_receipt":
                break
            time.sleep(2)
        assert bill is not None
        assert bill.get("service_fee_paid_at"), f"service_fee_paid_at not set, status={bill.get('status')}"
        assert bill["status"] == "awaiting_rent_receipt", f"status: {bill['status']}"

    def test_submit_rent_receipt_before_fee_rejected(self, t3_tok):
        # Find an untouched bill for tenant3
        r = requests.get(f"{API}/bills", headers=H(t3_tok), timeout=30)
        bill = next(
            (b for b in r.json()
             if b["status"] in ("pending", "partial")
             and not b.get("service_fee_paid_at")
             and not b.get("rent_receipt_submitted_at")),
            None,
        )
        if not bill:
            pytest.skip("no eligible bill")
        sub = requests.post(
            f"{API}/bills/{bill['id']}/submit-rent-receipt",
            headers=H(t3_tok),
            json={"mpesa_receipt": "SGH7XYZ123", "amount_paid": bill["amount"]},
            timeout=30,
        )
        assert sub.status_code == 400, f"expected 400 fee-not-paid, got {sub.status_code} {sub.text}"

    def test_submit_rent_receipt_after_fee(self, t1_tok):
        bill_id = getattr(TestTwoStepRentFlow, "bill_id", None)
        if not bill_id:
            pytest.skip("no bill from prior test")
        # Wait until fee is settled
        bill = None
        deadline = time.time() + 25
        while time.time() < deadline:
            r = requests.get(f"{API}/bills", headers=H(t1_tok), timeout=30)
            bill = next((b for b in r.json() if b["id"] == bill_id), None)
            if bill and bill.get("service_fee_paid_at") and bill["status"] == "awaiting_rent_receipt":
                break
            time.sleep(2)
        assert bill and bill.get("service_fee_paid_at"), f"fee not paid: {bill}"
        sub = requests.post(
            f"{API}/bills/{bill_id}/submit-rent-receipt",
            headers=H(t1_tok),
            json={"mpesa_receipt": "SGH7R5TEST", "amount_paid": bill["amount"]},
            timeout=30,
        )
        assert sub.status_code == 200, f"submit failed: {sub.status_code} {sub.text}"
        # Verify state flipped
        r2 = requests.get(f"{API}/bills", headers=H(t1_tok), timeout=30)
        b2 = next(b for b in r2.json() if b["id"] == bill_id)
        assert b2["status"] == "awaiting_landlord_confirmation"
        assert b2.get("rent_receipt_code") == "SGH7R5TEST"

    def test_tenant_cannot_confirm(self, t1_tok):
        bill_id = getattr(TestTwoStepRentFlow, "bill_id", None)
        if not bill_id:
            pytest.skip()
        r = requests.post(f"{API}/bills/{bill_id}/confirm-rent-receipt", headers=H(t1_tok), timeout=30)
        assert r.status_code in (401, 403)

    def test_wrong_caretaker_cannot_confirm(self, ck2_tok):
        bill_id = getattr(TestTwoStepRentFlow, "bill_id", None)
        if not bill_id:
            pytest.skip()
        r = requests.post(f"{API}/bills/{bill_id}/confirm-rent-receipt", headers=H(ck2_tok), timeout=30)
        assert r.status_code == 403, f"expected 403 cross-landlord caretaker, got {r.status_code} {r.text}"

    def test_landlord_can_reject(self, mary_tok, t1_tok):
        # Use the same bill: reject first to test reject, then re-submit, then confirm
        bill_id = getattr(TestTwoStepRentFlow, "bill_id", None)
        if not bill_id:
            pytest.skip()
        rej = requests.post(
            f"{API}/bills/{bill_id}/reject-rent-receipt",
            headers=H(mary_tok),
            json={"reason": "TEST_R5 wrong code"},
            timeout=30,
        )
        assert rej.status_code == 200, f"reject failed: {rej.status_code} {rej.text}"
        # verify status reverted to pending
        r = requests.get(f"{API}/bills", headers=H(t1_tok), timeout=30)
        b = next(x for x in r.json() if x["id"] == bill_id)
        assert b["status"] == "pending"
        assert not b.get("rent_receipt_code")
        # Re-submit (service fee still considered paid because service_fee_paid_at is preserved)
        sub = requests.post(
            f"{API}/bills/{bill_id}/submit-rent-receipt",
            headers=H(t1_tok),
            json={"mpesa_receipt": "SGH7R5FINAL", "amount_paid": b["amount"]},
            timeout=30,
        )
        # If service_fee_paid_at was cleared in reject, this will be 400 — record but don't fail this test
        TestTwoStepRentFlow.resubmit_status = sub.status_code

    def test_caretaker_can_confirm(self, ck1_tok, t1_tok, mary_tok):
        bill_id = getattr(TestTwoStepRentFlow, "bill_id", None)
        if not bill_id:
            pytest.skip()
        # If resubmit failed (fee got cleared on reject), we cannot confirm; skip
        if getattr(TestTwoStepRentFlow, "resubmit_status", None) != 200:
            pytest.skip(f"resubmit after reject returned {getattr(TestTwoStepRentFlow, 'resubmit_status', None)}")
        conf = requests.post(f"{API}/bills/{bill_id}/confirm-rent-receipt", headers=H(ck1_tok), timeout=30)
        assert conf.status_code == 200, f"caretaker confirm failed: {conf.status_code} {conf.text}"
        # Verify paid
        r = requests.get(f"{API}/bills", headers=H(t1_tok), timeout=30)
        b = next(x for x in r.json() if x["id"] == bill_id)
        assert b["status"] in ("paid", "partial"), f"expected paid/partial, got {b['status']}"


# ============ Disbursement ledger ============

class TestDisbursements:
    def test_list_disbursements_admin(self, admin_tok):
        r = requests.get(f"{API}/admin/disbursements", headers=H(admin_tok), timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "items" in data and "summary" in data
        for k in ["pending_caretaker_total", "paid_caretaker_total", "platform_revenue_viewings"]:
            assert k in data["summary"]
        # If items exist, check shape
        for row in data["items"][:3]:
            assert row.get("kind") == "viewing_caretaker"
            assert row.get("caretaker_share") == 150
            assert row.get("platform_share") == 50

    def test_disbursements_landlord_forbidden(self, mary_tok):
        r = requests.get(f"{API}/admin/disbursements", headers=H(mary_tok), timeout=30)
        assert r.status_code in (401, 403)

    def test_mark_paid_admin_only(self, admin_tok, mary_tok):
        r = requests.get(f"{API}/admin/disbursements", headers=H(admin_tok), params={"status": "pending"}, timeout=30)
        assert r.status_code == 200
        items = r.json()["items"]
        if not items:
            pytest.skip("no pending disbursements to mark paid")
        disb_id = items[0]["id"]
        # Landlord blocked
        bad = requests.post(
            f"{API}/admin/disbursements/{disb_id}/mark-paid",
            headers=H(mary_tok),
            json={"mpesa_receipt": "TEST", "note": "TEST"},
            timeout=30,
        )
        assert bad.status_code in (401, 403)
        # Admin succeeds
        ok = requests.post(
            f"{API}/admin/disbursements/{disb_id}/mark-paid",
            headers=H(admin_tok),
            json={"mpesa_receipt": "TEST_R5_DISB", "note": "TEST_R5"},
            timeout=30,
        )
        assert ok.status_code == 200
        assert ok.json()["status"] == "paid"
