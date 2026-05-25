# Nyumba OS — Complete Testing Scenarios

Full end-to-end manual QA playbook for **every feature** in the platform (MVP + Phase 1 + Phase 2 + Phase 3 + Phase 4).
Estimated total runtime: ~60-90 minutes. Run in order — later scenarios depend on data created in earlier ones.

---

## 0. Setup & Test Accounts

### Pre-seeded credentials

| Role | Email | Password |
|---|---|---|
| Super Admin | `admin@nyumbaos.co.ke` | `admin123` |
| Landlord | `land@demo.com` | `demo123` |
| Caretaker | `ck@demo.com` | `care123` |

### Created during testing (you'll set passwords below)

| Role | Email | Password | When |
|---|---|---|---|
| Tenant A | `tenant.a@demo.com` | `tenant123` | Scenario 4.1 |
| Tenant B | `tenant.b@demo.com` | `tenant123` | Scenario 4.2 |
| Prospect | auto-created on viewing booking | shown in toast | Scenario 6.2 |

### URLs
- App: `https://property-caretaker-3.preview.emergentagent.com` (your `REACT_APP_BACKEND_URL`)
- Public marketplace: `/marketplace`
- Login: `/login`

### Pre-flight check
1. Open `/marketplace` in incognito → page loads, AI Match button visible top-right, search bar + category chips render.
2. Backend health: `curl https://<your-url>/api/` → `{"message":"...", "status":"ok"}`.

---

## 1. AUTHENTICATION & ACCESS CONTROL

### 1.1 Register a new landlord
1. Go to `/register`. Fill: name `Jane Test`, email `jane.landlord@demo.com`, phone `0712345001`, role **Landlord**, password `pass1234`.
2. ✅ Redirected to landlord dashboard.
3. Sign out from sidebar.

### 1.2 Login as pre-seeded landlord
1. Go to `/login`. Use `land@demo.com` / `demo123`.
2. ✅ Lands on `/dashboard` showing landlord stats (properties, units, arrears, etc.).

### 1.3 Wrong password
1. Sign out, go to `/login`. Use `land@demo.com` / `wrong`.
2. ✅ Toast shows error like "Invalid credentials". Stays on login page.

### 1.4 Token persistence
1. After logging in, refresh the page.
2. ✅ Still logged in (token in localStorage works).

### 1.5 Role-based route guard
1. Logged in as **landlord**, navigate to `/admin` directly via URL.
2. ✅ Redirected to `/dashboard` (forbidden role).

### 1.6 Auto-logout on 401
1. In DevTools console, run `localStorage.setItem('nrm_token','garbage')` and refresh.
2. ✅ Frontend redirects to `/login`.

---

## 2. SUPER ADMIN DASHBOARD

### 2.1 Platform Overview
1. Login as **admin** → `/admin`.
2. ✅ See user counts by role, property/unit totals, gross/commission/net processed, current commission rate (3.5%), open issues, pending approvals.

### 2.2 Commission settings
1. `/admin/settings` → change commission to `0.05` (5%) → Save.
2. ✅ Toast "Saved". Reload → still 5%.
3. Revert to `0.035` (3.5%) so other tests aren't affected.

### 2.3 Users management
1. `/admin/users` → see paginated list of all users with role badges.
2. Pick a non-admin user → click **Suspend**.
3. Try to log in as that user in incognito → ✅ "Account suspended" error.
4. Back as admin → **Un-suspend** → login works again.

### 2.4 Cannot self-suspend
1. `/admin/users` → find your own admin row → Suspend button disabled or returns 400.

---

## 3. PROPERTY & UNIT MANAGEMENT (LANDLORD) + PHASE 1

### 3.1 Create a property with category + images
1. Login as **landlord** (`land@demo.com`) → `/properties` → **Add Property**.
2. Name `Sunrise Apartments`, address `Westlands, Nairobi`, **category `Apartment`**, description `Two-storey complex with parking`.
3. Upload 3 images (any JPGs/PNGs).
4. ✅ Image thumbnails preview in the dialog before submit.
5. Submit → Toast "Property created". Card appears in grid with category badge and "Awaiting admin approval" badge.

### 3.2 Admin approves the property
1. Open admin in another browser → `/admin/approvals` → find the new property → **Approve**.
2. ✅ Status pill changes to "Approved" → property card now eligible for marketplace.

