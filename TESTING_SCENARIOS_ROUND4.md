# NYUMBA FITI — Round 4 Testing Scenarios

> Round 4 = Security auto-approve + admin password reset + forced KES 35 yard-sale unlock + public pass viewer + lease/rental marketplace filter + M-Pesa sandbox keys live + admin CSV/XLSX/PDF exports + property tile sliders.

## Pre-flight

```bash
API=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d= -f2)

# Re-seed if needed
cd /app/backend && python3 seed_demo_data.py --reset
```

Credentials in `/app/memory/test_credentials.md`. All seeded users use password `demo123` except admin (`admin123`).

---

## 1. Security role — landlord-managed, no admin approval

### 1.1 Add security (auto-approve)
1. Login as `mary@demo.nyumba` → `/security`.
2. Click "Add Security" → fill name/email/phone → submit.
3. ✅ Toast shows the generated password. The user's `approval_status` is **approved** (no "pending" state).
4. Logout, login as the new security user → ✅ login succeeds without admin approval.

### 1.2 Admin approval queue excludes security
1. Login as admin → `/admin/approvals`.
2. ✅ Security users are NOT in the pending list. (One-time sweep also auto-approves any legacy pending records.)

### 1.3 Admin Users tab shows security with filter
1. Login as admin → `/admin/users`.
2. Click the **Securitys** tab.
3. ✅ All security users listed across all landlords. Admin can suspend/reactivate, but no "approve" action shows (already approved).

### 1.4 Security accesses visitor entry, scan & gate passes
1. Login as `sg1@demo.nyumba` → sidebar shows: Overview / Visitor Entry / Security Tickets / Community.
2. Open `/visitors` → ✅ all visitor passes for `mary@demo.nyumba` are listed (active + expired).
3. Tap **Scan / Log Entry** → paste a pass token → ✅ entry logged.
4. Open `/issues` → ✅ list of tickets, can resolve any.

---

## 2. Public Pass Viewer (`/pass/{token}`)

### 2.1 Tenant copies share link
1. Login as `tenant1@demo.nyumba` → `/visitors` → tap **New Pass** → create.
2. On the resulting card, tap **Copy share link for guest**.
3. ✅ Toast: "Pass link copied". Clipboard contains `https://.../pass/<token>`.

### 2.2 Guest opens link (no auth required)
1. In an incognito window, paste the URL.
2. ✅ Renders `/pass/<token>` with:
   - VALID badge
   - Visitor name (H1)
   - QR code (large)
   - Property name + address
   - Host name
   - Expected datetime (proper format, not "Invalid Date")
   - Token at the bottom

### 2.3 Security can also open the link
1. Login as security in another tab → paste same URL → ✅ same page renders.

### 2.4 Used pass shows "Logged in" footer
1. Security scans the pass (from `/visitors`).
2. Reload `/pass/<token>` → ✅ status badge = USED, "Logged in" section appears with timestamp + caretaker name.

### 2.5 Invalid / expired token
1. `/pass/foobar` → ✅ shows "Pass not available" error card.

---

## 3. Admin password / email reset

### 3.1 Generate new password
1. Admin → `/admin/users` → tenant tab → click **Reset** on `tenant3@demo.nyumba`.
2. Leave both fields blank → submit.
3. ✅ Dialog flips to success card with new email (unchanged) + new random password (e.g. `Kf8c1w2X9Q`). Auto-copied to clipboard.
4. Toast: "Reset successful — new password copied to clipboard".

### 3.2 User logs in with new password
1. Logout → login as `tenant3@demo.nyumba` with the new password → ✅ works.
2. Try the old password → ❌ 401.

### 3.3 Change email + custom password
1. Reset same tenant with `new_email=tenant3-new@demo.nyumba` and `new_password=Tested123`.
2. ✅ Success card shows both. Login with new email works.

### 3.4 Audit log
```bash
curl -s "$API/api/admin/audit-log" -H "Authorization: Bearer $ADMIN_TOKEN" | jq '.[0]'
```
✅ Shows recent `reset_credentials` entries.

### 3.5 Guards
- Non-admin reset attempt → 403.
- Reset own admin → 400.
- Duplicate email → 400.

---

## 4. Yard Sale forced KES 35 unlock at posting

