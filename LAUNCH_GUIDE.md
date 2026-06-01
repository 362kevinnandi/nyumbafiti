# NYUMBA FITI — Launch Checklist

A practical, ordered checklist to take your rental management system from demo to a real product Nairobi landlords are using and paying with real M-Pesa.

---

## Stage 1 — Pre-Launch Configuration

### 1.1 Switch M-Pesa from Demo to Real STK Push
Right now the system runs in **DEMO MODE**: it simulates M-Pesa callbacks after ~4 seconds. To accept real money you need Safaricom Daraja credentials.

1. **Register at Safaricom Daraja**: https://developer.safaricom.co.ke (create a developer account → create an App → enable the "Lipa na M-Pesa Online" product).
2. Copy the **Consumer Key**, **Consumer Secret**, **Business Short Code** (sandbox: 174379 / production: your paybill or till), and **Passkey**.
3. Open `/app/backend/.env` and fill in:
   ```
   MPESA_CONSUMER_KEY="your_key"
   MPESA_CONSUMER_SECRET="your_secret"
   MPESA_SHORTCODE="174379"          # or your real paybill
   MPESA_PASSKEY="your_passkey"
   MPESA_ENVIRONMENT="sandbox"        # change to "production" when going live
   MPESA_CALLBACK_BASE_URL="https://your-public-domain.com"
   ```
4. Restart backend: `sudo supervisorctl restart backend`.
5. Test with a real Kenyan phone in sandbox: book a viewing or pay a bill — you should now get a real STK prompt.

> **Important**: `MPESA_CALLBACK_BASE_URL` must be a **publicly reachable HTTPS URL** (Safaricom's servers will call it). The Emergent preview URL works perfectly for this.

### 1.2 Replace demo data
Currently the database has demo records (`land@demo.com`, "Riverside Apartments", a demo caretaker, etc.). Either:
- Delete via MongoDB Compass / shell, or
- Build a `/admin/reset` endpoint (we can add this on request), or
- Tell your first real landlord to create their account and ignore the demo records.

### 1.3 Set a strong JWT secret
In `/app/backend/.env` change:
```
JWT_SECRET="a-long-random-string-only-you-know"
```
Generate one with: `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`.

### 1.4 Lock down CORS for production
Currently `CORS_ORIGINS="*"`. Once you have a final domain, change to:
```
CORS_ORIGINS="https://nyumba-os.co.ke,https://www.nyumba-os.co.ke"
```

---

## Stage 2 — Deployment

### 2.1 Deploy on Emergent (Recommended for fastest go-live)
1. In the Emergent UI click the **Deploy** button (top-right of the editor).
2. Emergent provisions a permanent URL like `https://your-app.emergent.host` (or your custom domain).
3. Set environment variables in the deployment config (same keys as `.env`).
4. Configure `MPESA_CALLBACK_BASE_URL` to the deployed URL.
5. Restart and smoke-test.

### 2.2 Custom domain (optional)
1. Buy `nyumba-os.co.ke` (or similar) on Truehost / Sasahost / Namecheap.
2. Point an `A` or `CNAME` record to the deployment URL.
3. Update `MPESA_CALLBACK_BASE_URL` to use the custom domain.
4. Re-register the callback URL with Safaricom.

### 2.3 Backups
- MongoDB Atlas (recommended): set up a free M0 cluster, change `MONGO_URL` to the connection string. Atlas does daily backups out of the box.
- Schedule a daily export of the `users`, `properties`, `units`, `bills`, `payments`, `viewings` collections to S3 / Google Drive.

---

## Stage 3 — Operations

### 3.1 Onboard your first 5–10 landlords manually
For week 1, **don't rely on self-registration**:
1. Demo the system to each landlord in person (15 mins, screen-shared).
2. Help them create their account, add their first property, add 2–3 tenants.
3. Show the tenant how to receive an M-Pesa STK push for rent.
4. Stay in WhatsApp contact for the first 2 rent cycles.

### 3.2 Monitor the first real M-Pesa transactions
- Watch `/var/log/supervisor/backend.*.log` for callbacks.
- For the first 10 transactions, manually reconcile each one in M-Pesa for Business vs. the Payments page in NYUMBA FITI.

### 3.3 Customer support channel
- Set up a single WhatsApp Business number for "NYUMBA FITI Help".
- Document common issues (M-Pesa prompt not received, wrong amount, forgot password) and the fix for each.

---

## Stage 4 — Growth Features (in priority order)

### P1 — Easy wins (1–2 days each)
- [ ] **SMS reminders** for overdue bills (Twilio / Africa's Talking). Day 1, day 7, day 14.
- [ ] **Email notifications**: bill issued, payment received, issue resolved (Resend or SendGrid).
- [ ] **Password reset flow** via email magic link.
- [ ] **Rent receipt PDF download** after each successful M-Pesa payment.
- [ ] **Scheduled monthly bill cron** — auto-generate on the 1st of each month instead of one-click.
- [ ] **Property image uploads** (S3 / object storage) — currently you paste a URL.

### P2 — Differentiating features (3–5 days each)
- [ ] **Featured listings** — landlords pay a monthly fee to pin their property to the top of the marketplace.
- [ ] **Tenant move-in/move-out workflow** with deposit tracking.
- [ ] **Lease document storage** (PDF upload per tenant).
- [ ] **Multi-property analytics** — occupancy trends, revenue charts, average tenancy length.
- [ ] **Bulk tenant import** via CSV (helpful when landlord migrates from spreadsheets).
- [ ] **Maintenance vendor marketplace** — caretakers can request quotes from plumbers/electricians.

### P3 — Stretch (1–2 weeks each)
- [ ] Mobile app (React Native — large chunk of the React code is reusable).
- [ ] Multi-currency / multi-country (Uganda, Tanzania mobile money operators).
- [ ] Public landlord directory + reviews.
- [ ] Tenant credit scoring based on payment history.

---

## Stage 5 — Compliance & Trust (before charging real money at scale)

### 5.1 Safaricom Daraja Production Approval
- The sandbox is free and limit-free. Production requires Safaricom to approve your business + your callback URL.
- Submit through the Daraja portal → "Go Live" workflow → upload KRA PIN, business permit, etc.

### 5.2 Data protection
- Kenya's **Data Protection Act 2019** requires registration with the Office of the Data Protection Commissioner (ODPC) — fees ~KES 4,000 for small businesses.
- Add a Privacy Policy page (we can scaffold one) and a cookie banner.

### 5.3 Terms of Service
- Clarify: who owns the rent collected, how disputes between landlord/tenant are handled, refund policy on viewing fees.

---

## Stage 6 — Revenue Model Options

| Model | Pros | Cons |
|---|---|---|
| **Take a % of every rent payment** (e.g. 1–2%) | Recurring, scales with landlord success | Landlords resist platform fees on rent |
| **Monthly subscription per landlord** (e.g. KES 500–2,000) | Predictable revenue | Hard to acquire first 100 landlords |
| **Keep the KES 200 viewing fee** (or split with landlord) | Self-explanatory, prospect already pays | Volume depends on listing inventory |
| **Featured listings** | Pure platform revenue | Need critical mass of listings first |
| **Hybrid: free for ≤5 units + paid tiers** | Easy adoption | Complex pricing communication |

**Recommendation for Nairobi market**: start with **free for ≤5 units + KES 1,000/mo for unlimited units + keep the KES 200 viewing fee**. Revisit after 50 landlords.

---

*Last updated: Feb 2026*
