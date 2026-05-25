# Nyumba OS — Phase 2/3/4 Manual Testing Scenarios

> Run these end-to-end **after** the testing agent has confirmed automated tests pass. Each scenario takes ~1-2 min.

## Test Accounts

| Role | Email | Password |
|------|-------|----------|
| Super Admin | `admin@nyumbaos.co.ke` | `admin123` |
| Landlord | `land@demo.com` | `demo123` |
| Caretaker | `ck@demo.com` | `care123` |
| Tenant | Created by landlord on `/tenants` page | (you set it) |

---

## 🏘️ Phase 2 — Community Hub

### Scenario 2.1: Landlord posts a property announcement
1. Sign in as **landlord**.
2. Sidebar → **Community** → **Announcements** tab.
3. Click **New Announcement**. Confirm "Property" scope is preselected. Pick your property, title `"Water shutdown Saturday"`, body `"Mains down 9am-12pm. Sorry!"`, attach 1 PDF.
4. Click **Post**. Toast says "Announcement posted".
5. ✅ Card appears at top with PROPERTY badge, your name, attachment thumbnail.

### Scenario 2.2: Tenant sees announcement + gets notified
1. Sign in as **tenant** in that same property (different browser/incognito).
2. Top-right bell icon shows a red `1` badge.
3. Click bell → see "New announcement: Water shutdown Saturday".
4. Click the notification → opens `/community` with the new announcement visible.
5. ✅ Bell badge clears after click.

### Scenario 2.3: Admin posts a global announcement
1. Sign in as **admin**. Sidebar → Community → New Announcement.
2. Scope `Global (all users)`, title `"Holiday hours"`, post.
3. ✅ Every other user (landlord, tenant, caretaker) sees a GLOBAL badge on the card.

### Scenario 2.4: Tenant forum thread + reply
1. Tenant → Community → **Forum** tab → **New Thread**.
2. Title `"Lost cat"`, body `"Black & white cat near gate. Reach me."`, attach 1 image.
3. ✅ Thread card appears with replies count = 0.
4. Click into the thread, type a reply `"Saw it!"`, post.
5. Original poster gets a notification ("New reply on...").
6. ✅ Thread now shows replies count = 1.

### Scenario 2.5: Moderation
1. Landlord opens thread → Pin icon, then Lock icon.
2. ✅ Card now shows PINNED and LOCKED badges. Tenants can no longer reply.
3. Admin can delete any thread; landlord can delete own-property threads.

### Negative paths
- Tenant cannot view a thread in a property they don't belong to → 403.
- Non-admin trying to post `scope=global` → 403.
- Upload a `.docx` or 6 MB image → backend rejects with 400.

---

## 🛒 Phase 3 — Yard Sale Marketplace

### Scenario 3.1: Tenant creates listing
1. Sign in as **tenant** → Sidebar → **Yard Sale** → **List Item**.
2. Title `"Used microwave"`, description `"Works well, moving out"`, price `3500`, category `appliances`, upload 2 images.
3. ✅ Card appears in grid with price badge top-right.

### Scenario 3.2: Filter by category
1. Click `Appliances` chip → only your listing remains.
2. Click `All` → restored.

### Scenario 3.3: Feature listing via M-Pesa (KES 100, DEMO MODE)
1. On your own listing card, click the ✨ sparkle icon.
2. Enter your phone `0712345678`, click **Pay KES 100**.
3. Toast says "STK push sent". (Demo mode auto-confirms in ~4 sec.)
4. ✅ Within 6 seconds, card refreshes with gold "Featured" badge and the listing jumps to the top of the grid.
5. ✅ Tenant receives notification "Your listing is now featured".

### Scenario 3.4: Mark sold + delete
1. Tenant clicks **Mark sold** on their listing → moves out of default `active` filter.
2. Tenant clicks trash → listing deleted (with confirmation).

### Negative paths
- Trying to feature someone else's listing → 403.
- Featuring an already-featured listing → 400 "already featured".
- Uploading a PDF as a listing image → 400 "Only image files allowed".

---

## 🤖 Phase 4 — Smart Features

