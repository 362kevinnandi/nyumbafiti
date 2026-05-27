# Launching Nyumba OS at **nyumbafiti.co.ke** — Step-by-step

> Goal: ship the app to your own domain, with a production MongoDB, real Safaricom Daraja credentials, and SSL. Estimated time: **2–4 hours** end to end.

---

## 0. What you have today

| Layer | Stack | State |
|---|---|---|
| Frontend | React 19 + Tailwind | Built with `yarn build` → static `frontend/build/` |
| Backend  | FastAPI + Motor (async Mongo) | Single `uvicorn` process on port 8001 |
| Database | MongoDB | Currently embedded preview Mongo |
| Payments | M-Pesa Daraja STK Push | Sandbox keys wired; production needs Go-Live |
| AI       | Claude Sonnet 4.5 via Emergent LLM key | Works as-is in prod |
| File uploads | Local disk `backend/uploads/` | Need persistent volume in prod |

---

## 1. Recommended hosting platform: **Render**

Reasons:
- One-click web services for **FastAPI** (Python) and **static sites** (React build).
- Free-tier **persistent disk** (1 GB) for `uploads/` survives deploys.
- One-click managed Mongo via **MongoDB Atlas** integration.
- Free TLS + custom-domain CNAME setup in ~5 minutes.
- Sleep policy on free tier hibernates after inactivity — upgrade to **Starter ($7/mo)** for always-on.

**Alternative**: Railway ($5/mo flat) is simpler if you prefer one host for backend + Mongo. Vercel is **not** recommended for the backend (no long-running Python).

---

## 2. Provision MongoDB Atlas

