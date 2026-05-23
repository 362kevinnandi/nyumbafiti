"""Admin endpoint tests - super-admin role, commission, suspend, refund, payouts."""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback to read frontend/.env
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


# -------- helpers / fixtures --------

@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    data = r.json()
    assert data["user"]["role"] == "admin"
    return data["access_token"]


@pytest.fixture(scope="module")
def landlord_token():
    r = requests.post(f"{API}/auth/login", json={"email": LANDLORD_EMAIL, "password": LANDLORD_PASSWORD})
    assert r.status_code == 200, f"Landlord login failed: {r.text}"
    return r.json()["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# -------- Admin seed + auth --------

class TestAdminSeedAndAuth:
    def test_admin_login_succeeds(self):
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert r.status_code == 200
        body = r.json()
        assert body["user"]["role"] == "admin"
        assert body["user"]["email"] == ADMIN_EMAIL

    def test_register_admin_role_rejected(self):
        r = requests.post(f"{API}/auth/register", json={
            "email": f"hacker_{uuid.uuid4().hex[:6]}@x.com",
            "full_name": "Hacker",
            "phone": "254700111222",
            "role": "admin",
            "password": "abcdef",
        })
        assert r.status_code == 400


# -------- Settings --------

class TestAdminSettings:
    def test_get_settings_admin_only(self, admin_token, landlord_token):
        r = requests.get(f"{API}/admin/settings", headers=auth(admin_token))
        assert r.status_code == 200
        assert "commission_rate" in r.json()

        r2 = requests.get(f"{API}/admin/settings", headers=auth(landlord_token))
        assert r2.status_code == 403

    def test_update_settings_persists(self, admin_token):
        # get current
        cur = requests.get(f"{API}/admin/settings", headers=auth(admin_token)).json()
        original = cur.get("commission_rate", 0.035)

        # set to 0.05
        r = requests.patch(f"{API}/admin/settings", json={"commission_rate": 0.05}, headers=auth(admin_token))
        assert r.status_code == 200
        assert r.json()["commission_rate"] == 0.05

        # reload
        r2 = requests.get(f"{API}/admin/settings", headers=auth(admin_token))
        assert r2.json()["commission_rate"] == 0.05

        # restore
        requests.patch(f"{API}/admin/settings", json={"commission_rate": original}, headers=auth(admin_token))

    def test_update_settings_invalid_rate(self, admin_token):
        r = requests.patch(f"{API}/admin/settings", json={"commission_rate": 0.7}, headers=auth(admin_token))
        assert r.status_code == 400

        r2 = requests.patch(f"{API}/admin/settings", json={"commission_rate": -0.1}, headers=auth(admin_token))
        assert r2.status_code == 400


# -------- Stats --------

class TestAdminStats:
    def test_stats_admin_only(self, admin_token, landlord_token):
        r = requests.get(f"{API}/admin/stats", headers=auth(admin_token))
        assert r.status_code == 200
        data = r.json()
        for key in [
            "users_by_role", "properties", "units",
            "total_gross_processed", "total_commission_earned",
            "total_net_to_landlords", "current_commission_rate", "by_purpose"
        ]:
            assert key in data, f"missing {key}"
        assert isinstance(data["users_by_role"], dict)
        assert "admin" in data["users_by_role"]

        r2 = requests.get(f"{API}/admin/stats", headers=auth(landlord_token))
        assert r2.status_code == 403


# -------- Users + suspend --------

class TestAdminUsersAndSuspend:
    def test_list_users_strips_password_hash(self, admin_token):
        r = requests.get(f"{API}/admin/users", headers=auth(admin_token))
        assert r.status_code == 200
        users = r.json()
        assert isinstance(users, list) and len(users) > 0
        for u in users:
            assert "password_hash" not in u

    def test_list_users_role_filter(self, admin_token):
        r = requests.get(f"{API}/admin/users?role=landlord", headers=auth(admin_token))
        assert r.status_code == 200
        for u in r.json():
            assert u["role"] == "landlord"

    def test_admin_cannot_suspend_self(self, admin_token):
        admin_me = requests.get(f"{API}/auth/me", headers=auth(admin_token)).json()
        r = requests.patch(
            f"{API}/admin/users/{admin_me['id']}/suspend",
            json={"suspended": True}, headers=auth(admin_token)
        )
        assert r.status_code == 400

    def test_suspend_blocks_login_then_reactivate(self, admin_token):
        # create a fresh landlord
        email = f"test_suspend_{uuid.uuid4().hex[:6]}@x.com"
        password = "abcdef"
        reg = requests.post(f"{API}/auth/register", json={
            "email": email, "full_name": "Suspend Me",
            "phone": "254700333444", "role": "landlord", "password": password,
        })
        assert reg.status_code == 200
        new_token = reg.json()["access_token"]
        new_id_ = reg.json()["user"]["id"]

        # verify can call API
        me1 = requests.get(f"{API}/auth/me", headers=auth(new_token))
        assert me1.status_code == 200

        # admin suspends
        s = requests.patch(
            f"{API}/admin/users/{new_id_}/suspend",
            json={"suspended": True}, headers=auth(admin_token)
        )
        assert s.status_code == 200

        # login now blocked
        l = requests.post(f"{API}/auth/login", json={"email": email, "password": password})
        assert l.status_code == 403
        assert "suspend" in l.text.lower()

        # existing token should also be blocked (403)
        me2 = requests.get(f"{API}/auth/me", headers=auth(new_token))
        assert me2.status_code == 403

        # reactivate
        r2 = requests.patch(
            f"{API}/admin/users/{new_id_}/suspend",
            json={"suspended": False}, headers=auth(admin_token)
        )
        assert r2.status_code == 200

        # login again
        l2 = requests.post(f"{API}/auth/login", json={"email": email, "password": password})
        assert l2.status_code == 200


# -------- Commission on viewing payment --------

class TestCommissionOnPayment:
    def test_viewing_payment_records_commission(self, admin_token):
        # ensure commission rate is 3.5%
        requests.patch(f"{API}/admin/settings", json={"commission_rate": 0.035}, headers=auth(admin_token))

        # find a vacant unit from public listings
        listings = requests.get(f"{API}/public/listings").json()
        assert len(listings) > 0, "No public listings - cannot test commission flow"
        unit_id = listings[0]["id"]

        # book a viewing
        prospect_email = f"prospect_{uuid.uuid4().hex[:6]}@x.com"
        book = requests.post(f"{API}/public/viewings", json={
            "unit_id": unit_id,
            "prospect_name": "Test Prospect",
            "prospect_email": prospect_email,
            "prospect_phone": "254700555666",
            "scheduled_date": "2026-12-15",
            "scheduled_time": "10:00",
            "notes": "commission test",
        })
        assert book.status_code == 200, book.text
        body = book.json()
        viewing_id = body["viewing_id"]

        # wait for demo callback (~4s)
        time.sleep(7)

        # check viewing status via public endpoint
        v = requests.get(f"{API}/public/viewings/{viewing_id}").json()
        assert v["status"] == "scheduled", f"viewing not scheduled: {v}"

        # admin pulls payments and finds this viewing's payment
        payments = requests.get(
            f"{API}/admin/payments?purpose=viewing_fee&status=succeeded",
            headers=auth(admin_token),
        ).json()
        match = [p for p in payments if p.get("viewing_id") == viewing_id]
        assert match, f"No payment found for viewing {viewing_id}"
        p = match[0]
        assert p["amount"] == 200
        assert p["commission_amount"] == 7.00
        assert p["net_to_landlord"] == 193.00
        assert p["commission_rate"] == 0.035


# -------- Payments listing + refund --------

class TestAdminPaymentsAndRefund:
    def test_list_payments_enriched(self, admin_token):
        r = requests.get(f"{API}/admin/payments?status=succeeded", headers=auth(admin_token))
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        if items:
            assert "landlord_name" in items[0]

    def test_refund_only_succeeded(self, admin_token):
        # pick a pending or failed payment if any → must reject
        all_payments = requests.get(f"{API}/admin/payments", headers=auth(admin_token)).json()
        not_succeeded = [p for p in all_payments if p["status"] not in ("succeeded", "refunded")]
        if not_succeeded:
            pid = not_succeeded[0]["id"]
            r = requests.post(
                f"{API}/admin/payments/{pid}/refund",
                json={"reason": "test"}, headers=auth(admin_token)
            )
            assert r.status_code == 400

    def test_refund_succeeded_viewing_payment(self, admin_token):
        succeeded = requests.get(
            f"{API}/admin/payments?purpose=viewing_fee&status=succeeded",
            headers=auth(admin_token),
        ).json()
        if not succeeded:
            pytest.skip("No succeeded viewing payment to refund")
        p = succeeded[-1]  # use the latest one we created
        r = requests.post(
            f"{API}/admin/payments/{p['id']}/refund",
            json={"reason": "test refund"}, headers=auth(admin_token)
        )
        assert r.status_code == 200

        # confirm payment status updated
        check = requests.get(f"{API}/admin/payments", headers=auth(admin_token)).json()
        refunded = [x for x in check if x["id"] == p["id"]][0]
        assert refunded["status"] == "refunded"

        # confirm viewing cancelled
        if p.get("viewing_id"):
            v = requests.get(f"{API}/public/viewings/{p['viewing_id']}").json()
            assert v["status"] == "cancelled"


# -------- Payouts --------

class TestAdminPayouts:
    def test_payouts_aggregation(self, admin_token):
        r = requests.get(f"{API}/admin/payouts", headers=auth(admin_token))
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list)
        for row in rows:
            for k in [
                "landlord_id", "landlord_name", "gross_earned",
                "commission_taken", "net_owed_total", "already_paid_out", "balance_owed"
            ]:
                assert k in row
        # sorted by balance_owed desc
        if len(rows) >= 2:
            for i in range(len(rows) - 1):
                assert rows[i]["balance_owed"] >= rows[i + 1]["balance_owed"]

    def test_mark_paid_and_history(self, admin_token):
        payouts = requests.get(f"{API}/admin/payouts", headers=auth(admin_token)).json()
        candidate = next((p for p in payouts if p["balance_owed"] > 0), None)
        if not candidate:
            pytest.skip("No landlord with balance owed - skipping mark-paid")

        landlord_id = candidate["landlord_id"]
        before_paid = candidate["already_paid_out"]
        before_balance = candidate["balance_owed"]
        amount = min(10.0, before_balance)

        r = requests.post(
            f"{API}/admin/payouts/{landlord_id}/mark-paid",
            json={"amount": amount, "note": "test payout"},
            headers=auth(admin_token),
        )
        assert r.status_code == 200
        payout = r.json()
        assert payout["amount"] == amount
        assert payout["landlord_id"] == landlord_id

        # re-fetch payouts - already_paid_out should have increased
        after = requests.get(f"{API}/admin/payouts", headers=auth(admin_token)).json()
        after_row = next(p for p in after if p["landlord_id"] == landlord_id)
        assert round(after_row["already_paid_out"] - before_paid, 2) >= amount - 0.01

        # history endpoint includes it
        hist = requests.get(f"{API}/admin/payouts/history", headers=auth(admin_token)).json()
        assert any(h["id"] == payout["id"] for h in hist)
        assert any("landlord_name" in h for h in hist)

    def test_mark_paid_invalid_amount(self, admin_token):
        payouts = requests.get(f"{API}/admin/payouts", headers=auth(admin_token)).json()
        if not payouts:
            pytest.skip("No payouts to test")
        landlord_id = payouts[0]["landlord_id"]
        r = requests.post(
            f"{API}/admin/payouts/{landlord_id}/mark-paid",
            json={"amount": 0, "note": ""}, headers=auth(admin_token)
        )
        assert r.status_code == 400


# -------- Properties --------

class TestAdminProperties:
    def test_list_properties(self, admin_token):
        r = requests.get(f"{API}/admin/properties", headers=auth(admin_token))
        assert r.status_code == 200
        props = r.json()
        assert isinstance(props, list)
        if props:
            assert "landlord_name" in props[0]
            assert "units_count" in props[0]
