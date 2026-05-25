"""Phase 1 Property Foundations - backend tests
Covers: PropertyCategory, multipart create with images, PATCH (admin featured flag,
landlord ownership), DELETE cascade, /public/listings category filter + featured sort,
/public/listings/{unit_id} response fields, admin /properties.
"""
import io
import os
import uuid
import pytest
import requests
from PIL import Image

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@nyumbaos.co.ke"
ADMIN_PASSWORD = "admin123"
LANDLORD_EMAIL = "land@demo.com"
LANDLORD_PASSWORD = "demo123"

CATEGORIES = ("apartment", "bedsitter", "single_room", "self_contained",
              "standalone", "compound", "airbnb")


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=10)
    assert r.status_code == 200, f"Login failed {email}: {r.text}"
    return r.json()["access_token"]


def _png_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), color="red").save(buf, format="PNG")
    return buf.getvalue()


# ------------- Fixtures -------------
@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def landlord_token():
    # ensure landlord exists
    requests.post(f"{API}/auth/register", json={
        "email": LANDLORD_EMAIL, "password": LANDLORD_PASSWORD,
        "full_name": "Demo Landlord", "phone": "254700000001", "role": "landlord",
    }, timeout=10)
    return _login(LANDLORD_EMAIL, LANDLORD_PASSWORD)


@pytest.fixture(scope="module")
def landlord2_token():
    email = f"TEST_landlord2_{uuid.uuid4().hex[:6]}@demo.com"
    requests.post(f"{API}/auth/register", json={
        "email": email, "password": "demo123",
        "full_name": "TEST L2", "phone": "254700000002", "role": "landlord",
    }, timeout=10)
    return _login(email, "demo123")


def _headers(tok):
    return {"Authorization": f"Bearer {tok}"}