### 3.3 All 7 categories appear in dropdown
1. Back as landlord → Add Property → category dropdown contains **Apartment, Bedsitter, Single Room, Self-Contained, Standalone, Compound, Airbnb**.

### 3.4 Image upload — boundary
1. Try selecting 6 images → ✅ toast "Maximum 5 images allowed", no submission.

### 3.5 Edit a property (landlord)
1. Click the pencil icon on a property card → dialog opens with fields pre-filled, image upload hidden.
2. Change name to `Sunrise Towers`, category to `Standalone` → Save.
3. ✅ Card reflects new name + new category badge.

### 3.6 Add unit
1. Properties page → **Add Unit** → pick property → unit number `A101`, rent `25000`, bedrooms `1` → Submit.
2. ✅ Units tab shows the new unit with **Vacant** badge.

### 3.7 Delete unit
1. Trash icon on a vacant unit → confirm → ✅ row disappears.
2. Try deleting a unit with a tenant → ✅ Backend returns 400 "Unit has a tenant. Remove tenant first."

### 3.8 Delete property cascades
1. Trash icon on a property → confirm → ✅ property and all its units gone.

### 3.9 Admin can edit + feature any property
1. Login as **admin** → `/admin/properties` → click pencil on any property → edit name → Save.
2. Click ✨ **Feature** on a property → ✅ Gold "FEATURED" badge appears.
3. Open `/marketplace` in incognito → ✅ featured property/unit shows the gold "Featured" badge AND appears first in the carousel.

---

## 4. TENANT & CARETAKER ONBOARDING

### 4.1 Onboard Tenant A
1. Landlord → `/tenants` → **Add Tenant** → pick a **vacant** unit.
2. Email `tenant.a@demo.com`, name `Aisha Tenant`, phone `0712345002`, password `tenant123`.
3. ✅ Toast "Tenant onboarded". Tenant row appears with unit assignment.
4. Unit on `/properties` → Units tab now shows **Occupied**.

### 4.2 Onboard Tenant B
1. Same flow, different vacant unit. Email `tenant.b@demo.com` / `tenant123`.

### 4.3 Caretaker confirmation
1. Caretaker `ck@demo.com` already exists. Login → ✅ lands on caretaker dashboard.
2. As landlord, `/caretakers` → caretaker visible.

### 4.4 Add a new caretaker
1. Landlord → `/caretakers` → **Add Caretaker** → email `ck2@demo.com` / `care123`, phone `0712345004`.
2. ✅ Awaiting admin approval. Admin approves at `/admin/approvals` → caretaker activates.

---

## 5. BILLS & M-PESA PAYMENTS

### 5.1 Generate monthly rent bills
1. Landlord → `/bills` → **Generate Monthly Bills**.
2. ✅ Toast shows `created: N, skipped: 0, period: YYYY-MM`. Bills list populates.

### 5.2 Tenant gets bill notification
1. Login as **Tenant A** → ✅ red dot on notification bell shows `1` for "New bill: Rent · ...".
2. `/bills` → bill visible with `pending` status.

### 5.3 Manual bill (non-rent)
1. Landlord → `/bills` → **Add Bill** → tenant `Aisha Tenant`, type **water**, amount `500`, period current month, due date 5 days from today.
2. ✅ Row appears with status `pending`. Tenant gets another notification.

### 5.4 M-Pesa STK Push payment (demo)
1. Tenant A → `/bills` → on the rent bill → **Pay Now**.
2. Enter phone `0712345002` → **Pay KES 25,000** (or your unit rent).
3. ✅ Toast "STK push sent". Status spinner shows pending. Wait ~5 seconds.
4. ✅ Bill flips to `paid` (or `partial` if you input lower amount). Both tenant and landlord get success notifications. Receipt number shown.

### 5.5 Partial payment
1. New unpaid bill → Pay → enter custom amount **less** than the total.
2. ✅ Bill status becomes `partial`, `amount_paid` shows the partial. Pay again for the remainder → flips to `paid`.

### 5.6 Cannot pay an already-paid bill
1. Try Pay on a paid bill → backend returns 400.

