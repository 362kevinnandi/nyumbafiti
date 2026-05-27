# Nyumba OS — Round 6 Testing Scenarios

> **What changed**:
> 1. **Removed the false-success demo callback bug** — STK pushes that the user cancels (or simply ignores) now correctly settle as `failed`. Previously they auto-marked `succeeded` after 15s.
> 2. **Real Safaricom STK status polling** — backend polls Daraja's `/stkpushquery` at +15s/+45s/+95s/+170s/+270s and synthesizes a callback with the **real** result (success / cancelled / timeout / insufficient funds).
> 3. **Manual `/payments/{id}/check`** endpoint — frontend triggers it after ~25s so even if Safaricom's async callback never arrives, the truth is known.
> 4. **Manual `/payments/{id}/cancel`** endpoint — tenant can abort a stuck STK push and retry.
> 5. **Two-step flow now applies to ALL bill types** (rent, water, electricity, service charge, other) — the PayDialog wording adapts.
> 6. **Yard sale + viewing** flows piggyback on the same real-polling path. False-positive "paid" no longer possible.
> 7. **Failure notification** — when STK push fails, tenant gets a notification telling them to retry.

---

## Pre-flight

```bash
API=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d= -f2)
# Backend .env must have MPESA_DEMO_FALLBACK=false (default after this round)
grep MPESA_DEMO_FALLBACK /app/backend/.env  # → MPESA_DEMO_FALLBACK="false"
```

Credentials: `/app/memory/test_credentials.md` (admin / mary / james / tenant1..4 / ck1 / sg1).

---

## 1. The bug fix — false-positive "paid" eliminated

### 1.1 Tenant ignores STK push → bill correctly stays unpaid
1. Login as `tenant1@demo.nyumba` → `/bills`.
2. Click **Pay** on any pending bill (rent, water, electricity, service charge, other — all use the same flow).
3. STK push fires. ✅ Dialog shows spinner + "elapsed: Xs" counter + Cancel button.
4. **DO NOT enter PIN** on your phone. Wait 30+ seconds.
5. Frontend auto-calls `/check` at ~25s. Backend hits Safaricom which says "user did not respond" (ResultCode 1037).
6. ✅ Dialog flips to red "Payment didn't go through" panel with retry button.
7. ✅ Backend payment row: `status=failed`, `result_desc` mentions "DS timeout" or similar.
8. ✅ Bill stays `pending` (NOT falsely marked paid).

### 1.2 Tenant cancels the STK prompt → same outcome
1. Initiate payment. When STK push arrives on phone, press **Cancel** instead of entering PIN.
2. Wait for the next poll. ✅ Backend sees ResultCode 1032 (user cancelled) → `status=failed`.
3. ✅ Frontend shows red retry panel.

### 1.3 Tenant clicks **Cancel & retry** in the dialog
1. Initiate payment. Don't pay.
2. In the dialog, click **Cancel and retry** while it's still spinning.
3. ✅ `POST /payments/{id}/cancel` fires → payment status `failed`, `result_desc="Cancelled by user"`.
4. ✅ Dialog shows the red error panel + "Try again" button. Click it → re-opens fee step.

### 1.4 Happy path — tenant DOES enter PIN
1. Initiate payment. Enter PIN on real test phone (`254708374149` in sandbox).
2. Within ~15s Safaricom callback hits. ✅ Dialog flips green "Service fee paid — now pay rent to landlord".
3. ✅ Backend: payment `status=succeeded`, bill `status=awaiting_rent_receipt`.

### 1.5 Manual `/check` works
```bash
ADMIN=$(curl -s -X POST "$API/api/auth/login" -H "Content-Type: application/json" \
  -d '{"email":"admin@nyumbaos.co.ke","password":"admin123"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

# Find any pending payment
PID=$(curl -s "$API/api/admin/export/payments.csv" -H "Authorization: Bearer $ADMIN" | grep ",pending," | head -1 | cut -d, -f1)

# Force a Safaricom truth check
curl -X POST "$API/api/payments/$PID/check" -H "Authorization: Bearer $ADMIN" | python3 -m json.tool
# → returns the real current status from Safaricom
```

---

## 2. All bill types use the same flow (not just rent)

For each bill type below, repeat 1.4 (happy path) + 1.1 (ignore path):

### 2.1 Water bill
1. Login as landlord → `/bills` → "Generate this month" or create a single water bill (1500 KES).
2. Tenant → Pay → dialog header: **"Pay water bill"**. Instructions also say "pay water bill to landlord".
3. Service fee = ceil(1500 × 0.025 / 10) × 10 = 40 KES.
4. Verify flow end-to-end.

### 2.2 Electricity
- Service fee = ceil(amount × 0.025 / 10) × 10. e.g. 2000 → 50 KES.

### 2.3 Service charge
- Same flow; dialog header reads "Pay service charge".

### 2.4 Other
- Catch-all: dialog reads "Pay other bill".

