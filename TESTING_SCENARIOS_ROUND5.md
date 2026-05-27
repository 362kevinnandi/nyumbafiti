# Nyumba OS — Round 5 Testing Scenarios

> Round 5 changes:
> 1. **Security can scan visitor passes** (frontend bug fixed)
> 2. **Two-step rent/bill payment** — tenant pays 2.5% service fee via STK push to platform paybill, then pays rent manually to landlord's paybill, then enters M-Pesa receipt code; landlord/caretaker confirms.
> 3. **Property landlord paybill + account** (set per-property by landlord on create/edit)
> 4. **Admin Settings** controls platform paybill, account, service fee %, viewing splits
> 5. **Admin Disbursements ledger** — every paid viewing creates a row for caretaker payout (KES 150) with an admin "Mark paid" workflow.

---

## Pre-flight

```bash
API=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d= -f2)
# Optional fresh seed
cd /app/backend && python3 seed_demo_data.py --reset
```

Credentials: `/app/memory/test_credentials.md` (admin / mary / james / tenant1..4 / ck1 / sg1).

---

## 1. Security can now scan visitor passes (bug fix)

### 1.1 UI verification
1. Login as `sg1@demo.nyumba` → `/visitors`.
2. ✅ The **"Scan / Log Entry"** button is visible (top right) — was hidden before this round.
3. Click it → token dialog opens.

### 1.2 End-to-end scan
1. Find an active pass for sg1's landlord (mary). One easy way:
   - Login as `tenant1@demo.nyumba` → `/visitors` → create a new pass.
   - Copy the token from the QR card.
2. Login as `sg1@demo.nyumba` → `/visitors` → Scan → paste token → submit.
3. ✅ Toast: "Welcome <visitor>! Entry logged."
4. ✅ Pass status flips to USED. `used_by_role=security` written to the document.
5. Tenant gets a notification: "Visitor arrived — scanned by sg1 (security)".

### 1.3 Cross-landlord guard (should fail)
1. Have `tenant3@demo.nyumba` (under landlord james) create a pass.
2. As `sg1` (under mary), try to scan that token → ✅ 403 Forbidden.

---

## 2. Platform settings — paybill + service fee + viewing splits

### 2.1 Open settings
1. Login as admin → `/admin/settings`.
2. ✅ Three sections rendered:
   - **Platform M-Pesa Paybill**: 247247 / 0740479864 (pre-seeded).
   - **Rent & Bill Service Fee**: 2.5% with a live sample preview.
   - **Viewing Fee Split**: Caretaker 150 + Platform 50.

### 2.2 Update settings
1. Change service fee to `3.0`, viewing platform share to `75`, save.
2. Toast "Settings updated".
3. Reload → values persist.
4. Restore to 2.5 / 50 before continuing.

### 2.3 API check
```bash
ADMIN_TOKEN=$(curl -s -X POST "$API/api/auth/login" -H "Content-Type: application/json" \
  -d '{"email":"admin@nyumbaos.co.ke","password":"admin123"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
curl -s "$API/api/admin/settings" -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool
# Should show: platform_paybill, platform_account, service_fee_pct, viewing_caretaker_share, viewing_platform_share
```

### 2.4 Public settings (any authenticated user)
```bash
TT=$(curl -s -X POST "$API/api/auth/login" -H "Content-Type: application/json" \
  -d '{"email":"tenant1@demo.nyumba","password":"demo123"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
curl -s "$API/api/admin/public-settings" -H "Authorization: Bearer $TT" | python3 -m json.tool
# Shows platform_paybill, platform_account, service_fee_pct — NO secret fields.
```

---

## 3. Property paybill + account (landlord-owned)

### 3.1 Create with paybill
1. Login as `mary@demo.nyumba` → `/properties` → "Add Property".
2. Fill name/address/category/etc. plus:
   - **Your paybill**: `522522`
   - **Account number**: `WESTLANDS-1A`
3. ✅ Submit. New property has these fields stored.