### 5.7 Landlord sees payment history
1. Landlord → `/payments` → ✅ list of all tenant payments with commission/net columns.

### 5.8 Admin payments view + refund
1. Admin → `/admin/payments` → see ALL payments.
2. On a `succeeded` payment, click refund → confirm reason → ✅ status `refunded`, the linked bill rolls back to `partial`/`pending`, the viewing (if any) becomes `cancelled`.

### 5.9 Payouts
1. Admin → `/admin/payouts` → see per-landlord owed balances (net = gross − commission).
2. On a landlord with balance > 0, click **Mark Paid** → enter amount + note → ✅ recorded.
3. `/admin/payouts/history` shows the recorded payout row.

---

## 6. PUBLIC MARKETPLACE + PAID VIEWINGS

### 6.1 Browse marketplace (logged out)
1. Open `/marketplace` in incognito.
2. ✅ Hero, search bar, max-rent input, **category chips** (All + 7 categories).
3. ✅ Featured listings show gold badge and appear in the first slide of the carousel.
4. Click a category chip → grid filters to that category.
5. Click `All` → all listings.
6. Carousel: arrows + dots work, auto-advances every 5s.

### 6.2 Book a paid viewing
1. Click any listing card → detail page with Swiper image gallery (left/right thumbnails clickable).
2. Click **Book Viewing**.
3. Name `Peter Prospect`, email `peter@demo.com`, phone `0712345099`, date today, time 14:00.
4. Click **Pay KES 200**.
5. ✅ Toast "STK push sent". Wait ~5s.
6. ✅ Status becomes "Confirmed". The dialog reveals:
   - M-Pesa receipt
   - Property address
   - Caretaker contact (phone clickable)
   - Auto-generated login credentials (email + password) — **save this password** for next test.

### 6.3 Prospect login + dashboard
1. Use the credentials shown → login.
2. ✅ Prospect dashboard shows `total_viewings`, `scheduled`, `pending`, `completed` counts.
3. `/viewings` → see your booked viewing with all details.

### 6.4 Landlord sees the incoming viewing
1. Login as landlord → `/viewings` → ✅ row shows prospect name, unit, status `scheduled`.

### 6.5 Refused booking (unit becomes occupied)
1. Manually mark a unit occupied via tenant assignment, then try to book a viewing on that unit's listing → 404 "no longer available".

### 6.6 Search & max-rent filter
1. Marketplace → type a partial property name in search → ✅ grid narrows.
2. Set max rent `10000` → ✅ only listings ≤10k show. Clear to reset.

### 6.7 AI Match (Phase 4)
1. Marketplace (any auth state) → **AI Match** button (top-right).
2. Max rent `30000`, bedrooms `1`, areas `westlands, kilimani`, pick 2-3 category chips → **Find my match**.
3. ✅ Returns up to 3 listings with a one-line rationale each.
   - If platform has ≤3 matching listings, `used_llm: false` and rationale is simple.
   - With 4+ matches and the topped-up Emergent LLM key, you should see `used_llm: true` (the small sparkles indicator next to the caption).
4. Click any result → opens the listing detail.
5. Edge case: max rent `1` → ✅ Empty state "No listings match your filters".

---

## 7. ISSUE TICKETING

### 7.1 Tenant raises an issue
1. Tenant A → `/issues` → **New Issue** → title `Leaking tap`, description `Kitchen tap drips`, priority `high`.
2. ✅ Row appears with status `open`.

### 7.2 Landlord assigns caretaker
1. Landlord → `/issues` → open the new issue → **Assign** dropdown → pick a caretaker.
2. ✅ `assigned_to` populates; caretaker dashboard counter `assigned_open` increments.

### 7.3 Conversation thread
1. Tenant posts a message in the issue thread → ✅ landlord and caretaker can see it.
2. Caretaker replies → tenant sees the reply.

### 7.4 Caretaker resolves
1. Caretaker → opens issue → status dropdown → **Resolved**.
2. ✅ Issue status flips to `resolved` on all three sides.

### 7.5 Admin moderation in issue thread
1. Admin → `/admin/issues` → open any issue → admin can post a moderator message in the thread.
2. ✅ Message appears with `admin` role badge for the participants.

---

## 8. PHASE 2 — COMMUNITY HUB

