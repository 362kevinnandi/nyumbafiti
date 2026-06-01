# NYUMBA FITI — Round 3 Testing Scenarios

> Covers: Social reactions, announcement read receipts, multi-turn AI Concierge, prospect QR entry pass, Admin God-Mode Moderation, plus regression for Round 1/2 (Security role, tenancy types, yard sale monetization).

## Pre-flight

**URL**: `${REACT_APP_BACKEND_URL}` (currently `https://property-caretaker-3.preview.emergentagent.com`)

**Test Accounts** (`/app/memory/test_credentials.md`):
| Role | Email | Password |
|---|---|---|
| Admin | admin@nyumbaos.co.ke | admin123 |
| Landlord | land@demo.com | demo123 |
| Caretaker | ck@demo.com | care123 |
| Tenant | created by landlord on `/tenants` (auto-emails a generated password — copy it from the success toast) |
| Security | created by landlord on `/security` (same flow as caretaker) |
| Prospect | auto-created when booking a viewing on `/marketplace/<unitId>` — credentials returned in the booking dialog |

**Note**: M-Pesa runs in **DEMO MODE** → STK push auto-confirms after ~4–7 seconds.

---

## 1. Social Reactions (announcements / threads / replies)

### 1.1 Tenant adds reaction to announcement
1. Login as **landlord** → `/community` → create a new announcement targeting a property.
2. Logout, login as a **tenant** of that property → `/community`.
3. Find the announcement card → click 👍 **Like**.
4. ✅ Counter increments to `1`, like button glows sky-blue.
5. Click 👍 **Like** again.
6. ✅ Counter back to `0`, button returns to neutral (toggle off).
7. Click ❤️ **Love**.
8. ✅ Love counter = 1, like = 0 (single reaction per user per target — switching swaps).

### 1.2 Multiple users react to the same thread
1. Open a forum thread as **tenant A** → click 🎉 **Celebrate**.
2. Login as **tenant B** in another browser → react with 🙌 **Support** on the same thread.
3. ✅ Both counters show `1` and `1`. Only your own reaction button is highlighted.

### 1.3 Reaction on a forum reply
1. Open any forum thread with replies → click 👍 on a reply.
2. ✅ Reply card shows `1` next to like icon. Persists after page reload.

### 1.4 API direct check
```bash
TOKEN=...
curl -X POST "$API/api/social/announcement/<aid>/react?reaction=love" -H "Authorization: Bearer $TOKEN"
# Response: {"action":"added","counts":{"love":1}}
curl "$API/api/social/announcement/<aid>/reactions" -H "Authorization: Bearer $TOKEN"
# Response: {"counts":{"love":1},"my_reaction":"love","reactions":[...]}
```

---

## 2. Announcement Read Receipts

### 2.1 Tenant view auto-records receipt
1. Login as **tenant** → `/community` (announcements tab loads).
2. Behind the scenes: `POST /api/social/announcement/{id}/view` fires for each non-authored announcement.
3. Logout, login as the **author landlord** → `/community`.
4. ✅ Each announcement card shows a 👁️ **eye + count** chip on the right.
5. Click the chip → popover lists viewers (name, role, last viewed timestamp, view count).

### 2.2 Author viewing own does NOT increment
1. Author landlord opens their own announcement.
2. ✅ Total view count remains the same (own views are intentionally ignored).

### 2.3 Non-author non-admin cannot see receipts
1. Login as a **different tenant** (not author) → `/community`.
2. ✅ The 👁️ chip is **hidden** on every card (component returns null when `canSee=false`).
3. Direct API check: `GET /api/social/announcement/<aid>/views` → **403**.

### 2.4 Admin god-view
1. Login as **admin** → `/community` → click view-receipts chip on any announcement.
2. ✅ Popover loads with full viewer list, regardless of authorship.

---

## 3. Multi-turn AI Concierge Chat (Marketplace)