### 3.2 Edit paybill
1. Click ✎ Edit on any existing property.
2. ✅ Form pre-fills with stored paybill & account if any.
3. Update them → save → ✅ persisted.

### 3.3 API check
```bash
curl -s "$API/api/properties" -H "Authorization: Bearer $LL_TOKEN" | python3 -c '
import sys,json
d=json.load(sys.stdin)
for p in d:
    print(p["name"], p.get("landlord_paybill",""), p.get("landlord_account_number",""))
'
```

---

## 4. Two-step rent/bill payment (the main flow)

### Setup
1. Login as `mary@demo.nyumba` → ensure her property `Westlands Park Apartments` has `landlord_paybill=522522` & `landlord_account_number=WESTLANDS-1A`.
2. Generate a bill for tenant1 if none exists:
   ```bash
   curl -s -X POST "$API/api/bills/generate-monthly" -H "Authorization: Bearer $LL_TOKEN"
   ```

### 4.1 Tenant initiates payment
1. Login as `tenant1@demo.nyumba` → `/bills`.
2. ✅ Pending bill shows status `pending`.
3. Click **Pay** → dialog opens with header *"Two-step payment"*:
   - Step 1: STK push (now) for 2.5% to NyumbaOS
   - Step 2: pay rent directly to landlord's paybill
4. Phone field pre-fills tenant's number → click **Pay service fee (~2.5%)**.

### 4.2 Service fee STK callback
1. ✅ Toast "STK push sent". Dialog shows spinner "Check your phone for the M-Pesa STK push prompt".
2. Wait ~4–18s for callback (real Daraja OR demo fallback).
3. ✅ Dialog flips to "Fee paid · Now pay rent to landlord" with green checkmark.
4. Backend bill now has:
   - `status=awaiting_rent_receipt`
   - `service_fee_amount=250` (assuming KES 10,000 rent → 2.5% → 250 → round up to 10)
   - `service_fee_payment_id`, `service_fee_paid_at` populated.

### 4.3 Tenant pays rent manually (simulated)
1. Same dialog now shows step-by-step instructions:
   ```
   1. Open M-Pesa → Lipa na M-Pesa → Pay Bill
   2. Business no.: 522522
   3. Account no.: WESTLANDS-1A
   4. Amount: KES 10,000
   5. Enter PIN → save the receipt code
   ```
2. Enter a fake receipt code e.g. `SGH7XYZ123` and the amount.
3. Submit → ✅ toast "Receipt submitted — waiting for landlord to confirm".
4. Bill status flips to `awaiting_landlord_confirmation`. Tenant cannot pay again (idempotent).

### 4.4 Landlord confirms
1. Login as `mary@demo.nyumba` → `/bills`.
2. ✅ The bill row shows status badge "awaiting confirm" + a **Confirm** button + **Reject** button.
3. Click **Confirm** → confirmation prompt → ✅ toast "Receipt confirmed — bill marked paid".
4. Bill status: `paid`. `rent_confirmed_at` + `rent_confirmed_by_role=landlord` recorded.