### 8.1 Landlord posts a property announcement with PDF attachment
1. Landlord → `/community` → **Announcements** tab → **New Announcement**.
2. Scope `Property`, pick a property, title `Water shutdown Saturday`, body `Mains down 9am–12pm.`, attach 1 PDF (or any image) ≤5MB, check **Pin**.
3. ✅ Card appears at top with PINNED + PROPERTY badges and attachment thumbnail/icon. Click attachment → opens in new tab from `/api/uploads/community/...`.

### 8.2 Tenant sees announcement + bell notification
1. Tenant A (same property) → top-right bell → red `1`. Click → "New announcement: Water shutdown Saturday".
2. Click the notification → opens `/community` page with the announcement visible.
3. ✅ Bell count clears.

### 8.3 Admin global announcement
1. Admin → `/community` → New Announcement → scope `Global` → ✅ visible to ALL roles.

### 8.4 Pin/unpin + delete
1. Landlord clicks the pin icon on own announcement → toggles pinned.
2. Click trash → confirms → ✅ removed.
3. As another landlord, try to delete someone else's → ✅ 403.

### 8.5 Tenant starts a forum thread
1. Tenant A → Community → **Forum** tab → **New Thread**.
2. Title `Lost cat`, body `Black & white cat near gate.`, attach an image.
3. ✅ Card appears in list with replies count `0`.

### 8.6 Reply + notify thread author
1. Tenant B (same property) → Community → Forum → click the `Lost cat` thread → reply `I saw it on Block 3`.
2. ✅ Tenant A's bell shows new notification "New reply on…". Replies count = 1.

### 8.7 Moderation: pin + lock
1. Landlord opens the thread → click pin → ✅ PINNED badge. Click lock → ✅ LOCKED badge.
2. Tenant A returns → reply input is hidden (thread locked).
3. Admin can still reply.

### 8.8 Cross-property isolation
1. Tenant B (assigned to property B) tries `GET /api/forum/threads` → ✅ only sees property B's threads, not property A's.
2. Direct URL access via API to a foreign thread → 403.

### 8.9 Attachment validation
1. Try uploading a `.docx` to an announcement → ✅ backend rejects with 400 "Unsupported file type".
2. Upload a 6MB image → ✅ 400 "exceeds 5MB limit".

---

## 9. PHASE 3 — YARD SALE MARKETPLACE

### 9.1 Tenant creates a listing
1. Tenant A → `/yard-sale` → **List Item**.
2. Title `Used microwave`, description `Works perfectly`, price `3500`, category `appliances`, upload 2 images.
3. ✅ Card appears in grid with price badge top-right and first image as cover.

### 9.2 Category filter chips
1. Click `Appliances` chip → ✅ only your listing remains.
2. Click `All` → restored.

### 9.3 Feature via M-Pesa (KES 100, demo mode)
1. Click ✨ sparkle on your own listing → enter phone `0712345002` → **Pay KES 100**.
2. ✅ Toast "STK push sent". Wait ~5 seconds.
3. ✅ Card refreshes with gold **Featured** badge; listing jumps to top of grid; bell notifies "Your listing is featured".

### 9.4 Cross-property visibility
1. Tenant B (different property) → `/yard-sale` → ✅ sees Tenant A's listing (platform-wide visibility, as configured).

### 9.5 Cannot feature someone else's listing
1. Tenant B clicks ✨ on Tenant A's listing → ✅ no sparkle button visible (only owner sees it). Direct API POST → 403.

### 9.6 Edit, mark sold, delete (owner only)
1. Tenant A → on own card → **Mark sold** → ✅ moves out of default `active` filter.
2. Trash icon → confirm → ✅ deleted.

### 9.7 Image type validation
1. Try uploading a `.pdf` as yard sale image → ✅ 400 "Only image files allowed".

### 9.8 Featured expiry (manual DB check, optional)
1. The `featured_until` is set to ~7 days out. After expiry, next `GET /api/yard-sale/listings` auto-unfeatures it.

---

## 10. PHASE 4 — DIGITAL LEASE