### 3.1 Suggestion chips → first response
1. Open `/marketplace` (public — no auth required) → click **AI Concierge** (amber pill, top right of toolbar).
2. ✅ Modal opens with 4 suggestion chips and welcome text.
3. Click "Westlands 2 bedroom under 30k".
4. ✅ User bubble appears (dark) → "Thinking..." indicator → assistant bubble (amber) with response (2–4 sentences max).
5. If response mentions `listing_id=<uuid>`, ✅ a **View →** chip is rendered below the bubble.

### 3.2 Follow-up turn (multi-turn continuity)
1. After the first reply, type "What about 3 bedroom?" → send.
2. ✅ Second exchange appears under the first (history not lost).
3. Inspect Network → POST `/api/ai/chat` with the **same `session_id`** from turn 1.

### 3.3 Listing chip → marketplace detail
1. Click the **View →** chip on an assistant message.
2. ✅ Navigates to `/marketplace/<listing_id>` and the listing detail loads with image carousel + booking sidebar.

### 3.4 Close + reopen resets session
1. Close the modal → reopen.
2. ✅ Empty state with suggestion chips again (new session_id will be assigned on next send).

### 3.5 Conversation persistence + admin visibility
1. After a chat, login as admin → call:
   ```bash
   curl "$API/api/admin/ai-conversations" -H "Authorization: Bearer $TOKEN"
   ```
2. ✅ Most recent session listed with `user_name`, `user_role`, `message_count`, `preview`.
3. ✅ Non-admin call → 403.

### 3.6 LLM fallback (when EMERGENT_LLM_KEY missing / errors)
1. Temporarily clear the key in backend `.env` → restart backend.
2. Send a chat message.
3. ✅ Response begins with "I'm in basic mode right now..." (fallback path), `used_llm=false`.
4. **Restore the key**.

---

## 4. Prospect QR Entry Pass

### 4.1 Booking flow → auto-issue
1. Open `/marketplace/<unitId>` in incognito (no auth).
2. Click **Book Viewing** → fill name/email/phone/date/time → submit.
3. ✅ Toast "STK push sent! Check your phone." → dialog flips to **Awaiting Payment**.
4. Wait ~4–7s (demo callback).
5. ✅ Dialog flips to **Confirmed!** with M-Pesa receipt, address, caretaker contact, and the prospect's new login credentials.
6. Note the email/password.

### 4.2 Prospect Dashboard QR banner
1. Login with the prospect credentials from 4.1.
2. ✅ `/dashboard` shows a prominent **emerald-bordered card** with:
   - QR code image (left)
   - "Your viewing entry pass" overline
   - "Show this QR at the gate" headline
   - VALID badge + Expected datetime (proper format — not "Invalid Date")
   - **View all my passes** + **My Viewings** action buttons
3. Inspect data: `data-testid="prospect-qr-banner"`, `prospect-qr-image`.

