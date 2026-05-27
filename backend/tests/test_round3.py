"""Round 3 regression tests: social reactions, view receipts, AI multi-turn chat,
admin moderation router, prospect QR pass visibility."""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://property-caretaker-3.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@nyumbaos.co.ke"
ADMIN_PASS = "admin123"
LANDLORD_EMAIL = "land@demo.com"
LANDLORD_PASS = "demo123"


# ---------------- helpers ----------------

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
def prospect_credentials(landlord_token):
    """Book a viewing as a public prospect to get prospect login credentials."""
    # Find a public listing
    r = requests.get(f"{API}/public/listings", timeout=30)
    assert r.status_code == 200, r.text
    listings = r.json()
    assert len(listings) > 0, "No public listings available"
    listing = listings[0]
    unit_id = listing["id"]
    prop_id = listing["property"]["id"]

    suffix = uuid.uuid4().hex[:6]
    payload = {
        "property_id": prop_id,
        "unit_id": unit_id,
        "prospect_name": f"TestProspect_{suffix}",
        "prospect_phone": "+254700000999",
        "prospect_email": f"test_prospect_{suffix}@example.com",
        "scheduled_date": "2026-02-15",
        "scheduled_time": "10:00",
        "notes": "Round3 regression test"
    }
    r = requests.post(f"{API}/public/viewings", json=payload, timeout=30)
    assert r.status_code in (200, 201), f"Public viewing failed: {r.status_code} {r.text}"
    data = r.json()
    return {
        "email": payload["prospect_email"],
        "password": data.get("prospect_password"),
        "viewing_id": data.get("viewing_id"),
        "payment_id": data.get("payment_id"),
    }


# ============= SOCIAL REACTIONS =============