### 4.1 Create listing triggers STK push immediately
1. Login as `tenant1@demo.nyumba` → `/yard-sale` → tap **List Item**.
2. ✅ Fee info card visible: "KES 35 unlocks your listing. Buyers will see your name, phone, email, property + unit number."
3. Fill title="Test toaster", price=2500, category=kitchen, phone=`254708374149` (Safaricom sandbox test phone) → submit.
4. ✅ Toast "STK push sent — enter your M-Pesa PIN to publish the listing." Dialog flips to "Awaiting M-Pesa confirmation".
5. Backend creates listing with `status="pending_payment"`, `contact_unlocked=false`. Hidden from other users.
6. After ~4–15 seconds (demo fallback or real Safaricom callback), listing flips to `active` + `contact_unlocked=true`. Dialog auto-closes, listing appears in the grid.

### 4.2 Pending listing invisible to other tenants
1. While listing is in pending_payment state, login as `tenant2@demo.nyumba` → `/yard-sale`.
2. ✅ Test toaster NOT in the list (filtered out by `_can_see_listing`).

### 4.3 After payment, buyers see full contact + property
1. After STK confirms, tenant2 opens the listing detail.
2. ✅ Sees seller name, phone, email, property name, unit number (no address shown — only after broadcast).

### 4.4 Broadcast (KES 50) exposes address
1. As seller, click "Broadcast to all NyumbaOS tenants (KES 50)" → pay.
2. ✅ After callback, `scope=all`. A tenant from a different landlord can now see the listing AND the property address.

### 4.5 Admin sees pending listings
1. Admin → `/admin/moderation` → Yard Sale tab.
2. ✅ Sees all listings including those still `pending_payment`.

---

## 5. Lease vs Rental marketplace filter

### 5.1 Tenancy filter chips
1. Open `/marketplace` (public).
2. ✅ See new "Tenancy" filter row with chips: Any / For Rental / For Lease.
3. Click "For Lease" → ✅ list shrinks to only properties with `tenancy_types` containing `lease` (e.g. Karen Villas, Kilimani Heights, Lavington).
4. Click "For Rental" → ✅ all properties listing rental.

### 5.2 Listing cards show tenancy badges
1. ✅ Each card now shows colored pill badges: `FOR LEASE` (amber) and/or `FOR RENT` (emerald).

### 5.3 API check
```bash
curl -s "$API/api/public/listings?tenancy_type=lease" | jq 'length'
curl -s "$API/api/public/listings?tenancy_type=rental" | jq 'length'
```
✅ Two different counts (lease typically fewer than rental).

### 5.4 Sidebar dynamic label
1. Login as `tenant3@demo.nyumba` (rental) → sidebar reads **Rental Agreement**.
2. Login as `tenant4@demo.nyumba` (lease) → sidebar reads **Lease Agreement**.

---

## 6. M-Pesa sandbox live integration

### 6.1 Keys are loaded
```bash
grep MPESA_CONSUMER_KEY /app/backend/.env
# Output should show the configured Consumer Key
```

### 6.2 Real STK push attempt
1. As tenant, pay a bill → ✅ backend logs show a real Daraja request to `sandbox.safaricom.co.ke`. Look for:
   ```
   POST /mpesa/stkpush/v1/processrequest → 200
   ```
2. The Safaricom test phone `254708374149` should receive a real STK prompt.
3. If callback arrives (`/api/payments/mpesa/callback/{secret}`) → payment marked succeeded immediately.
4. If callback doesn't arrive (sandbox is unreliable), the **15-second demo fallback** fires → payment still marked succeeded.

### 6.3 Idempotency
- Both real callback and demo fallback may fire. ✅ Second one is ignored (we early-return in `_process_callback_payload` if status already `succeeded`).

---

## 7. Admin CSV / XLSX / PDF exports

### 7.1 UI flow
1. Admin → `/admin/users` → top right **Export ▾** → CSV.
2. ✅ Browser downloads `nyumbaos_users.csv`. Open in spreadsheet → headers + rows correct.
3. Repeat with XLSX → ✅ Excel opens it cleanly.
4. Repeat with PDF → ✅ landscape A4 with zebra-striped table.

### 7.2 Coverage matrix
Each of these pages has an **Export ▾** button:
- `/admin/users` → users
- `/admin/payments` → payments
- `/admin/payouts` → payouts
- `/admin/properties` → properties (next to the search box)
- `/admin/bills` → bills
- `/admin/issues` → issues