### 10.1 Landlord creates lease
1. Landlord → `/leases` → **New Lease**.
2. Pick an occupied unit (rent auto-fills). Deposit `50000`. Start `2026-03-01`. End `2027-02-28`. Optional terms `Pets allowed with deposit.`
3. **Generate & Send** → ✅ Row appears `SENT` status. Click **PDF** → opens formatted lease PDF in new tab with both parties + terms + property block.
4. ✅ Tenant gets bell notification "New lease awaiting your e-signature".

### 10.2 Tenant e-signs
1. Tenant A → bell → click notification → /leases → status `SENT`.
2. Click **E-Sign** → ✅ Status flips to `SIGNED` with green checkmark.
3. Click PDF again → ✅ now shows "Signed by Tenant: Aisha Tenant" with timestamp + IP in the footer.
4. ✅ Landlord bell notifies "Tenant signed their lease".

### 10.3 Cannot re-sign or sign cancelled
1. Tenant tries to sign again → 400 "Already signed".
2. Landlord cancels an unsigned lease → status `cancelled`. Tenant tries to sign → 400 "Lease cancelled".

### 10.4 Cannot cancel signed lease
1. Landlord on a `SIGNED` lease → no X button visible. API DELETE → 400 "Cannot cancel a signed lease".

### 10.5 Role isolation
1. Tenant B tries to fetch Tenant A's lease → 403.

---

## 11. PHASE 4 — QR VISITOR PASSES

### 11.1 Tenant creates a pass
1. Tenant A → `/visitors` → **New Pass**.
2. Visitor name `Jane Doe`, phone `0700111222`, expected today 18:00, notes `Friend visiting`.
3. ✅ Big QR card appears: PNG QR + raw token string + visitor details. Pass also in list as `ACTIVE`.

### 11.2 Caretaker scans
1. Caretaker (same landlord) in another browser → `/visitors` → **Scan / Log Entry** → paste the token string → Log Entry.
2. ✅ Toast "Welcome Jane Doe! Entry logged."
3. Pass status flips to `USED` with timestamp + caretaker name.
4. ✅ Tenant A bell notifies "Visitor Jane Doe has arrived".

### 11.3 Cross-landlord caretaker rejected
1. Caretaker from a **different** landlord tries to scan → 403.

### 11.4 Re-use rejected
1. Same caretaker tries the now-USED token again → 400 "already used".

### 11.5 Expired pass
1. Pass `expires_at` is now + 24h. Manually wait or use the DB to advance — listing `/visitor-passes` next time auto-expires it. Scan → 400 "expired".

### 11.6 Cancel
1. Tenant clicks **Cancel pass** on an active pass → ✅ status `cancelled`. Scan → 400 "cancelled".

### 11.7 Tenant without a unit
1. Try creating pass while not assigned to a unit (admin/landlord trying via API) → 400.

---

## 12. PHASE 4 — IN-APP NOTIFICATIONS

### 12.1 Bell auto-polls every 30 seconds
1. Open the bell, leave page open. Trigger an event (e.g. landlord creates a bill for the tenant) → ✅ within ~30s, badge increments.

### 12.2 Mark one read
1. Click a notification card → ✅ background turns white (was amber) and the badge decrements. Page navigates to the link if any.

### 12.3 Mark all read
1. With multiple unread → click **Mark all read** → ✅ red badge disappears immediately.

### 12.4 Each event-source verification
Trigger each, then verify a notification appears:
- ✅ `bill_due` — landlord creates a bill
- ✅ `bill_due` — landlord runs Generate Monthly
- ✅ `payment_succeeded` — tenant pays, both tenant AND landlord get a notification
- ✅ `announcement` — landlord/admin posts announcement (audience based on scope)
- ✅ `forum_reply` — another user replies on your thread
- ✅ `lease_pending` — landlord creates lease for tenant
- ✅ `lease_signed` — tenant signs (notifies landlord)
- ✅ `visitor_arrived` — caretaker scans visitor pass
- ✅ `yard_sale_featured` — feature payment confirms

---

## 13. ADMIN OVERSIGHT (PHASE 2/3/4 reach)

### 13.1 Admin sees all yard sale listings
1. Admin → `/yard-sale` → ✅ sees listings across the whole platform.
2. Admin can delete any.

### 13.2 Admin sees all announcements + forum threads
1. Admin → `/community` → see all global and property-scoped announcements.
2. `/admin/issues` already shows all issues platform-wide.