# ----------- Create property -----------
class TestCreateProperty:
    def test_create_property_multipart_with_image_and_category(self, landlord_token):
        files = [
            ("images", ("a.png", _png_bytes(), "image/png")),
            ("images", ("b.png", _png_bytes(), "image/png")),
        ]
        data = {"name": f"TEST_Prop_{uuid.uuid4().hex[:6]}", "address": "Westlands",
                "description": "Phase1 test", "category": "bedsitter"}
        r = requests.post(f"{API}/properties", data=data, files=files,
                          headers=_headers(landlord_token), timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["category"] == "bedsitter"
        assert body["featured"] is False
        assert isinstance(body["images"], list)
        assert len(body["images"]) == 2
        assert body["images"][0].startswith("uploads/properties/")

        # persisted
        rl = requests.get(f"{API}/properties", headers=_headers(landlord_token), timeout=10)
        ids = [p["id"] for p in rl.json()]
        assert body["id"] in ids
        pytest.shared_prop_id = body["id"]
        pytest.shared_prop_image = body["images"][0]

    def test_create_property_invalid_category_returns_400(self, landlord_token):
        data = {"name": "TEST_bad", "address": "x", "category": "mansion"}
        r = requests.post(f"{API}/properties", data=data,
                          headers=_headers(landlord_token), timeout=10)
        assert r.status_code == 400, r.text
        assert "Invalid category" in r.text

    def test_create_property_defaults_to_apartment_when_category_omitted(self, landlord_token):
        data = {"name": f"TEST_default_{uuid.uuid4().hex[:6]}", "address": "x"}
        r = requests.post(f"{API}/properties", data=data,
                          headers=_headers(landlord_token), timeout=10)
        assert r.status_code == 200
        assert r.json()["category"] == "apartment"

    def test_image_url_is_accessible_via_backend(self, landlord_token):
        # uses prop_image from first test. Images must be served via /api/uploads
        # so they go through K8s ingress to backend (not the frontend SPA).
        img = pytest.shared_prop_image
        url = f"{BASE_URL}/api/{img}"
        r = requests.get(url, timeout=10)
        assert r.status_code == 200, f"Static file not served: {url} -> {r.status_code}"
        assert r.headers.get("content-type", "").startswith("image/")


# ----------- PATCH property -----------
class TestUpdateProperty:
    def test_landlord_can_edit_own(self, landlord_token):
        pid = pytest.shared_prop_id
        r = requests.patch(f"{API}/properties/{pid}",
                           json={"name": "TEST_Renamed", "category": "airbnb"},
                           headers=_headers(landlord_token), timeout=10)
        assert r.status_code == 200, r.text
        assert r.json()["name"] == "TEST_Renamed"
        assert r.json()["category"] == "airbnb"

    def test_landlord_featured_field_silently_ignored(self, landlord_token):
        pid = pytest.shared_prop_id
        r = requests.patch(f"{API}/properties/{pid}",
                           json={"featured": True},
                           headers=_headers(landlord_token), timeout=10)
        assert r.status_code == 200, r.text
        assert r.json()["featured"] is False  # landlord cannot set featured

    def test_non_owner_landlord_gets_404(self, landlord2_token):
        pid = pytest.shared_prop_id
        r = requests.patch(f"{API}/properties/{pid}",
                           json={"name": "hijack"},
                           headers=_headers(landlord2_token), timeout=10)
        assert r.status_code == 404, r.text

    def test_admin_can_set_featured_and_edit_anyone(self, admin_token):
        pid = pytest.shared_prop_id
        r = requests.patch(f"{API}/properties/{pid}",
                           json={"featured": True, "category": "apartment"},
                           headers=_headers(admin_token), timeout=10)
        assert r.status_code == 200, r.text
        assert r.json()["featured"] is True
        assert r.json()["category"] == "apartment"

    def test_admin_invalid_category_400(self, admin_token):
        pid = pytest.shared_prop_id
        r = requests.patch(f"{API}/properties/{pid}",
                           json={"category": "villa"},
                           headers=_headers(admin_token), timeout=10)
        # Pydantic Literal validation kicks in first -> 422; manual check in handler -> 400.
        # Either rejection is acceptable.
        assert r.status_code in (400, 422)


# ----------- Public listings -----------
class TestPublicListings:
    @pytest.fixture(scope="class")
    def featured_setup(self, admin_token, landlord_token):
        """Create a property + unit, admin-approves it, makes it featured. Plus a non-featured one."""
        # Featured property
        r = requests.post(f"{API}/properties",
                          data={"name": f"TEST_FEAT_{uuid.uuid4().hex[:6]}",
                                "address": "Kileleshwa", "category": "compound"},
                          files=[("images", ("a.png", _png_bytes(), "image/png"))],
                          headers=_headers(landlord_token), timeout=15)
        feat_pid = r.json()["id"]
        # Non-featured
        r2 = requests.post(f"{API}/properties",
                           data={"name": f"TEST_NORM_{uuid.uuid4().hex[:6]}",
                                 "address": "Kilimani", "category": "apartment"},
                           headers=_headers(landlord_token), timeout=15)
        norm_pid = r2.json()["id"]
        # Create one unit each
        u1 = requests.post(f"{API}/units",
                           json={"property_id": feat_pid, "unit_number": "F1",
                                 "rent_amount": 50000, "bedrooms": 2},
                           headers=_headers(landlord_token), timeout=10).json()
        u2 = requests.post(f"{API}/units",
                           json={"property_id": norm_pid, "unit_number": "N1",
                                 "rent_amount": 15000, "bedrooms": 1},
                           headers=_headers(landlord_token), timeout=10).json()
        # Admin approves both & features one
        for pid in (feat_pid, norm_pid):
            requests.post(f"{API}/admin/approvals/property/{pid}",
                          json={"approve": True},
                          headers=_headers(admin_token), timeout=10)
        requests.patch(f"{API}/properties/{feat_pid}",
                       json={"featured": True},
                       headers=_headers(admin_token), timeout=10)
        return {"feat_pid": feat_pid, "norm_pid": norm_pid,
                "feat_uid": u1["id"], "norm_uid": u2["id"]}

    def test_public_listings_returns_category_featured(self, featured_setup):
        r = requests.get(f"{API}/public/listings", timeout=10)
        assert r.status_code == 200
        items = r.json()
        assert len(items) >= 2
        sample = items[0]
        assert "category" in sample
        assert "featured" in sample
        assert "property" in sample
        assert "category" in sample["property"]
        assert "featured" in sample["property"]
        assert "images" in sample["property"]

    def test_featured_sorts_first(self, featured_setup):
        r = requests.get(f"{API}/public/listings", timeout=10)
        items = r.json()
        feat_indexes = [i for i, x in enumerate(items) if x["featured"]]
        non_feat_indexes = [i for i, x in enumerate(items) if not x["featured"]]
        if feat_indexes and non_feat_indexes:
            assert max(feat_indexes) < min(non_feat_indexes), "Featured items must come first"

    def test_category_filter(self, featured_setup):
        r = requests.get(f"{API}/public/listings", params={"category": "compound"}, timeout=10)
        assert r.status_code == 200
        items = r.json()
        # All returned should be compound
        for it in items:
            assert it["category"] == "compound"
        # Featured compound prop should be in
        assert any(x["property"]["id"] == featured_setup["feat_pid"] for x in items)

    def test_public_listing_detail(self, featured_setup):
        uid = featured_setup["feat_uid"]
        r = requests.get(f"{API}/public/listings/{uid}", timeout=10)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["property"]["category"] == "compound"
        assert body["property"]["featured"] is True
        assert isinstance(body["property"]["images"], list)
        assert len(body["property"]["images"]) >= 1


# ----------- Admin /properties -----------
class TestAdminProperties:
    def test_admin_list_all(self, admin_token):
        r = requests.get(f"{API}/admin/properties", headers=_headers(admin_token), timeout=10)
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        if items:
            assert "landlord_name" in items[0]
            assert "category" in items[0]
            assert "featured" in items[0]

    def test_landlord_forbidden_from_admin_endpoint(self, landlord_token):
        r = requests.get(f"{API}/admin/properties",
                         headers=_headers(landlord_token), timeout=10)
        assert r.status_code in (401, 403)


# ----------- DELETE -----------
class TestDeleteProperty:
    def test_landlord_delete_own_cascades_units(self, landlord_token):
        # create prop + unit
        r = requests.post(f"{API}/properties",
                          data={"name": f"TEST_DEL_{uuid.uuid4().hex[:6]}",
                                "address": "x", "category": "single_room"},
                          headers=_headers(landlord_token), timeout=10)
        pid = r.json()["id"]
        u = requests.post(f"{API}/units",
                          json={"property_id": pid, "unit_number": "D1",
                                "rent_amount": 5000, "bedrooms": 1},
                          headers=_headers(landlord_token), timeout=10).json()
        uid = u["id"]
        # delete
        r2 = requests.delete(f"{API}/properties/{pid}",
                             headers=_headers(landlord_token), timeout=10)
        assert r2.status_code == 200
        # ensure unit cascaded
        rl = requests.get(f"{API}/units", headers=_headers(landlord_token), timeout=10)
        ids = [x["id"] for x in rl.json()]
        assert uid not in ids

    def test_other_landlord_cannot_delete(self, landlord_token, landlord2_token):
        r = requests.post(f"{API}/properties",
                          data={"name": f"TEST_DEL2_{uuid.uuid4().hex[:6]}",
                                "address": "x", "category": "apartment"},
                          headers=_headers(landlord_token), timeout=10)
        pid = r.json()["id"]
        r2 = requests.delete(f"{API}/properties/{pid}",
                             headers=_headers(landlord2_token), timeout=10)
        assert r2.status_code == 404

    def test_admin_can_delete_any(self, admin_token, landlord_token):
        r = requests.post(f"{API}/properties",
                          data={"name": f"TEST_ADEL_{uuid.uuid4().hex[:6]}",
                                "address": "x", "category": "apartment"},
                          headers=_headers(landlord_token), timeout=10)
        pid = r.json()["id"]
        r2 = requests.delete(f"{API}/properties/{pid}",
                             headers=_headers(admin_token), timeout=10)
        assert r2.status_code == 200


# ----------- Cleanup -----------
def test_zz_cleanup(landlord_token, admin_token):
    """Delete TEST_-prefixed properties."""
    r = requests.get(f"{API}/properties", headers=_headers(landlord_token), timeout=10)
    for p in r.json():
        if p["name"].startswith("TEST_"):
            requests.delete(f"{API}/properties/{p['id']}",
                            headers=_headers(landlord_token), timeout=10)