### 7.3 API smoke (cURL)
```bash
ADMIN_TOKEN=$(curl -s -X POST "$API/api/auth/login" -H "Content-Type: application/json" \
  -d '{"email":"admin@nyumbaos.co.ke","password":"admin123"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

for r in users payments payouts properties bills issues viewings leases; do
  for ext in csv xlsx pdf; do
    CODE=$(curl -s -o "/tmp/nyumbaos_${r}.${ext}" -w "%{http_code}" \
      "$API/api/admin/export/${r}.${ext}" -H "Authorization: Bearer $ADMIN_TOKEN")
    echo "$CODE  ${r}.${ext}"
  done
done
```
✅ All 24 combinations return 200.

### 7.4 Non-admin guard
```bash
curl -i "$API/api/admin/export/users.csv" -H "Authorization: Bearer $LANDLORD_TOKEN"
# 403 Forbidden
```

---

## 8. Property tile slider

### 8.1 Landlord side
1. Login as `mary@demo.nyumba` → `/properties` → upload 3 images on a property.
2. ✅ Card replaces the single hero image with a Swiper carousel (navigation arrows, pagination dots). Auto-rotates.

### 8.2 Marketplace tile
1. `/marketplace` shows the same Swiper carousel on each listing card. Click left/right arrows on hover.

### 8.3 Detail page
1. `/marketplace/<unitId>` shows the larger Swiper with thumbnail strip below.

---

## 9. Regression — Round 3 carry-over

- Social reactions (like/love/celebrate/support) on announcements + threads + replies — ✅ should still work.
- Announcement view receipts (eye chip visible to author/admin only) — ✅
- AI Concierge multi-turn — ✅
- Prospect QR pass auto-issued + Dashboard banner — ✅
- Admin Moderation page (summary + tabs + delete cascade) — ✅

---

## 10. Smoke matrix

```bash
API=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d= -f2)
ADMIN_TOKEN=$(curl -s -X POST "$API/api/auth/login" -H "Content-Type: application/json" \
  -d '{"email":"admin@nyumbaos.co.ke","password":"admin123"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

# Round 4 endpoints
for path in \
  "/api/admin/audit-log" \
  "/api/admin/export/users.csv" \
  "/api/admin/export/payments.xlsx" \
  "/api/admin/export/properties.pdf" \
  "/api/public/listings?tenancy_type=lease" \
  "/api/public/listings?tenancy_type=rental" \
  ; do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" "$API$path" -H "Authorization: Bearer $ADMIN_TOKEN")
  echo "$CODE  $path"
done

# Pass viewer (public — no auth)
TOKEN=$(curl -s "$API/api/admin/moderation/visitor-passes" -H "Authorization: Bearer $ADMIN_TOKEN" \
  | python3 -c 'import sys,json;d=json.load(sys.stdin);active=[p for p in d if p["status"]=="active"];print(active[0]["token"] if active else "")')
curl -s "$API/api/public/pass/$TOKEN" | python3 -c 'import sys,json;d=json.load(sys.stdin);print("OK pass for",d.get("visitor_name"))'
```

---

## 11. Regression Checklist

- [ ] 1.1 Security create → status approved immediately
- [ ] 1.2 Admin approvals queue empty of security
- [ ] 1.3 Admin Users tab has Security filter
- [ ] 2.1 Tenant copies pass share link
- [ ] 2.2 Guest opens `/pass/{token}` (no auth)
- [ ] 2.4 Used pass shows "Logged in" timestamp
- [ ] 3.1 Random password auto-copied to clipboard
- [ ] 3.2 User logs in with new password
- [ ] 3.4 Audit log entry created
- [ ] 4.1 Yard sale create triggers STK push, listing pending
- [ ] 4.2 Other tenants don't see pending listing
- [ ] 4.3 After payment, contact visible
- [ ] 4.4 Broadcast exposes address
- [ ] 5.1 Tenancy filter chips work
- [ ] 5.4 Sidebar reads correct agreement label per tenant
- [ ] 6.2 Real Safaricom sandbox call attempted in logs
- [ ] 7.1 CSV+XLSX+PDF downloads work
- [ ] 8 Property tile sliders carousel through images