### 13.3 Approvals queue includes new actors
1. New landlord/property registers → ✅ admin `/admin/approvals` shows pending items + counts.
2. Admin approves → property becomes visible on `/marketplace`.

### 13.4 Notification panel for admin
1. Admin bell does NOT receive announcement fan-out (admins are excluded by `_audience_user_ids`).
2. But admin DOES receive payment-success and lease-signed notifications only if they are the payer/landlord (typically not). Expected: admin bell mostly empty unless admin actions trigger personal events.

---

## 14. API SMOKE (cURL, optional for tech testers)

```bash
API=https://property-caretaker-3.preview.emergentagent.com

# Health
curl -s $API/api/ | jq

# Login → JWT
TOKEN=$(curl -s -X POST $API/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"land@demo.com","password":"demo123"}' | jq -r .access_token)

# Public listings
curl -s $API/api/public/listings | jq 'length'

# Authenticated
curl -s $API/api/notifications -H "Authorization: Bearer $TOKEN" | jq '.unread_count'
curl -s $API/api/announcements -H "Authorization: Bearer $TOKEN" | jq 'length'
curl -s $API/api/yard-sale/listings -H "Authorization: Bearer $TOKEN" | jq 'length'
curl -s $API/api/leases -H "Authorization: Bearer $TOKEN" | jq
curl -s $API/api/visitor-passes -H "Authorization: Bearer $TOKEN" | jq

# AI recommend (try with broad filters)
curl -s -X POST $API/api/ai/recommend-properties \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"max_rent":50000,"preferred_bedrooms":null}' | jq
```

---

## 15. NEGATIVE PATHS / SECURITY CHECKS

| Action | Expected |
|---|---|
| GET `/api/properties` without token | 401 |
| GET `/api/admin/stats` as landlord | 403 |
| POST `/api/announcements` scope=global as landlord | 403 |
| POST forum thread in another landlord's property | 403 |
| PATCH another seller's yard sale listing | 403 |
| Sign another tenant's lease | 403 |
| Scan visitor pass from another landlord (as caretaker) | 403 |
| Upload non-image to yard sale | 400 |
| Upload `.docx` to announcement | 400 |
| Upload >5MB attachment | 400 |
| Pay an already paid bill | 400 |
| Feature an already-featured yard sale listing | 400 |
| Cancel a signed lease | 400 |
| Scan an already-used or expired or cancelled pass | 400 |
| Invalid M-Pesa phone format | 400 |
| Suspended user login | 403 |
| Direct URL `/admin` as non-admin role | redirect to `/dashboard` |

---

## 16. DEMO MODE / MOCKED BEHAVIOURS (KNOWN)

- 💳 **M-Pesa STK Push** runs in DEMO mode — no real money. Auto-confirms after ~4 seconds via the simulated callback in `mpesa.py::schedule_demo_callback`. Receipts are prefixed `DEMO...`. Replace with real Daraja credentials in `/app/backend/.env` to switch to live.
- 🤖 **AI Match** falls back to "cheapest 3 matching" if `EMERGENT_LLM_KEY` is missing/errored. The `used_llm` flag in the response tells you whether Claude Sonnet 4.5 was used.
- 🔔 **Notifications** poll every 30 seconds (no websockets yet).
- 📷 **Image uploads** are saved to local disk under `/app/backend/uploads/...` and served via `/api/uploads/...`.

---

## 17. AUTOMATED COVERAGE

The same flows are covered by pytest:

- `/app/backend/tests/test_phase1_properties.py` — 19 tests (Phase 1)
- `/app/backend/tests/test_phase234.py` — 30 tests (Phase 2/3/4)

Run all:
```bash
cd /app && pytest backend/tests/ -v
```

Expected: **49/49 passing**.

---

## 18. ISSUE LOGGING TEMPLATE

When you find a bug while running these scenarios, capture:

```
Scenario: [number, e.g. 5.4]
Role: [landlord / tenant / etc.]
Steps: [what you clicked]
Expected: [from this doc]
Actual: [what happened]
Console errors: [open DevTools → Console → screenshot]
Network errors: [DevTools → Network → red rows]
Screenshot: [attach]
```

---

_End of testing scenarios. Last updated: Feb 2026, covers MVP + Phase 1 + 2 + 3 + 4._
