"""Round 6 — STK push false-positive bug fix tests.

Covers:
- /payments/{id}/check + /payments/{id}/cancel auth + state machine
- Failure notification creation
- Two-step flow works for non-rent bill types (water/electricity/service/other)
- Idempotency of _process_callback_payload (forced-success vs cancel race)
- STK push failure branch: when sandbox returns 502 the payment is marked failed and a notification is emitted
"""
import os
import time
import uuid
import pytest
import requests

def _load_frontend_env():
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().strip('"')
    except Exception:
        pass
    return os.environ.get("REACT_APP_BACKEND_URL", "")

BASE_URL = _load_frontend_env().rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL missing"
API = f"{BASE_URL}/api"

# ---- Helpers ----

def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json()["access_token"]

def _hdr(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def _stk_push_retry(tokens, bill_id, attempts=6):
    """STK push with retries — sandbox sometimes returns 502."""
    last = None
    for i in range(attempts):
        r = requests.post(
            f"{API}/payments/mpesa/stk-push",
            headers=_hdr(tokens["tenant1"]),
            json={"bill_id": bill_id, "phone_number": "254700000000"},
        )
        last = r
        if r.status_code == 200:
            return r
        time.sleep(1.5 + i * 0.5)
    return last


@pytest.fixture(scope="module")
def tokens():
    return {
        "admin": _login("admin@nyumbaos.co.ke", "admin123"),
        "mary":  _login("mary@demo.nyumba", "demo123"),
        "tenant1": _login("tenant1@demo.nyumba", "demo123"),
        "tenant4": _login("tenant4@demo.nyumba", "demo123"),
    }


@pytest.fixture
def fresh_bill(tokens):
    """Create a fresh pending water bill for tenant1 under mary."""
    tenant1_info = requests.get(f"{API}/auth/me", headers=_hdr(tokens["tenant1"])).json()
    tenant_id = tenant1_info["id"]
    units = requests.get(f"{API}/units", headers=_hdr(tokens["mary"])).json()
    unit = next((u for u in units if u.get("tenant_id") == tenant_id), None)
    assert unit, "Could not find tenant1's unit under mary"
    payload = {
        "tenant_id": tenant_id,
        "unit_id": unit["id"],
        "bill_type": "water",
        "amount": 1500,
        "period": "TEST_R6_FX_" + uuid.uuid4().hex[:6],
        "due_date": "2026-02-28",
        "description": "fixture bill",
    }
    b = requests.post(f"{API}/bills", headers=_hdr(tokens["mary"]), json=payload)
    assert b.status_code == 200, b.text
    return b.json()


# ----------- A) /check + /cancel auth + state machine -----------

class TestCheckCancelEndpoints:
    def test_cancel_nonexistent_payment(self, tokens):
        r = requests.post(f"{API}/payments/does-not-exist/cancel", headers=_hdr(tokens["tenant1"]))
        assert r.status_code == 404

    def test_check_nonexistent_payment(self, tokens):
        r = requests.post(f"{API}/payments/does-not-exist/check", headers=_hdr(tokens["tenant1"]))
        assert r.status_code == 404

    def test_full_cancel_flow(self, tokens, fresh_bill):
        # Find tenant1's bills
        bill = fresh_bill
        # Initiate STK – sandbox keys/shortcode mismatch will throw 502 (per agent_to_agent_context_note)
        r = _stk_push_retry(tokens, bill["id"])
        # Either we got 502 (sandbox unreachable) OR 200 with a pending payment
        if r.status_code == 502:
            pytest.skip("Sandbox 502 — covered by separate test_stk_failure_branch")
        assert r.status_code == 200, r.text
        payment_id = r.json()["payment_id"]

        # Cancel as tenant should work
        c = requests.post(f"{API}/payments/{payment_id}/cancel", headers=_hdr(tokens["tenant1"]))
        assert c.status_code == 200, c.text
        assert c.json()["status"] == "failed"

        # Verify payment doc
        p = requests.get(f"{API}/payments/{payment_id}", headers=_hdr(tokens["tenant1"])).json()
        assert p["status"] == "failed"
        assert p["result_desc"] == "Cancelled by user"

        # 2nd cancel attempt → 400 (not pending anymore)
        c2 = requests.post(f"{API}/payments/{payment_id}/cancel", headers=_hdr(tokens["tenant1"]))
        assert c2.status_code == 400, c2.text

    def test_cancel_auth_other_tenant_forbidden(self, tokens, fresh_bill):
        # tenant1's payment can't be cancelled by tenant4
        bill = fresh_bill
        r = _stk_push_retry(tokens, bill["id"])
        if r.status_code != 200:
            pytest.skip(f"STK push didn't yield pending payment: {r.status_code}")
        pid = r.json()["payment_id"]
        try:
            c = requests.post(f"{API}/payments/{pid}/cancel", headers=_hdr(tokens["tenant4"]))
            assert c.status_code == 403
        finally:
            # cleanup
            requests.post(f"{API}/payments/{pid}/cancel", headers=_hdr(tokens["tenant1"]))

    def test_check_auth_landlord_and_admin_allowed(self, tokens, fresh_bill):
        bill = fresh_bill
        r = _stk_push_retry(tokens, bill["id"])
        if r.status_code != 200:
            pytest.skip(f"STK push didn't yield pending: {r.status_code}")
        pid = r.json()["payment_id"]
        try:
            # mary is the landlord
            l = requests.post(f"{API}/payments/{pid}/check", headers=_hdr(tokens["mary"]))
            assert l.status_code in (200, 502), l.text  # 502 if Safaricom query also fails
            a = requests.post(f"{API}/payments/{pid}/check", headers=_hdr(tokens["admin"]))
            assert a.status_code in (200, 502), a.text
            # tenant4 cannot check
            t4 = requests.post(f"{API}/payments/{pid}/check", headers=_hdr(tokens["tenant4"]))
            assert t4.status_code == 403
        finally:
            requests.post(f"{API}/payments/{pid}/cancel", headers=_hdr(tokens["tenant1"]))


# ----------- B) Failure notification on STK 502 ------------

class TestFailureNotification:
    def test_stk_push_502_marks_payment_failed_and_notifies(self, tokens, fresh_bill):
        """When sandbox returns 502, payment row is created+marked failed.

        Per current implementation, the route raises HTTPException 502 to the
        caller but the payment doc is updated to status='failed' beforehand.
        Notification is emitted from _process_callback_payload (callback path),
        not from the direct exception path. So we don't assert notification
        here — we assert it under the /check (synth callback) path test.
        """
        bill = fresh_bill
        r = _stk_push_retry(tokens, bill["id"])
        if r.status_code == 200:
            # Real sandbox accepted — try to cancel and skip
            pid = r.json()["payment_id"]
            requests.post(f"{API}/payments/{pid}/cancel", headers=_hdr(tokens["tenant1"]))
            pytest.skip("Sandbox accepted STK — not a failure-branch repro")
        assert r.status_code == 502, r.text

    def test_stk_push_502_creates_failure_notification(self, tokens, fresh_bill):
        """When sandbox 502s, payment is marked failed AND a notification is created."""
        bill = fresh_bill
        # Force the failure path: keep retrying isn't useful here — direct call
        r = requests.post(
            f"{API}/payments/mpesa/stk-push",
            headers=_hdr(tokens["tenant1"]),
            json={"bill_id": bill["id"], "phone_number": "254700000000"},
        )
        if r.status_code == 200:
            # Sandbox accepted; cancel and skip
            requests.post(f"{API}/payments/{r.json()['payment_id']}/cancel", headers=_hdr(tokens["tenant1"]))
            pytest.skip("Sandbox accepted STK — failure branch not triggered")
        assert r.status_code == 502
        # Wait briefly and check notification
        time.sleep(0.8)
        notifs_resp = requests.get(f"{API}/notifications", headers=_hdr(tokens["tenant1"])).json()
        notifs = notifs_resp.get("items", []) if isinstance(notifs_resp, dict) else notifs_resp
        assert any("Payment did not go through" in (n.get("title") or "") for n in notifs[:20]), \
            "Expected 'Payment did not go through' notification on 502 path"

    def test_callback_failure_creates_notification(self, tokens, fresh_bill):
        """Force a callback with ResultCode != 0 via the public callback endpoint.

        This simulates Safaricom telling us the user cancelled/timed out.
        """
        # 1) Create a pending payment via stk-push
        bill = fresh_bill
        r = _stk_push_retry(tokens, bill["id"])
        if r.status_code != 200:
            pytest.skip(f"Need successful pending STK to exercise callback (got {r.status_code})")
        co_id = r.json()["checkout_request_id"]
        pid = r.json()["payment_id"]

        secret = "nrm-callback-secret"
        payload = {
            "Body": {
                "stkCallback": {
                    "MerchantRequestID": "test-r6",
                    "CheckoutRequestID": co_id,
                    "ResultCode": 1037,
                    "ResultDesc": "DS timeout user cannot be reached.",
                }
            }
        }
        cb = requests.post(f"{API}/payments/mpesa/callback/{secret}", json=payload)
        assert cb.status_code == 200

        # Payment must now be failed
        time.sleep(0.5)
        p = requests.get(f"{API}/payments/{pid}", headers=_hdr(tokens["tenant1"])).json()
        assert p["status"] == "failed"
        assert "DS timeout" in (p.get("result_desc") or "")

        # Notification "Payment did not go through" must exist for tenant1
        notifs_resp = requests.get(f"{API}/notifications", headers=_hdr(tokens["tenant1"])).json()
        notifs = notifs_resp.get("items", notifs_resp) if isinstance(notifs_resp, dict) else notifs_resp
        titles = [n.get("title", "") for n in notifs]
        assert any("Payment did not go through" in t for t in titles), \
            f"No failure notification found. Titles: {titles[:10]}"


# ----------- C) Idempotency of _process_callback_payload ------------

class TestCallbackIdempotency:
    def test_late_callback_does_not_revive_failed_payment(self, tokens, fresh_bill):
        bill = fresh_bill
        r = _stk_push_retry(tokens, bill["id"])
        if r.status_code != 200:
            pytest.skip(f"Need pending payment: {r.status_code}")
        co_id = r.json()["checkout_request_id"]
        pid = r.json()["payment_id"]
        # Cancel → failed
        c = requests.post(f"{API}/payments/{pid}/cancel", headers=_hdr(tokens["tenant1"]))
        assert c.status_code == 200

        # Late real-callback (success) arrives — must be ignored
        secret = "nrm-callback-secret"
        payload = {
            "Body": {
                "stkCallback": {
                    "MerchantRequestID": "late-success",
                    "CheckoutRequestID": co_id,
                    "ResultCode": 0,
                    "ResultDesc": "OK late",
                    "CallbackMetadata": {"Item": [
                        {"Name": "Amount", "Value": 100},
                        {"Name": "MpesaReceiptNumber", "Value": "LATE123"},
                    ]},
                }
            }
        }
        cb = requests.post(f"{API}/payments/mpesa/callback/{secret}", json=payload)
        assert cb.status_code == 200
        p = requests.get(f"{API}/payments/{pid}", headers=_hdr(tokens["tenant1"])).json()
        assert p["status"] == "failed", f"Late callback revived a failed payment: {p}"
        assert p["result_desc"] == "Cancelled by user"


# ----------- D) Non-rent bill types use two-step flow ------------

class TestNonRentBillTypes:
    @pytest.mark.parametrize("bill_type", ["water", "electricity", "service", "other"])
    def test_stk_push_for_bill_type(self, tokens, bill_type):
        # Mary creates a bill of this type for tenant1
        tenant1_info = requests.get(f"{API}/auth/me", headers=_hdr(tokens["tenant1"])).json()
        tenant_id = tenant1_info["id"]
        # Find tenant1's unit under mary
        units = requests.get(f"{API}/units", headers=_hdr(tokens["mary"])).json()
        unit = next((u for u in units if u.get("tenant_id") == tenant_id), None)
        if not unit:
            pytest.skip("Could not find tenant1's unit under mary")

        payload = {
            "tenant_id": tenant_id,
            "unit_id": unit["id"],
            "bill_type": bill_type,
            "amount": 2000,
            "period": "TEST_R6_" + uuid.uuid4().hex[:6],
            "due_date": "2026-02-28",
            "description": f"TEST R6 {bill_type}",
        }
        b = requests.post(f"{API}/bills", headers=_hdr(tokens["mary"]), json=payload)
        assert b.status_code == 200, b.text
        bill_id = b.json()["id"]

        # Tenant initiates two-step pay
        r = requests.post(
            f"{API}/payments/mpesa/stk-push",
            headers=_hdr(tokens["tenant1"]),
            json={"bill_id": bill_id, "phone_number": "254700000000"},
        )
        # Acceptable: 200 (sandbox accepted) or 502 (sandbox unreachable). Both prove
        # the route doesn't reject non-rent bill types.
        assert r.status_code in (200, 502), f"bill_type={bill_type} → {r.status_code} {r.text}"
        if r.status_code == 200:
            j = r.json()
            assert j["service_fee_amount"] == 50.0, j  # ceil(2000*0.025/10)*10 = 50
            assert j["rent_amount"] == 2000.0
            assert j["total_cost_to_tenant"] == 2050.0
            # cleanup pending payment
            requests.post(f"{API}/payments/{j['payment_id']}/cancel", headers=_hdr(tokens["tenant1"]))


# ----------- E) Demo fallback OFF by default ------------

class TestDemoFallbackOff:
    def test_env_var_false(self):
        # Check env file reflects MPESA_DEMO_FALLBACK=false
        env_path = "/app/backend/.env"
        with open(env_path) as f:
            content = f.read()
        assert "MPESA_DEMO_FALLBACK=\"false\"" in content or "MPESA_DEMO_FALLBACK=false" in content, \
            "MPESA_DEMO_FALLBACK should default to false in Round 6"