### 2.5 Rent
- Already covered in §1.

### Edge cases
- Tenant tries to submit rent receipt before paying fee → ✅ 400 "Pay the 2.5% service fee first".
- Bill already in `awaiting_landlord_confirmation` → Pay button hidden, Confirm/Reject shown to landlord.

---

## 3. Yard sale forced fee — same anti-false-positive

### 3.1 Listing stays in `pending_payment` until real STK confirms
1. Login as `tenant1@demo.nyumba` → `/yard-sale` → List Item.
2. Fill form + click **Pay KES 35 & Publish** (with phone `254708374149`).
3. ✅ Dialog shows "Awaiting M-Pesa confirmation".
4. **DO NOT enter PIN**. Wait 30s.
5. ✅ Toast: "Payment did not go through — DS timeout..." Pending state cleared.
6. ✅ Listing in DB: `status=pending_payment` still (NEVER falsely activated). It will sit there for cleanup.

### 3.2 Cancel pending yard sale STK
1. Repeat 3.1 but click **Cancel & close**.
2. ✅ `/payments/{id}/cancel` fires. Listing remains pending_payment (admin can delete from `/admin/moderation/yard-sale`).

### 3.3 Happy path
1. Enter PIN → ✅ listing flips to `active` + `contact_unlocked=true` within ~15s.

---

## 4. Viewing booking — same anti-false-positive

### 4.1 Prospect ignores STK
1. Incognito → `/marketplace/<unitId>` → Book → fill form → submit.
2. STK push fires to KES 200. Don't enter PIN.
3. After ~25s, frontend calls `/check`. Safaricom returns timeout.
4. ✅ Dialog shows "Payment did not go through — DS timeout..."
5. ✅ Backend viewing row stays in `pending_payment`, prospect QR is NOT issued, disbursement ledger has NO new row.

### 4.2 Happy path
1. Enter PIN → ✅ viewing flips to `scheduled`, prospect QR auto-issued, disbursement ledger gets a new row (caretaker 150 / platform 50).

---

## 5. Notification on failure

After any `status=failed` payment:
1. Login as the tenant who initiated → bell icon shows new notification.
2. ✅ Title: "Payment did not go through — DS timeout user cannot be reached" (or whichever Safaricom desc).
3. ✅ Body: "Your M-Pesa payment was not completed. Open the bill and try again."
4. ✅ Link goes to `/bills` (for bills) or `/marketplace` (for viewings).

---

## 6. Backend endpoint reference

### New / changed in Round 6
| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/payments/{id}/check` | any (owner or admin) | Force Safaricom STK status query + settle |
| POST | `/api/payments/{id}/cancel` | any (owner or admin) | Mark stuck pending payment as failed |
| changed | `/api/payments/mpesa/stk-push` | tenant | Now schedules real status poller (not blind demo callback) |
| changed | `_process_callback_payload` | internal | Notifies tenant on failure |

### Smoke
```bash
API=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d= -f2)
ADMIN=$(curl -s -X POST "$API/api/auth/login" -H "Content-Type: application/json" \
  -d '{"email":"admin@nyumbaos.co.ke","password":"admin123"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

# Pick any pending payment id (or create one via /payments/mpesa/stk-push)
curl -X POST "$API/api/payments/<pid>/check"  -H "Authorization: Bearer $ADMIN"
curl -X POST "$API/api/payments/<pid>/cancel" -H "Authorization: Bearer $ADMIN"
```

---

## 7. Manual end-to-end on real sandbox

1. Set `MPESA_DEMO_FALLBACK=false` (default after Round 6).
2. Tenant initiates fee payment with phone `254708374149`.
3. **DO NOT enter PIN**. Watch backend logs:
   ```
   tail -f /var/log/supervisor/backend.err.log
   ```
   Within ~15s you'll see the status_poll firing and Safaricom returning ResultCode `1037` (DS timeout).
4. ✅ payment row → `failed`. NO false positive.
5. Re-initiate, enter PIN this time → ✅ `succeeded` within ~15s.

---

## 8. Regression checklist

- [ ] 1.1 Ignored STK → payment fails (not falsely paid)
- [ ] 1.2 Cancelled STK → payment fails
- [ ] 1.3 In-dialog Cancel button works
- [ ] 1.4 Happy path STK paid → bill flips to awaiting_rent_receipt
- [ ] 1.5 `/payments/{id}/check` returns real Safaricom truth
- [ ] 2.1–2.4 Same flow works for water / electricity / service / other
- [ ] 3.1 Yard sale ignored STK → listing stays pending_payment, NOT active
- [ ] 3.3 Yard sale paid STK → listing active + contact_unlocked
- [ ] 4.1 Viewing ignored STK → no QR issued, no disbursement row
- [ ] 4.2 Viewing paid STK → scheduled + QR + disbursement row
- [ ] 5 Failure notification visible in bell