class TestSocialReactions:
    """Reactions on announcements/threads/replies."""

    def test_react_toggle_on_announcement(self, admin_token, landlord_token):
        # Get an announcement
        r = requests.get(f"{API}/announcements", headers=_h(landlord_token), timeout=15)
        assert r.status_code == 200, r.text
        anns = r.json()
        if not anns:
            pytest.skip("No announcements seeded")
        ann_id = anns[0]["id"]

        # Add a "like" reaction (landlord)
        r = requests.post(
            f"{API}/social/announcement/{ann_id}/react?reaction=like",
            headers=_h(landlord_token), timeout=15,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["action"] in ("added", "changed", "removed")
        assert "counts" in data

        # Toggle off (same reaction)
        r2 = requests.post(
            f"{API}/social/announcement/{ann_id}/react?reaction=like",
            headers=_h(landlord_token), timeout=15,
        )
        assert r2.status_code == 200
        assert r2.json()["action"] == "removed"

        # Re-add as "love"
        r3 = requests.post(
            f"{API}/social/announcement/{ann_id}/react?reaction=love",
            headers=_h(landlord_token), timeout=15,
        )
        assert r3.status_code == 200
        assert r3.json()["action"] in ("added",)

    def test_list_reactions_returns_my_reaction(self, landlord_token):
        r = requests.get(f"{API}/announcements", headers=_h(landlord_token), timeout=15)
        anns = r.json()
        if not anns:
            pytest.skip("No announcements")
        ann_id = anns[0]["id"]
        # Make sure we have a reaction
        requests.post(
            f"{API}/social/announcement/{ann_id}/react?reaction=celebrate",
            headers=_h(landlord_token), timeout=15,
        )
        r = requests.get(
            f"{API}/social/announcement/{ann_id}/reactions",
            headers=_h(landlord_token), timeout=15,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "counts" in data
        assert "my_reaction" in data
        assert data["my_reaction"] in ("like", "love", "celebrate", "support")


# ============= ANNOUNCEMENT VIEW RECEIPTS =============

class TestAnnouncementViews:
    def test_view_recorded_and_403_for_non_author(self, admin_token, landlord_token):
        r = requests.get(f"{API}/announcements", headers=_h(admin_token), timeout=15)
        anns = r.json()
        if not anns:
            pytest.skip("No announcements")
        # Find one not authored by landlord
        ann = next((a for a in anns if a.get("author_id") != "land-demo" and a.get("author_role") != "landlord"), anns[0])
        ann_id = ann["id"]

        # Landlord views
        r = requests.post(f"{API}/social/announcement/{ann_id}/view", headers=_h(landlord_token), timeout=15)
        assert r.status_code == 200, r.text

        # Author/admin sees views; non-author non-admin (landlord, if not author) gets 403
        r = requests.get(f"{API}/social/announcement/{ann_id}/views", headers=_h(admin_token), timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "total" in data and "views" in data

        # If landlord isn't author, expect 403
        if ann.get("author_id") and ann["author_id"] != "land-demo":
            # We don't know landlord_id exactly; check via token user id
            me = requests.get(f"{API}/auth/me", headers=_h(landlord_token), timeout=15).json()
            if me["id"] != ann.get("author_id"):
                r = requests.get(f"{API}/social/announcement/{ann_id}/views", headers=_h(landlord_token), timeout=15)
                assert r.status_code == 403, f"Expected 403 for non-author, got {r.status_code}"


# ============= AI CHAT MULTI-TURN =============

class TestAIChat:
    def test_chat_creates_session_and_appends(self, landlord_token):
        # Turn 1: no session_id
        r = requests.post(
            f"{API}/ai/chat",
            json={"message": "Hi, I'm looking for a 2BR in Westlands under 80k"},
            headers=_h(landlord_token), timeout=60,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "session_id" in data and data["session_id"]
        assert "reply" in data and data["reply"]
        sid = data["session_id"]

        # Turn 2: same session
        r2 = requests.post(
            f"{API}/ai/chat",
            json={"session_id": sid, "message": "Actually budget is 60k"},
            headers=_h(landlord_token), timeout=60,
        )
        assert r2.status_code == 200, r2.text
        assert r2.json()["session_id"] == sid

        # GET conversations
        r3 = requests.get(f"{API}/ai/conversations", headers=_h(landlord_token), timeout=15)
        assert r3.status_code == 200, r3.text
        convs = r3.json()
        assert any(c["session_id"] == sid for c in convs)

        # GET specific conversation
        r4 = requests.get(f"{API}/ai/conversations/{sid}", headers=_h(landlord_token), timeout=15)
        assert r4.status_code == 200
        full = r4.json()
        assert len(full["messages"]) >= 4  # 2 user + 2 assistant

    def test_non_owner_gets_403(self, admin_token, landlord_token):
        # Create chat as landlord
        r = requests.post(
            f"{API}/ai/chat", json={"message": "test"},
            headers=_h(landlord_token), timeout=60,
        )
        sid = r.json()["session_id"]
        # Login as caretaker (non-admin, non-owner)
        try:
            ck_token = _login("ck@demo.com", "care123")
        except AssertionError:
            pytest.skip("Caretaker login unavailable")
        r2 = requests.get(f"{API}/ai/conversations/{sid}", headers=_h(ck_token), timeout=15)
        assert r2.status_code == 403, f"Expected 403, got {r2.status_code}"
        # Admin can access
        r3 = requests.get(f"{API}/ai/conversations/{sid}", headers=_h(admin_token), timeout=15)
        assert r3.status_code == 200

    def test_admin_list_all_conversations(self, admin_token, landlord_token):
        r = requests.get(f"{API}/admin/ai-conversations", headers=_h(admin_token), timeout=15)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)
        # Landlord (non-admin) should be forbidden
        r2 = requests.get(f"{API}/admin/ai-conversations", headers=_h(landlord_token), timeout=15)
        assert r2.status_code == 403


# ============= ADMIN MODERATION =============

class TestAdminModeration:
    def test_summary(self, admin_token, landlord_token):
        r = requests.get(f"{API}/admin/moderation/summary", headers=_h(admin_token), timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        for key in ("users", "properties", "yard_sale", "announcements", "forum_threads",
                    "viewings", "visitor_passes", "issues", "leases", "ai_conversations"):
            assert key in data, f"Missing key {key}"
            assert isinstance(data[key], int)

        # Non-admin forbidden
        r2 = requests.get(f"{API}/admin/moderation/summary", headers=_h(landlord_token), timeout=15)
        assert r2.status_code == 403

    @pytest.mark.parametrize("endpoint", [
        "yard-sale", "announcements", "forum/threads",
        "viewings", "visitor-passes", "issues", "leases",
    ])
    def test_admin_list_endpoints(self, admin_token, landlord_token, endpoint):
        r = requests.get(f"{API}/admin/moderation/{endpoint}", headers=_h(admin_token), timeout=20)
        assert r.status_code == 200, f"{endpoint}: {r.text}"
        assert isinstance(r.json(), list)
        # Non-admin
        r2 = requests.get(f"{API}/admin/moderation/{endpoint}", headers=_h(landlord_token), timeout=15)
        assert r2.status_code == 403, f"{endpoint}: expected 403 got {r2.status_code}"

    def test_delete_throwaway_announcement_cascades(self, admin_token, landlord_token):
        # POST /announcements uses multipart Form fields, not JSON
        form = {
            "title": f"TEST_throwaway_{uuid.uuid4().hex[:6]}",
            "body": "regression",
            "scope": "global",
        }
        headers = {"Authorization": f"Bearer {admin_token}"}
        r = requests.post(f"{API}/announcements", data=form, headers=headers, timeout=15)
        assert r.status_code in (200, 201), f"Could not create test announcement: {r.status_code} {r.text}"
        ann_id = r.json()["id"]

        # React + view to seed cascading docs
        requests.post(f"{API}/social/announcement/{ann_id}/react?reaction=like",
                      headers=_h(admin_token), timeout=15)
        requests.post(f"{API}/social/announcement/{ann_id}/view",
                      headers=_h(admin_token), timeout=15)

        # Delete via moderation
        r = requests.delete(f"{API}/admin/moderation/announcements/{ann_id}",
                            headers=_h(admin_token), timeout=15)
        assert r.status_code == 200, r.text

        # Verify gone
        r2 = requests.get(f"{API}/admin/moderation/announcements", headers=_h(admin_token), timeout=15)
        assert not any(a["id"] == ann_id for a in r2.json())

    def test_delete_throwaway_ai_conversation(self, admin_token, landlord_token):
        r = requests.post(f"{API}/ai/chat", json={"message": "throwaway test"},
                          headers=_h(landlord_token), timeout=60)
        sid = r.json()["session_id"]
        r = requests.delete(f"{API}/admin/moderation/ai-conversations/{sid}",
                            headers=_h(admin_token), timeout=15)
        assert r.status_code == 200, r.text

        # Verify gone (admin list)
        r2 = requests.get(f"{API}/admin/ai-conversations", headers=_h(admin_token), timeout=15)
        assert not any(c["session_id"] == sid for c in r2.json())


# ============= PROSPECT QR PASS =============

class TestProspectQRPass:
    def test_prospect_can_list_passes_after_viewing_payment(self, prospect_credentials):
        creds = prospect_credentials
        if not creds.get("password"):
            pytest.skip("No prospect password returned from booking")

        # Wait for demo M-Pesa callback (~4-7s) to auto-issue the pass
        time.sleep(8)

        # Login as prospect
        token = _login(creds["email"], creds["password"])

        # Now prospect should see auto-issued pass
        r = requests.get(f"{API}/visitor-passes", headers=_h(token), timeout=15)
        assert r.status_code == 200, f"Prospect /visitor-passes blocked: {r.status_code} {r.text}"
        passes = r.json()
        assert isinstance(passes, list)
        assert len(passes) >= 1, "Prospect should have at least one auto-issued pass after viewing payment"
        active = [p for p in passes if p.get("status") == "active"]
        assert active, "Expected at least one active prospect pass"
        assert "qr_data_url" in active[0]
        assert active[0]["qr_data_url"].startswith("data:image/png;base64,")
