"""Phase 2/3/4 backend tests — community, yard-sale, leases, visitors, notifications, AI."""
import io
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = ("admin@nyumbaos.co.ke", "admin123")
LANDLORD = ("land@demo.com", "demo123")
CARETAKER = ("ck@demo.com", "care123")

UNIQ = uuid.uuid4().hex[:8]


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password})
    if r.status_code != 200:
        return None
    return r.json()["access_token"]


def _h(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- shared fixtures ----------

@pytest.fixture(scope="module")
def admin_token():
    t = _login(*ADMIN)
    if not t:
        pytest.skip("admin login failed")
    return t


@pytest.fixture(scope="module")
def landlord_token():
    t = _login(*LANDLORD)
    if not t:
        pytest.skip("landlord login failed")
    return t


@pytest.fixture(scope="module")
def caretaker_token():
    t = _login(*CARETAKER)
    if not t:
        pytest.skip("caretaker login failed")
    return t


@pytest.fixture(scope="module")
def landlord_property(landlord_token):
    """Return one of the landlord's owned properties (must exist from earlier seed)."""
    r = requests.get(f"{API}/properties", headers=_h(landlord_token))
    assert r.status_code == 200, r.text
    items = r.json()
    if not items:
        pytest.skip("no landlord property")
    # Must have a unit too — find first prop and ensure a unit
    return items[0]


@pytest.fixture(scope="module")
def landlord_unit(landlord_token, landlord_property):
    pid = landlord_property["id"]
    r = requests.get(f"{API}/units?property_id={pid}", headers=_h(landlord_token))
    assert r.status_code == 200, r.text
    units = r.json()
    vacant = [u for u in units if not u.get("tenant_id")]
    if vacant:
        return vacant[0]
    # create a fresh vacant unit
    u = requests.post(
        f"{API}/units",
        headers=_h(landlord_token),
        json={"property_id": pid, "unit_number": f"T{UNIQ[:4]}", "bedrooms": 1, "rent_amount": 15000},
    )
    assert u.status_code in (200, 201), u.text
    return u.json()


@pytest.fixture(scope="module")
def tenant_creds(landlord_token, landlord_unit):
    """Onboard a tenant to landlord_unit and return creds + login token."""
    email = f"TEST_tenant_{UNIQ}@demo.com"
    payload = {
        "full_name": "Test Tenant",
        "email": email,
        "phone": "254700111222",
        "password": "tenant123",
        "unit_id": landlord_unit["id"],
    }
    r = requests.post(f"{API}/tenants", headers=_h(landlord_token), json=payload)
    if r.status_code not in (200, 201):
        # Maybe unit already occupied — try to fetch tenant assigned to it
        if r.status_code == 400 and landlord_unit.get("tenant_id"):
            # find user by id
            return None
        pytest.skip(f"tenant onboard failed: {r.status_code} {r.text}")
    token = _login(email, "tenant123")
    assert token, "tenant login failed after onboard"
    return {"email": email, "password": "tenant123", "token": token}


# ---------- Phase 2: Announcements ----------

class TestAnnouncements:
    def test_landlord_post_property(self, landlord_token, landlord_property):
        files = {"attachments": ("hello.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 32, "image/png")}
        data = {"scope": "property", "title": f"TEST_ann_{UNIQ}", "body": "Hello tenants", "property_id": landlord_property["id"]}
        r = requests.post(f"{API}/announcements", headers=_h(landlord_token), data=data, files=files)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["scope"] == "property"
        assert body["title"].startswith("TEST_ann_")
        assert len(body["attachments"]) == 1
        # save id for next test
        TestAnnouncements.ann_id = body["id"]

    def test_landlord_cannot_post_global(self, landlord_token, landlord_property):
        data = {"scope": "global", "title": "nope", "body": "x"}
        r = requests.post(f"{API}/announcements", headers=_h(landlord_token), data=data)
        assert r.status_code == 403

    def test_admin_can_post_global(self, admin_token):
        data = {"scope": "global", "title": f"TEST_global_{UNIQ}", "body": "platform-wide"}
        r = requests.post(f"{API}/announcements", headers=_h(admin_token), data=data)
        assert r.status_code == 200, r.text
        assert r.json()["scope"] == "global"

    def test_image_too_large_rejected(self, landlord_token, landlord_property):
        big = b"\x89PNG" + b"\x00" * (6 * 1024 * 1024)
        files = {"attachments": ("big.png", big, "image/png")}
        data = {"scope": "property", "title": "big", "body": "x", "property_id": landlord_property["id"]}
        r = requests.post(f"{API}/announcements", headers=_h(landlord_token), data=data, files=files)
        assert r.status_code == 400, r.text

    def test_docx_rejected(self, landlord_token, landlord_property):
        files = {"attachments": ("doc.docx", b"junk", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        data = {"scope": "property", "title": "doc", "body": "x", "property_id": landlord_property["id"]}
        r = requests.post(f"{API}/announcements", headers=_h(landlord_token), data=data, files=files)
        assert r.status_code == 400, r.text

    def test_list_admin_sees_all(self, admin_token):
        r = requests.get(f"{API}/announcements", headers=_h(admin_token))
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        assert any(a["scope"] == "global" for a in items)
        assert any(a["scope"] == "property" for a in items)

    def test_pin_toggle_and_delete(self, landlord_token):
        # find a test announcement by this landlord
        r = requests.get(f"{API}/announcements", headers=_h(landlord_token))
        mine = [a for a in r.json() if a["title"].startswith("TEST_ann_") and a["scope"] == "property"]
        assert mine, "no landlord announcement found"
        ann_id = mine[0]["id"]
        p = requests.patch(f"{API}/announcements/{ann_id}/pin", headers=_h(landlord_token))
        assert p.status_code == 200, p.text
        assert "pinned" in p.json()
        # delete (author can delete)
        d = requests.delete(f"{API}/announcements/{ann_id}", headers=_h(landlord_token))
        assert d.status_code == 200, d.text


# ---------- Phase 2: Forum ----------

class TestForum:
    def test_landlord_creates_thread(self, landlord_token, landlord_property):
        data = {"property_id": landlord_property["id"], "title": f"TEST_thread_{UNIQ}", "body": "hello"}
        r = requests.post(f"{API}/forum/threads", headers=_h(landlord_token), data=data)
        assert r.status_code == 200, r.text
        TestForum.tid = r.json()["id"]

    def test_landlord_lists_own(self, landlord_token, landlord_property):
        r = requests.get(f"{API}/forum/threads?property_id={landlord_property['id']}", headers=_h(landlord_token))
        assert r.status_code == 200
        assert any(t["id"] == TestForum.tid for t in r.json())

    def test_admin_lists_all(self, admin_token):
        r = requests.get(f"{API}/forum/threads", headers=_h(admin_token))
        assert r.status_code == 200
        assert any(t["id"] == TestForum.tid for t in r.json())

    def test_landlord_reply_bumps_count(self, landlord_token):
        data = {"body": "self reply"}
        r = requests.post(f"{API}/forum/threads/{TestForum.tid}/replies", headers=_h(landlord_token), data=data)
        assert r.status_code == 200, r.text
        # verify replies_count
        g = requests.get(f"{API}/forum/threads/{TestForum.tid}", headers=_h(landlord_token))
        assert g.status_code == 200
        assert g.json()["thread"]["replies_count"] == 1
        assert g.json()["thread"]["last_reply_at"]

    def test_lock_and_locked_blocks_reply(self, landlord_token):
        m = requests.patch(
            f"{API}/forum/threads/{TestForum.tid}/moderate?locked=true",
            headers=_h(landlord_token),
        )
        assert m.status_code == 200, m.text
        assert m.json()["locked"] is True
        # non-admin author reply should now be 403
        r = requests.post(f"{API}/forum/threads/{TestForum.tid}/replies", headers=_h(landlord_token), data={"body": "x"})
        assert r.status_code == 403

    def test_delete_thread_cascades(self, landlord_token):
        d = requests.delete(f"{API}/forum/threads/{TestForum.tid}", headers=_h(landlord_token))
        assert d.status_code == 200


# ---------- Phase 3: Yard Sale ----------

class TestYardSale:
    def test_landlord_create_listing(self, landlord_token):
        data = {"title": f"TEST_listing_{UNIQ}", "description": "table", "price": "500", "category": "furniture"}
        r = requests.post(f"{API}/yard-sale/listings", headers=_h(landlord_token), data=data)
        assert r.status_code == 200, r.text
        TestYardSale.lid = r.json()["id"]

    def test_invalid_category_400(self, landlord_token):
        data = {"title": "bad", "price": "100", "category": "nuclear-waste"}
        r = requests.post(f"{API}/yard-sale/listings", headers=_h(landlord_token), data=data)
        assert r.status_code == 400

    def test_list_and_filter(self, landlord_token):
        r = requests.get(f"{API}/yard-sale/listings?category=furniture&max_price=1000", headers=_h(landlord_token))
        assert r.status_code == 200
        items = r.json()
        assert any(i["id"] == TestYardSale.lid for i in items)

    def test_update_listing(self, landlord_token):
        r = requests.patch(
            f"{API}/yard-sale/listings/{TestYardSale.lid}",
            headers=_h(landlord_token),
            json={"price": 450.0},
        )
        assert r.status_code == 200, r.text
        assert r.json()["price"] == 450.0

    def test_admin_can_edit_other(self, admin_token):
        r = requests.patch(
            f"{API}/yard-sale/listings/{TestYardSale.lid}",
            headers=_h(admin_token),
            json={"status": "sold"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "sold"

    def test_feature_payment_demo_flow(self, landlord_token):
        # create a fresh listing then feature it
        data = {"title": f"TEST_feat_{UNIQ}", "price": "200", "category": "electronics"}
        c = requests.post(f"{API}/yard-sale/listings", headers=_h(landlord_token), data=data)
        assert c.status_code == 200
        lid = c.json()["id"]
        f = requests.post(
            f"{API}/yard-sale/listings/{lid}/feature",
            headers=_h(landlord_token),
            data={"phone_number": "254712345678"},
        )
        assert f.status_code == 200, f.text
        assert f.json()["amount"] == 100
        # wait ~5s for demo callback
        time.sleep(6)
        g = requests.get(f"{API}/yard-sale/listings/{lid}", headers=_h(landlord_token))
        assert g.status_code == 200, g.text
        assert g.json()["featured"] is True, g.json()
        assert g.json()["featured_until"]
        TestYardSale.lid_feat = lid

    def test_cleanup_yardsale(self, landlord_token):
        for lid in [getattr(TestYardSale, "lid", None), getattr(TestYardSale, "lid_feat", None)]:
            if lid:
                requests.delete(f"{API}/yard-sale/listings/{lid}", headers=_h(landlord_token))


# ---------- Phase 4: Notifications ----------

class TestNotifications:
    def test_landlord_notifications_shape(self, landlord_token):
        r = requests.get(f"{API}/notifications", headers=_h(landlord_token))
        assert r.status_code == 200
        body = r.json()
        assert "items" in body and "unread_count" in body
        assert isinstance(body["items"], list)
        assert isinstance(body["unread_count"], int)

    def test_mark_all_read(self, landlord_token):
        r = requests.post(f"{API}/notifications/mark-all-read", headers=_h(landlord_token))
        assert r.status_code == 200
        # verify
        g = requests.get(f"{API}/notifications", headers=_h(landlord_token))
        assert g.json()["unread_count"] == 0


# ---------- Phase 4: Leases ----------

class TestLeases:
    def test_create_lease_requires_tenant(self, landlord_token, landlord_unit, tenant_creds):
        if tenant_creds is None:
            pytest.skip("tenant not provisioned")
        payload = {
            "tenant_id": _get_user_id(tenant_creds["token"]),
            "unit_id": landlord_unit["id"],
            "rent_amount": 15000,
            "deposit_amount": 15000,
            "start_date": "2026-02-01",
            "end_date": "2027-01-31",
            "terms": "Test terms",
        }
        r = requests.post(f"{API}/leases", headers=_h(landlord_token), json=payload)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "sent"
        assert body["pdf_path"]
        TestLeases.lid = body["id"]

    def test_tenant_sees_lease(self, tenant_creds):
        if tenant_creds is None:
            pytest.skip("no tenant")
        r = requests.get(f"{API}/leases", headers=_h(tenant_creds["token"]))
        assert r.status_code == 200
        assert any(le["id"] == TestLeases.lid for le in r.json())

    def test_tenant_sign(self, tenant_creds):
        if tenant_creds is None:
            pytest.skip("no tenant")
        r = requests.post(f"{API}/leases/{TestLeases.lid}/sign", headers=_h(tenant_creds["token"]))
        assert r.status_code == 200, r.text
        # cannot re-sign
        r2 = requests.post(f"{API}/leases/{TestLeases.lid}/sign", headers=_h(tenant_creds["token"]))
        assert r2.status_code == 400

    def test_cannot_cancel_signed(self, landlord_token):
        if not hasattr(TestLeases, "lid"):
            pytest.skip("no lease created")
        r = requests.delete(f"{API}/leases/{TestLeases.lid}", headers=_h(landlord_token))
        assert r.status_code == 400


# ---------- Phase 4: Visitor passes ----------

class TestVisitors:
    def test_tenant_create_pass(self, tenant_creds):
        if tenant_creds is None:
            pytest.skip("no tenant")
        r = requests.post(
            f"{API}/visitor-passes",
            headers=_h(tenant_creds["token"]),
            json={"visitor_name": "Guest", "visitor_phone": "254700111000", "expected_time": "evening"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["qr_data_url"].startswith("data:image/png;base64,")
        assert body["expires_at"]
        TestVisitors.token = body["token"]
        TestVisitors.pid = body["id"]

    def test_caretaker_scan(self, caretaker_token, tenant_creds):
        if tenant_creds is None or not hasattr(TestVisitors, "token"):
            pytest.skip("no visitor pass")
        r = requests.post(f"{API}/visitor-passes/scan/{TestVisitors.token}", headers=_h(caretaker_token))
        # Caretaker must belong to same landlord
        if r.status_code == 403:
            pytest.skip("caretaker not assigned to landlord")
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "used"

    def test_double_scan_400(self, caretaker_token):
        if not hasattr(TestVisitors, "token"):
            pytest.skip("no token")
        r = requests.post(f"{API}/visitor-passes/scan/{TestVisitors.token}", headers=_h(caretaker_token))
        assert r.status_code in (400, 403)


# ---------- Phase 4: AI Recommend ----------

class TestAI:
    def test_recommend_returns_structure(self, landlord_token):
        r = requests.post(
            f"{API}/ai/recommend-properties",
            headers=_h(landlord_token),
            json={"max_rent": 100000, "preferred_bedrooms": None},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "items" in body and "used_llm" in body and "message" in body
        assert isinstance(body["items"], list)
        for it in body["items"]:
            assert "listing_id" in it and "rationale" in it


# ---------- helpers ----------

def _get_user_id(token):
    r = requests.get(f"{API}/auth/me", headers=_h(token))
    assert r.status_code == 200
    return r.json()["id"]