### 4.5 Reject path
1. Repeat 4.1–4.3 with another bill.
2. Landlord clicks **Reject**, supplies a reason.
3. ✅ Bill reverts to `pending` (service fee NOT refunded — that's intentional, the fee was for processing the receipt). Tenant gets a notification.
4. Tenant must pay service fee again to resubmit.

### 4.6 Caretaker can confirm too
1. Login as `ck1@demo.nyumba` (mary's caretaker) → `/bills`.
2. Currently caretakers don't see /bills sidebar, but the API endpoint accepts caretaker role:
   ```bash
   CK=$(login ck1)
   curl -X POST "$API/api/bills/<bid>/confirm-rent-receipt" -H "Authorization: Bearer $CK"
   ```
3. ✅ 200, bill marked paid by caretaker role.

### 4.7 API smoke
```bash
# Service fee math: ceil(amount × pct / 10) × 10
# rent 10,000 × 0.025 = 250 → round up = 250
# rent 12,345 × 0.025 = 308.625 → round up = 310
# rent 7,890 × 0.025 = 197.25 → round up = 200

# Tenant initiates fee
curl -X POST "$API/api/payments/mpesa/stk-push" -H "Authorization: Bearer $TT" \
  -H "Content-Type: application/json" \
  -d '{"bill_id":"<bid>","phone_number":"254708374149"}' | python3 -m json.tool
# response: service_fee_amount, rent_amount, total_cost_to_tenant, landlord_paybill, landlord_account_number, platform_paybill, platform_account

# Submit receipt (after fee confirmed)
curl -X POST "$API/api/bills/<bid>/submit-rent-receipt" -H "Authorization: Bearer $TT" \
  -H "Content-Type: application/json" -d '{"mpesa_receipt":"SGH7XYZ","amount_paid":10000}'

# Confirm
curl -X POST "$API/api/bills/<bid>/confirm-rent-receipt" -H "Authorization: Bearer $LL"

# Reject
curl -X POST "$API/api/bills/<bid>/reject-rent-receipt" -H "Authorization: Bearer $LL" \
  -H "Content-Type: application/json" -d '{"reason":"Wrong amount"}'
```

---

## 5. Viewing fee → disbursement ledger

### 5.1 Book + pay a viewing
1. Open `/marketplace/<unitId>` in incognito.
2. Book viewing → STK push KES 200 → fee paid (~15s later).
3. ✅ Viewing status flips to `scheduled` + prospect QR auto-issued.

### 5.2 Admin sees disbursement queued
1. Login as admin → `/admin/disbursements`.
2. ✅ Top summary cards show:
   - Caretakers owed (pending): KES 150
   - Caretakers paid: KES 0
   - Platform viewing revenue: KES 50
3. ✅ Table row: kind=`viewing_caretaker`, gross=200, caretaker=150, platform=50, status=pending.

### 5.3 Mark paid
1. Click **Mark paid** → dialog → enter M-Pesa B2C receipt (any string) → confirm.
2. ✅ Row status → paid, summary recalculates (pending KES 0, paid KES 150).

### 5.4 API
```bash
curl -s "$API/api/admin/disbursements" -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -m json.tool
curl -X POST "$API/api/admin/disbursements/<disb_id>/mark-paid" -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" -d '{"mpesa_receipt":"SGH123","note":"Weekly batch"}'
```

---

## 6. Yard sale fees — already platform-paybill

No change in this round — already lands in platform paybill. Verify nothing regressed:
1. Tenant creates yard sale listing → STK KES 35 → publishes after confirmation.
2. Tenant clicks Broadcast → STK KES 50 → scope=all.

---

## 7. Curl smoke matrix

```bash
ADMIN=$(curl -s -X POST "$API/api/auth/login" -H "Content-Type: application/json" \
  -d '{"email":"admin@nyumbaos.co.ke","password":"admin123"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

for p in \
  "/api/admin/settings" \
  "/api/admin/public-settings" \
  "/api/admin/disbursements" \
  "/api/admin/audit-log" \
  ; do
  echo "$(curl -s -o /dev/null -w '%{http_code}' "$API$p" -H "Authorization: Bearer $ADMIN")  $p"
done
```
Expected: 200 for all.

---

## 8. Regression checklist

- [ ] 1.1 Security sees Scan button on `/visitors`
- [ ] 1.2 Security successfully scans a same-landlord pass → USED
- [ ] 1.3 Security CANNOT scan cross-landlord pass → 403
- [ ] 2.1 Admin Settings page renders 4 sections
- [ ] 2.2 Settings PATCH persists across reload
- [ ] 3.1 Property create with paybill+account saves
- [ ] 4.1 Tenant Pay dialog shows two-step instructions
- [ ] 4.2 Service fee STK fires + bill flips to awaiting_rent_receipt
- [ ] 4.3 Tenant submits receipt → status awaiting_landlord_confirmation
- [ ] 4.4 Landlord confirms → bill paid
- [ ] 4.5 Landlord rejects → bill back to pending
- [ ] 5.2 Paid viewing creates disbursement_ledger row
- [ ] 5.3 Admin marks disbursement paid → summary updates