### 4.3 Prospect QR pass list
1. Click **View all my passes** → `/visitors`.
2. ✅ Page lists the auto-issued pass with QR image, VALID status, host name, expected datetime, expires datetime.
3. Prospect cannot create new passes (no "+ New Pass" button — that's tenant only).

### 4.4 Security/Caretaker scans the pass
1. Copy the token from the pass card (the small monospace string under the QR).
2. Logout → login as **security** (or caretaker) attached to the same landlord → `/visitors` → **Scan / Log Entry**.
3. Paste the token → submit.
4. ✅ Toast "Welcome <prospect name>! Entry logged."
5. ✅ Pass status flips to **USED**, `used_by_caretaker_name` set to security's name.
6. Logout, login as prospect again → check Notifications bell.
7. ✅ Notification: "Visitor <prospect> has arrived — Scanned by <security> (security)".

### 4.5 Expired / double-use guards
1. Try scanning the same token again → ✅ 400 "Pass has already been used".
2. Manually set a pass `expires_at` to the past → scan → ✅ 400 "Pass has expired".

### 4.6 Direct API for prospect visibility (was previously broken)
```bash
PROSPECT_TOKEN=$(curl -s -X POST "$API/api/auth/login" -H "Content-Type: application/json" \
  -d '{"email":"<prospect_email>","password":"<prospect_pw>"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
curl "$API/api/visitor-passes" -H "Authorization: Bearer $PROSPECT_TOKEN"
# Should now return >= 1 pass with qr_data_url for active ones.
```

---

## 5. Admin God-Mode Moderation Page

### 5.1 Sidebar entry
1. Login as **admin** → sidebar shows new **Moderation** link (shield-alert icon).
2. Click it → `/admin/moderation` loads.

### 5.2 Summary grid
1. ✅ Top tab "Overview" shows a 4-column grid of counts: Users / Properties / Units / Yard Sale / Announcements / Forum Threads / Forum Replies / Viewings / Visitor Passes / Issues / Leases / AI Conversations / Reactions / Payments.
2. Click any clickable card (e.g. **Yard sale**) → jumps to its tab.

### 5.3 Tab list + search
1. Click each tab in turn: Yard Sale / Announcements / Forum / Viewings / Visitor Passes / Issues / Leases / AI Chats.
2. ✅ Each tab loads records sorted by `created_at DESC`. Search box filters across any field (JSON-stringified contains).
3. Counter "X of Y" updates as you type.

### 5.4 Visitor pass row sanity
1. Open Visitor Passes tab.
2. ✅ Each row shows visitor name, host, status, expected + expires (**no "Invalid Date"** after this session's fix).
3. ✅ Prospect-issued passes show an amber **prospect** badge.

### 5.5 Delete with cascade — announcement
1. Open Announcements tab.
2. As **admin**, first react to a test announcement + view it from another account so it has reactions + view receipts.
3. Click the trash icon → confirm.
4. ✅ Row disappears, toast "Deleted".
5. Verify cascade:
   ```bash
   curl "$API/api/admin/moderation/summary" -H "Authorization: Bearer $TOKEN" | jq
   # announcements count: -1, reactions/announcement_views also decremented.
   ```

### 5.6 Delete with cascade — forum thread
1. Open Forum tab → delete a thread that has replies.
2. ✅ Thread + replies + reactions on both removed in single call.

### 5.7 Delete other resources
- Yard sale → ✅ 200, item gone from `/yard-sale`.
- Viewing → ✅ 200, gone from `/admin/moderation/viewings`.
- Visitor pass → ✅ 200, gone from `/visitor-passes` for the host.
- Issue → ✅ 200, gone from `/issues`.
- Lease → ✅ 200, gone from `/leases`.
- AI conversation → ✅ 200; admin call to `/api/admin/ai-conversations` no longer lists it.

### 5.8 Non-admin guards
For each endpoint pair, login as landlord/tenant/security and confirm:
```bash
curl -i "$API/api/admin/moderation/summary" -H "Authorization: Bearer $LANDLORD_TOKEN"
# 403 Forbidden
curl -i -X DELETE "$API/api/admin/moderation/yard-sale/<id>" -H "Authorization: Bearer $LANDLORD_TOKEN"
# 403 Forbidden
```

---

## 6. Regression — Round 1 & Round 2 features

### 6.1 Security role
1. Login as **landlord** → `/security` → add a security user (email/full name/phone).
2. ✅ Generated password appears in toast — save it.
3. Login as security → sidebar = Overview / Visitor Entry / Security Tickets / Community (no rent stuff).
4. From `/visitors` security can **Scan / Log Entry** (4.4 above).
5. On `/issues` (or "Security Tickets") security can resolve a ticket. ✅ The resolution shows `resolved_by_role=security` to landlord on admin.

### 6.2 Tenancy types
1. Landlord creates a property with `tenancy_types=["lease"]` only.
2. Adds a tenant on that unit with `tenancy_type=lease`.
3. ✅ Tenant sidebar reads **My Agreement** (not "My Rental"), Bills page badge shows LEASE, lease auto-gen on tenant onboarding.
4. Repeat with `tenancy_types=["rental"]` — sidebar reads "My Rental" / "Rental Agreement".

### 6.3 Yard sale KES 35 unlock-contact
1. Login as tenant → `/yard-sale` → create a listing (free, scope=property).
2. Open the listing detail (`/yard-sale/<id>`).
3. ✅ Other users see "Contact hidden" placeholder.
4. As owner, click **Unlock contact details (KES 35)** → enter M-Pesa phone → STK push.
5. After demo callback (~5s), reload detail page.
6. ✅ Phone & email visible to any buyer + notification fired.

### 6.4 Yard sale KES 50 broadcast
1. Same as 6.3 but click **Broadcast to all NyumbaOS tenants (KES 50)**.
2. ✅ After callback, `scope` flips to `all`. Tenant in a different property can now see the listing on `/yard-sale`.

### 6.5 Yard sale KES 100 feature-for-7-days
1. Click **Feature for 7 days (KES 100)** → pay.
2. ✅ Item gets a gold ✨ FEATURED badge, sorted to the top, `featured_until` set 7 days out.

---

## 7. Smoke API matrix (curl-able)

```bash
API=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d= -f2)
TOKEN=$(curl -s -X POST "$API/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@nyumbaos.co.ke","password":"admin123"}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# Round 3 endpoints — every one should return 200
for path in \
  "/api/admin/moderation/summary" \
  "/api/admin/moderation/yard-sale" \
  "/api/admin/moderation/announcements" \
  "/api/admin/moderation/forum/threads" \
  "/api/admin/moderation/viewings" \
  "/api/admin/moderation/visitor-passes" \
  "/api/admin/moderation/issues" \
  "/api/admin/moderation/leases" \
  "/api/admin/ai-conversations" \
  ; do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" "$API$path" -H "Authorization: Bearer $TOKEN")
  echo "$CODE  $path"
done

# AI chat smoke
curl -s -X POST "$API/api/ai/chat" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"Westlands 2 bedroom"}' | python3 -m json.tool
```

Expected: `200` for every admin endpoint above; AI chat returns `{session_id, reply, used_llm}`.

---

## 8. Known caveats / out-of-scope

- M-Pesa STK runs in **DEMO mode** — no real money moves; callback fires automatically after ~4–7 seconds.
- AI chat uses `EMERGENT_LLM_KEY` via emergentintegrations; if Anthropic API is briefly unreachable, the response falls back to a static message with `used_llm=false` (still returns 200).
- Existing visitor passes created before this session may show their `expected_time` in raw string form ("10:00") — this is cosmetic and only affects old test data; new prospect passes use full ISO datetime.
- "Made with Emergent" badge removal is a platform-level request handled via `support@emergent.sh` — not a code change.

---

## 9. Regression checklist (paste-in for CI / manual round)

- [ ] 1.1 Like toggle works
- [ ] 1.2 Two users can react independently
- [ ] 1.3 Reaction persists on forum reply across reload
- [ ] 2.1 View auto-records, eye chip shows count for author
- [ ] 2.3 Non-author tenants do NOT see the chip
- [ ] 3.1 AI chat first reply rendered
- [ ] 3.2 Same session_id on follow-up turn
- [ ] 3.3 listing chip navigates to detail
- [ ] 3.5 Admin sees the conversation in `/admin/ai-conversations`
- [ ] 4.1 Demo M-Pesa booking → confirmed
- [ ] 4.2 Prospect dashboard QR banner present with valid datetime
- [ ] 4.4 Security scan flips status to USED + notifies prospect
- [ ] 4.6 GET /visitor-passes for prospect returns pass with qr_data_url
- [ ] 5.2 Moderation summary grid loads with correct counts
- [ ] 5.5 Announcement delete cascades reactions+views
- [ ] 5.6 Forum thread delete cascades replies+reactions
- [ ] 5.8 Non-admin gets 403 on every /admin/moderation/* call
- [ ] 6.1 Security user resolves ticket, role-attributed
- [ ] 6.3 Yard sale unlock-contact works after STK callback
- [ ] 6.4 Yard sale broadcast flips scope to all
- [ ] 7 Every Round 3 endpoint returns 200 in smoke matrix
