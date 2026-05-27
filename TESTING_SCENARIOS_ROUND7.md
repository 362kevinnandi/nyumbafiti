# Round 7 — Sandbox STK push fixes (`&` sanitization, token cache, retry endpoint)

## What was breaking

You hit:
> `M-Pesa request failed: Server error '500 Internal Server Error' for url 'https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest'`

Two compounding root causes:
1. **Ampersand in `TransactionDesc`** ("Unlock & publish") broke Safaricom's XSLT parser → 500 with `XSLEvaluationFailed` error.
2. **No oauth token caching** → we hit `/oauth/v1/generate` on every payment call → Safaricom started rate-limiting (429/403) → cascading failures.

## What was fixed
- `mpesa.py::_sanitize_text()` — strips `&`, `<`, `>`, `/`, etc. from `TransactionDesc` & `AccountReference` before sending.
- `mpesa.py::get_access_token()` — caches token for ~55 minutes (Safaricom expires at 3599s; we refresh 30s early).
- `yardsale_router.py` — if STK push raises (Safaricom 500), the listing is still saved as `pending_payment` + a new `/yard-sale/listings/{lid}/retry-unlock` endpoint lets the seller retry without redoing the form.
- Frontend YardSale dialog — handles `payment: null + stk_error` response by showing a Retry button.
- Yard sale "My listings" now includes the seller's own `pending_payment` drafts so they can retry from the listing detail page too.

## About paybill 247247 in sandbox

**Sandbox cannot push to 247247.** Safaricom sandbox only has ONE test paybill: `174379`. Real STK to 247247 only works after Go-Live with your production keys + the matching production passkey.

In the UI everywhere, NyumbaOS labels the platform paybill as **247247 / 0740479864** (your production paybill). When Go-Live happens, you change ONE env var (`MPESA_SHORTCODE=247247` + matching production passkey) and everything just works — same code path.

---

## Testing scenarios

### Pre-flight
```bash
API=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d= -f2)
TT=$(curl -s -X POST "$API/api/auth/login" -H "Content-Type: application/json" \
  -d '{"email":"tenant1@demo.nyumba","password":"demo123"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
```

### 1. Yard sale create — STK fires successfully

```bash
curl -X POST "$API/api/yard-sale/listings" -H "Authorization: Bearer $TT" \
  -F "title=Coffee table" -F "price=5000" -F "category=furniture" \
  -F "phone_number=254708374149" -F "description=Slightly used"
```

Expected response:
```json
{
  "listing": { "id": "...", "status": "pending_payment", "contact_unlocked": false, ... },
  "payment": {
    "payment_id": "...",
    "amount": 35,
    "demo_mode": false,
    "message": "Success. Request accepted for processing"
  }
}
```

Then test phone `254708374149` receives the STK push for **KES 35** to paybill **174379** account `POST-<lid8>`.

### 2. Sandbox is down → retry path

If Safaricom returns 500 (XSL bug, rate-limit, etc.), response becomes:
```json
{
  "listing": { ..., "status": "pending_payment" },
  "payment": null,
  "stk_error": "M-Pesa request failed: Server error '500 ...'",
  "message": "Listing saved as draft. M-Pesa was unreachable — open the listing and tap 'Pay to publish' to retry."
}
```

Frontend now shows a red "M-Pesa unreachable" panel + **Retry STK push** button. Click it → calls:

```bash
curl -X POST "$API/api/yard-sale/listings/<lid>/retry-unlock" \
  -H "Authorization: Bearer $TT" \
  -H "Content-Type: application/json" \
  -d '{"phone_number":"254708374149"}'
```

✅ Each retry uses cached token (no oauth hammering).

### 3. Viewing booking — STK fires to 174379 (KES 200)

```bash
UNITID=$(curl -s "$API/api/public/listings" | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d[0]["id"])')
curl -X POST "$API/api/public/viewings" -H "Content-Type: application/json" \
  -d "{
    \"unit_id\":\"$UNITID\",
    \"prospect_name\":\"Real Test\",
    \"prospect_email\":\"realtest@demo.nyumba\",
    \"prospect_phone\":\"254708374149\",
    \"scheduled_date\":\"2026-05-30\",
    \"scheduled_time\":\"15:00\"
  }"
```

Expected: `"demo_mode": false` + `"message": "Success. Request accepted for processing"`.

Test phone receives STK push for **KES 200** to paybill **174379** account `VIEW-<vid8>`.

### 4. Rent/bill 2.5% service fee STK

```bash
# tenant initiates fee payment on a 10,000 KES water bill → fee should be 250 KES
curl -X POST "$API/api/payments/mpesa/stk-push" -H "Authorization: Bearer $TT" \
  -H "Content-Type: application/json" \
  -d '{"bill_id":"<bill_id>","phone_number":"254708374149"}'
```

Expected: STK push fires for **KES 250** to paybill **174379**. After PIN entry, callback marks payment succeeded + bill flips to `awaiting_rent_receipt`.

### 5. Verify token caching

After 5+ successful STK pushes in a row, check logs:
```bash
grep "oauth/v1/generate" /var/log/supervisor/backend.err.log | tail -5
```
Should see only ONE oauth call per ~55min (not one per STK push).

### 6. False-positive prevention (Round 6 still holds)

1. Initiate yard sale create → DO NOT enter PIN on phone.
2. Wait 30 seconds.
3. Frontend auto-calls `/payments/<pid>/check` at +25s.
4. ✅ Payment marked `failed` (Safaricom returned ResultCode 1037 timeout).
5. ✅ Listing stays in `pending_payment` (NOT activated).

### 7. Manual cancel

While STK is in-flight, click **Cancel & close** in the yard sale dialog.
```bash
curl -X POST "$API/api/payments/<pid>/cancel" -H "Authorization: Bearer $TT"
```
✅ Payment status flips to `failed` with `result_desc="Cancelled by user"`.

---

## Checklist

- [ ] Yard sale create — STK push fires successfully to 174379 in sandbox
- [ ] TransactionDesc with `&`, `<`, `/` characters doesn't break STK
- [ ] Multiple back-to-back STK pushes use cached oauth token (one 200 in logs, then nothing)
- [ ] When Safaricom flakes (500), listing saves as draft + Retry button works
- [ ] Viewing booking STK push fires to 174379 (KES 200) in sandbox
- [ ] Bill payment STK fires for 2.5% fee in sandbox
- [ ] Ignored STK → payment correctly marked failed (Round 6 still working)
- [ ] Cancel button on yard sale pending state aborts the STK
- [ ] Listing visible only to seller while in pending_payment status

---

## Notes for Go-Live

When you're ready for production:
1. Apply for **Go-Live** in Daraja portal (1-3 weeks approval).
2. In `/app/backend/.env`:
   ```
   MPESA_ENVIRONMENT=production
   MPESA_CONSUMER_KEY=<your production key>
   MPESA_CONSUMER_SECRET=<your production secret>
   MPESA_SHORTCODE=247247
   MPESA_PASSKEY=<your production passkey for paybill 247247>
   MPESA_DEMO_FALLBACK=false
   ```
3. Restart backend. STK pushes now go to real 247247.
4. See `/app/LAUNCH_nyumbafiti.md` §7 for full Go-Live runbook.