1. Create a free account at **https://cloud.mongodb.com**.
2. Build a new **M0 cluster** (free, 512 MB) in the `africa-south1` or `eu-west-1` region (lowest Nairobi latency).
3. Database Access → add a user `nyumba_app` with a strong password.
4. Network Access → add `0.0.0.0/0` (or restrict to Render's egress IPs once you have them).
5. Copy the connection string: `mongodb+srv://nyumba_app:<pw>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority`.

---

## 3. Push your code to GitHub

In Emergent: click **Save to GitHub** in the chat input. Once your repo (e.g. `github.com/yourname/nyumbafiti`) is up:

```bash
# Your local clone, once
git clone https://github.com/yourname/nyumbafiti.git
cd nyumbafiti
```

Repo layout that Render needs:
```
backend/        # FastAPI app + uploads/
frontend/       # React app (yarn build → build/)
```

---

## 4. Render — backend service

1. Render dashboard → **New → Web Service** → connect GitHub repo.
2. Settings:
   - **Name**: `nyumbafiti-api`
   - **Root Directory**: `backend`
   - **Runtime**: Python 3.11
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn server:app --host 0.0.0.0 --port $PORT`
   - **Plan**: Starter ($7/mo recommended) — Free tier sleeps after 15 min.
3. **Disks** → add 1 GB disk mounted at `/app/uploads` (mirror the local `backend/uploads/`).
4. Set environment variables (copy from `backend/.env`):

   ```
   MONGO_URL = mongodb+srv://nyumba_app:<pw>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
   DB_NAME = nyumba_prod
   CORS_ORIGINS = https://nyumbafiti.co.ke,https://www.nyumbafiti.co.ke
   JWT_SECRET = <generate-a-64-char-random-string>
   JWT_ALGO = HS256
   JWT_EXPIRY_HOURS = 72
   MPESA_ENVIRONMENT = production       # see §6 below
   MPESA_CONSUMER_KEY = <prod-key>
   MPESA_CONSUMER_SECRET = <prod-secret>
   MPESA_SHORTCODE = <your-paybill-or-buy-goods-number>
   MPESA_PASSKEY = <prod-passkey>
   MPESA_CALLBACK_BASE_URL = https://api.nyumbafiti.co.ke
   MPESA_CALLBACK_SECRET = <random-string-make-up-your-own>
   MPESA_DEMO_FALLBACK = false           # IMPORTANT: false in prod
   ADMIN_EMAIL = your-real-admin@nyumbafiti.co.ke
   ADMIN_PASSWORD = <strong-bootstrap-password>
   ADMIN_FULL_NAME = Founder
   ADMIN_PHONE = 2547XXXXXXXX
   EMERGENT_LLM_KEY = sk-emergent-...    # keep the same key from preview
   ```

5. Tweak `backend/uploads/` references: in `server.py` confirm the mount path of `/api/uploads` is `os.path.join(os.path.dirname(__file__), "uploads")` — this stays relative to the service root, which Render serves out of `backend/`.

6. Add a custom domain → **api.nyumbafiti.co.ke** (will produce a CNAME target).

---

## 5. Render — frontend static site

1. Render dashboard → **New → Static Site** → same GitHub repo.
2. Settings:
   - **Name**: `nyumbafiti-web`
   - **Root Directory**: `frontend`
   - **Build Command**: `yarn install && yarn build`
   - **Publish Directory**: `build`
3. Env vars:
   ```
   REACT_APP_BACKEND_URL = https://api.nyumbafiti.co.ke
   ```
4. Add a **rewrite/redirect** rule so React Router works:
   - Source `/*` → Destination `/index.html` → Status `200` (Rewrite).
5. Add a custom domain → **nyumbafiti.co.ke** + **www.nyumbafiti.co.ke**.

---

## 6. DNS at your registrar (where you bought nyumbafiti.co.ke)

| Type | Host | Value | Notes |
|---|---|---|---|
| A or ANAME | @ | (Render IP / `nyumbafiti-web.onrender.com`) | Apex → frontend |
| CNAME | www | `nyumbafiti-web.onrender.com` | Apex alias |
| CNAME | api | `nyumbafiti-api.onrender.com` | Backend |

Render auto-issues Let's Encrypt SSL once DNS propagates (5 min – 24 h).

---

## 7. M-Pesa **Production** (Go-Live)

You currently have sandbox keys. Production needs a separate app **plus** a Safaricom Go-Live application.

### 7.1 Pre-requisites
- Registered KE business (sole-prop or limited company).
- **Paybill** or **Buy Goods Till** number (apply via Safaricom dealer; 1–3 days).
- KRA PIN, certificate of incorporation, business permit.

### 7.2 Daraja portal
1. Go to **https://developer.safaricom.co.ke** → log in or create account.
2. **My Apps** → create a *production* app:
   - Tick **Lipa Na M-Pesa Online** (STK Push) + **M-Pesa Express**.
3. **Go-Live wizard**:
   - Submit business name, paybill, callback URL `https://api.nyumbafiti.co.ke/api/payments/mpesa/callback/<your-callback-secret>`.
   - Upload Cert of Inc + KRA PIN + business permit.
   - Wait ~1–3 business days for approval.
4. Once approved, retrieve from the production app:
   - `Consumer Key` → `MPESA_CONSUMER_KEY`
   - `Consumer Secret` → `MPESA_CONSUMER_SECRET`
   - `Passkey` (under Lipa Na M-Pesa → Production) → `MPESA_PASSKEY`
   - Your paybill / till number → `MPESA_SHORTCODE`

### 7.3 Production checklist
- [ ] `MPESA_ENVIRONMENT=production` in Render env.
- [ ] `MPESA_DEMO_FALLBACK=false` (very important — no fake callbacks in prod).
- [ ] Whitelist Safaricom callback IPs in any firewall (Render Free tier allows all egress).
- [ ] Test with a small real STK push from your own M-Pesa first (KES 10 → yourself).
- [ ] Verify `/api/payments/mpesa/callback/<secret>` returns 200 and updates the payment in Atlas.

### 7.4 Common Go-Live gotchas
- Callback URL must be **HTTPS** and **publicly reachable** (no path params before the secret).
- The `AccountReference` field is capped at 12 chars in production (currently we cap at 20 — Safaricom truncates).
- Their callback retries up to 4 times over 60 seconds; idempotency is already wired in our `_process_callback_payload`.

---

## 8. First-time prod bootstrap

```bash
# In Render shell for the backend service (Settings → Shell)
python3 seed_demo_data.py --reset   # OPTIONAL — only if you want demo data in prod
```

Or skip seeding entirely — admin user is auto-created from `ADMIN_EMAIL` / `ADMIN_PASSWORD` on first startup.

Then log in at `https://nyumbafiti.co.ke/login`, head to `/admin/settings` and:
1. Confirm commission rate (default 3.5%).
2. `/admin/properties` → review & approve real landlord submissions.
3. `/admin/users` → invite your first real landlords (manual reset-credentials to set their password).

---

## 9. Day-2 operations

| Task | How |
|---|---|
| Backups | Atlas → Backup tab → enable continuous (paid tier) OR `mongodump` cron from a tiny worker. |
| Image uploads | Atlas free tier has 5 GB. If you outgrow disk on Render, move uploads to **S3** or **Cloudflare R2** (adapter pattern: replace `/api/uploads` mount with a presigned-URL flow). |
| Logs | Render → Service → Logs. Filter by `ERROR`. |
| Custom email/SMS | Add **Resend** (email) + **Africa's Talking** (SMS) integrations and wire into `notifications.py`. |
| Monitoring | Free **UptimeRobot** ping on `https://api.nyumbafiti.co.ke/api/auth/me` every 5 min. |

---

## 10. Domain checklist before launch day

- [ ] Domain registered at any registrar (Truehost, Domains.co.ke, Cloudflare).
- [ ] DNS records pointed at Render (§6).
- [ ] Both `nyumbafiti.co.ke` and `www.nyumbafiti.co.ke` resolve to the static site (test with `curl -I https://nyumbafiti.co.ke`).
- [ ] `api.nyumbafiti.co.ke` returns `{"status":"ok"}` from `GET /api/auth/me` with a valid token.
- [ ] M-Pesa Go-Live approved + production keys swapped in.
- [ ] At least one real **landlord** seeded so the marketplace isn't empty.
- [ ] Privacy policy + terms of service drafted (mandatory for M-Pesa Go-Live).
- [ ] Google Analytics / Plausible script added to `frontend/public/index.html` (optional).

---

## 11. Quick rollback plan

If something breaks post-deploy:
1. Render → service → **Deploys** → click the previous green deploy → **Redeploy**.
2. Atlas point-in-time restore (paid) → restore to ~5 min before incident.
3. If M-Pesa goes wrong: set `MPESA_ENVIRONMENT=sandbox` and `MPESA_DEMO_FALLBACK=true` to halt real money flow while you investigate.

---

**You're done.** First successful tenant rent payment via real M-Pesa → 🎉.