### Scenario 4.1: AI Property Recommendations
1. Open **/marketplace** (no login required).
2. Top-right **AI Match** button → fill: max rent `30000`, bedrooms `1`, areas `westlands`, pick `Apartment` + `Bedsitter` chips.
3. Click **Find my match**.
4. ✅ Returns top-3 matches with 1-sentence rationale each (will use Claude Sonnet 4.5 when ≥4 candidates; uses fallback ranking for ≤3). Each card is clickable → goes to listing detail.
5. Click **Try different filters** → form returns.
6. If no listings match the very tight filter (e.g. max rent `1`) → friendly empty state.

### Scenario 4.2: Digital Lease — create + sign
1. Sign in as **landlord** → Sidebar → **Leases** → **New Lease**.
2. Pick an occupied unit (rent auto-fills). Set deposit `KES 50,000`, start `2026-03-01`, end `2027-02-28`. Optional terms.
3. Click **Generate & Send**.
4. ✅ Row appears with status `SENT`. Click **PDF** → opens a properly formatted lease PDF in a new tab.
5. ✅ Tenant gets notification "New lease awaiting your e-signature".
6. Sign in as **tenant** → /leases → status `SENT` → click **E-Sign**.
7. ✅ Status flips to `SIGNED` with green checkmark. Click PDF again → now shows signature footer with timestamp + IP.
8. ✅ Landlord gets notification "Tenant signed their lease".

### Scenario 4.3: QR Visitor Pass
1. Sign in as **tenant** → Sidebar → **Visitors** → **New Pass**.
2. Visitor name `"Jane Doe"`, phone `"0700111222"`, expected `today 18:00`, submit.
3. ✅ Big QR card appears at top with the QR image + token string. Card also shown in list with status `ACTIVE`.
4. Copy the token text (long random string).
5. Sign in as **caretaker** (same landlord) in another browser → Visitors → **Scan / Log Entry** → paste token → Log Entry.
6. ✅ Toast "Welcome Jane Doe! Entry logged." Pass status flips to `USED`.
7. ✅ Tenant gets notification "Visitor Jane Doe has arrived".

### Negative paths
- Caretaker from a different landlord tries to scan → 403.
- Scanning a `used` or `cancelled` pass → 400 "already used" / "cancelled".
- Tenant without a unit tries to create a pass → 400.

### Scenario 4.4: Notifications bell
1. Open the bell from any role.
2. Unread items have an amber left dot + light background.
3. Click an item → marks it read AND navigates to its link.
4. **Mark all read** clears the red badge.
5. New events (bill created, payment received, announcement, forum reply, lease signed, visitor scanned) all appear within ~30 sec (auto-poll).

---

## 🚦 Cross-Phase Smoke

1. Log in as each role and confirm the sidebar shows the right items:
   - **Landlord**: Properties, Tenants, Caretakers, Bills, Payments, Issues, Viewings, **Leases, Community, Yard Sale, Visitors**.
   - **Tenant**: Bills, Payments, Issues, **Leases, Community, Yard Sale, Visitors**.
   - **Caretaker**: Tickets, **Visitor Entry, Community**.
   - **Admin**: All admin views + **Community + Yard Sale**.
2. Notifications bell appears for all roles top-right.
3. Image URLs on all pages render through `${REACT_APP_BACKEND_URL}/api/uploads/...` (NOT `localhost:8001`).

---

## 🐛 Known Demo Mode Behaviors
- M-Pesa STK push auto-confirms after ~4 seconds (no Daraja keys set).
- AI recommendations fall back to "sort by lowest rent" if `EMERGENT_LLM_KEY` is missing or LLM call fails. The dialog's small caption indicates whether the LLM was used (`used_llm: true`).

## File References
- Phase 2: `backend/routers/community_router.py`, `frontend/src/pages/Community.jsx`
- Phase 3: `backend/routers/yardsale_router.py`, `frontend/src/pages/YardSale.jsx`
- Phase 4 Lease: `backend/routers/leases_router.py`, `frontend/src/pages/Leases.jsx`
- Phase 4 QR: `backend/routers/visitors_router.py`, `frontend/src/pages/Visitors.jsx`
- Phase 4 Notifications: `backend/routers/notifications_router.py`, `backend/notifications.py`, `frontend/src/components/NotificationBell.jsx`
- Phase 4 AI: `backend/routers/ai_router.py`, `frontend/src/components/AiRecommendButton.jsx`
