# NyumbaOS — Nairobi Rental Management Platform

Multi-role SaaS for Kenyan landlords, tenants, caretakers, security guards, prospects and platform admins. M-Pesa split-payment monetization, digital leases, visitor QR passes, public marketplace, paid viewings, Yard Sale and an AI concierge.

> **Live target:** `https://nyumbafiti.co.ke`
> **Stack:** FastAPI (Python 3.11) · React 19 (CRACO) · MongoDB · M-Pesa Daraja · Claude Sonnet 4.5

---

## Table of contents
1. [Local development](#1-local-development)
2. [Environment variables](#2-environment-variables)
3. [Seeding demo data](#3-seeding-demo-data)
4. [Deploy to Railway](#4-deploy-to-railway)
5. [Deploy to Render](#5-deploy-to-render-recommended-blueprint)
6. [Connect the domain `nyumbafiti.co.ke`](#6-connect-the-domain-nyumbafiticoke)
7. [M-Pesa: sandbox → production](#7-m-pesa-sandbox--production)
8. [Project layout](#8-project-layout)

---

## 1. Local development

### Prerequisites
- Python **3.11** (Daraja SDKs + motor are picky about 3.12+)
- Node **18+** and **Yarn** (`npm i -g yarn`)
- MongoDB **6+** locally OR a free MongoDB Atlas cluster

### Clone
```bash
git clone https://github.com/<your-user>/nyumbafiti.git
cd nyumbafiti
```

### Backend
```bash
cd backend
python3.11 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env            # then edit — see section 2
uvicorn server:app --reload --port 8001
```
Backend health-check: <http://localhost:8001/api/> → `{"message":"NyumbaOS API"}`
Swagger docs: <http://localhost:8001/docs>

### Frontend (new terminal)
```bash
cd frontend
yarn install
cp .env.example .env            # set REACT_APP_BACKEND_URL=http://localhost:8001
yarn start                      # opens http://localhost:3000
```

### MongoDB
**Option A — Local:**
```bash
# macOS
brew tap mongodb/brew && brew install mongodb-community
brew services start mongodb-community

# Ubuntu/Debian
sudo apt install -y mongodb
sudo systemctl start mongodb
```
Then in `backend/.env` set `MONGO_URL=mongodb://localhost:27017` and `DB_NAME=nyumba_os`.

**Option B — Atlas (recommended even for local):**
1. <https://mongodb.com/cloud/atlas> → create a **free M0 cluster**
2. Database Access → create user
3. Network Access → allow your IP (or `0.0.0.0/0` for dev)
4. Connect → copy SRV string → paste as `MONGO_URL`

---

## 2. Environment variables

### `backend/.env`
```dotenv
MONGO_URL=mongodb://localhost:27017
DB_NAME=nyumba_os
JWT_SECRET=change-me-to-a-random-32-char-string

# Super admin seeded on first boot
ADMIN_EMAIL=admin@nyumbafiti.co.ke
ADMIN_PASSWORD=change-me-strong

# Emergent Universal LLM Key (Profile → Universal Key in app.emergent.sh)
EMERGENT_LLM_KEY=sk-emergent-xxxxxxxx

# M-Pesa Daraja — sandbox values for now
MPESA_CONSUMER_KEY=sandbox_consumer_key
MPESA_CONSUMER_SECRET=sandbox_consumer_secret
MPESA_PASSKEY=sandbox_passkey
MPESA_SHORTCODE=174379
MPESA_CALLBACK_BASE_URL=http://localhost:8001
MPESA_CALLBACK_SECRET=any-random-string-here
MPESA_DEMO_FALLBACK=false
```
> ⚠️ Callback URL is built as `{MPESA_CALLBACK_BASE_URL}/api/payments/mpesa/callback/{MPESA_CALLBACK_SECRET}`. For local dev Safaricom can't reach `localhost`, so the platform polls Safaricom's STKQuery API every 15s/45s/95s/170s/270s — payment confirmations still work end-to-end without a public tunnel.

### `frontend/.env`
```dotenv
REACT_APP_BACKEND_URL=http://localhost:8001
WDS_SOCKET_PORT=443
ENABLE_HEALTH_CHECK=false
```

### `frontend/.env.production`
```dotenv
REACT_APP_BACKEND_URL=https://api.nyumbafiti.co.ke
```

---

## 3. Seeding demo data
After the backend boots once (auto-seeds super-admin), populate fixtures:
```bash
cd backend
source venv/bin/activate
python3 seed_demo_data.py --reset
```
That gives you 6 properties, 12 units, 4 tenants, 2 caretakers, 2 security, plus yard-sale and community content.

**Demo logins** (see `memory/test_credentials.md` for the full list):
| Role | Email | Password |
|---|---|---|
| Super admin | `admin@nyumbafiti.co.ke` | (from `ADMIN_PASSWORD`) |
| Landlord | `mary@demo.nyumba` | `demo123` |
| Tenant | `tenant1@demo.nyumba` | `demo123` |
| Caretaker | `ck1@demo.nyumba` | `demo123` |
| Security | `sg1@demo.nyumba` | `demo123` |

---

## 4. Deploy to Railway

Railway is the fastest path because uploads (property images, lease PDFs, yard-sale photos) need a persistent volume and Railway gives you one for free.

### 4.1 Push to GitHub
Inside the Emergent chat, click **Save to GitHub** → pick the repo → push `main`. Locally:
```bash
git remote add origin https://github.com/<you>/nyumbafiti.git
git fetch && git pull
```

### 4.2 Provision MongoDB Atlas (free)
Follow [section 1](#1-local-development) → copy the SRV string.

### 4.3 Create the backend service
1. <https://railway.app> → **New Project → Deploy from GitHub repo** → pick the repo
2. After detection, set **Root directory** to `backend`
3. **Variables** tab — paste everything from `backend/.env` *except* swap:
   - `MONGO_URL` → the Atlas SRV string
   - `MPESA_CALLBACK_BASE_URL` → (leave blank for now, fill after step 4.4)
4. Settings → Networking → **Generate Domain** (gives you `nyumbafiti-backend-production.up.railway.app`)
5. Settings → **Volume** → mount `/app/uploads` size 1GB. *Without this, uploaded images/PDFs disappear on each redeploy.*
6. Re-open Variables → set:
   ```
   MPESA_CALLBACK_BASE_URL=https://nyumbafiti-backend-production.up.railway.app
   ```
   Railway will auto-redeploy.

### 4.4 Create the frontend service
1. Same project → **+ New → GitHub Repo** (same repo)
2. Root directory: `frontend`
3. Variables: `REACT_APP_BACKEND_URL=https://nyumbafiti-backend-production.up.railway.app`
4. Settings → Networking → **Generate Domain**

The included `frontend/railway.json` and `backend/railway.json` handle build + start commands automatically.

### 4.5 Verify
- `https://<backend>.up.railway.app/api/` → `{"message":"NyumbaOS API"}`
- `https://<frontend>.up.railway.app/` → login screen renders
- Login as super-admin → Settings → confirm `service_fee_flat_kes = 33`

---

## 5. Deploy to Render (recommended blueprint)

Render is great if you prefer a declarative, version-controlled setup. The repo already contains `render.yaml`.

### 5.1 One-click blueprint
1. Push to GitHub (same as 4.1)
2. <https://dashboard.render.com> → **New → Blueprint** → connect the repo
3. Render reads `render.yaml` and proposes two services + one persistent disk
4. Fill in the `sync: false` secrets in the dashboard:
   - `MONGO_URL`, `EMERGENT_LLM_KEY`, `MPESA_*` keys, `ADMIN_PASSWORD`, and `REACT_APP_BACKEND_URL`
5. Click **Apply** — first deploy takes ~5 min

### 5.2 After first deploy
- Copy the backend URL (e.g. `https://nyumbafiti-backend.onrender.com`)
- Set `MPESA_CALLBACK_BASE_URL` to that URL
- Set frontend `REACT_APP_BACKEND_URL` to that URL (or your custom `api.nyumbafiti.co.ke`)
- Trigger a manual redeploy on both services

> Render free tier sleeps after 15 min of idle. Upgrade the backend to **Starter ($7/mo)** before going live — M-Pesa callbacks will be missed otherwise.

---

## 6. Connect the domain `nyumbafiti.co.ke`

You'll point **two** subdomains:
- `nyumbafiti.co.ke` (apex, optionally `www`) → frontend
- `api.nyumbafiti.co.ke` → backend (so the M-Pesa callback URL is stable)

### Railway
1. Frontend service → Settings → Domains → **Custom Domain** → `nyumbafiti.co.ke` and `www.nyumbafiti.co.ke`. Railway shows you the CNAME target.
2. Backend service → Settings → Domains → **Custom Domain** → `api.nyumbafiti.co.ke`.

### Render
Same flow under **Settings → Custom Domains** on each service.

### DNS records (at your registrar — KENIC, Truehost, Sasahost, Cloudflare etc.)

| Type | Name | Value | TTL |
|---|---|---|---|
| `CNAME` | `www` | `<frontend>.up.railway.app` *(or `.onrender.com`)* | 300 |
| `CNAME` | `api` | `<backend>.up.railway.app` *(or `.onrender.com`)* | 300 |
| `A` *(apex)* | `@` | IP shown by the platform | 300 |

> Many `.co.ke` registrars don't support CNAME on the apex. Two workarounds:
> - **Use Cloudflare** (free) for DNS — it supports CNAME flattening on the apex
> - **Or** redirect `nyumbafiti.co.ke → www.nyumbafiti.co.ke` at the registrar and only run the app on `www`

After saving, SSL is auto-provisioned by Let's Encrypt within 2–10 min. Check with `https://dnschecker.org`.

### Final post-domain edits
Once `api.nyumbafiti.co.ke` resolves:
- Backend env: `MPESA_CALLBACK_BASE_URL=https://api.nyumbafiti.co.ke`
- Frontend env: `REACT_APP_BACKEND_URL=https://api.nyumbafiti.co.ke`
- Redeploy both

---

## 7. M-Pesa: sandbox → production

You're launching on **sandbox** (`MPESA_SHORTCODE=174379`). When you're ready:

1. <https://developer.safaricom.co.ke> → log in with the same account
2. **Go-Live Wizard** — submit the production app for review. Required:
   - Real registered company name + KRA PIN
   - Production paybill / till (yours is `247247`)
   - Public callback URL → `https://api.nyumbafiti.co.ke/api/payments/mpesa/callback/<MPESA_CALLBACK_SECRET>`
3. After approval, Safaricom emails new **production** Consumer Key, Consumer Secret, and Passkey.
4. Update the deployed backend env:
   ```
   MPESA_CONSUMER_KEY=<prod_key>
   MPESA_CONSUMER_SECRET=<prod_secret>
   MPESA_PASSKEY=<prod_passkey>
   MPESA_SHORTCODE=247247
   ```
5. In `backend/mpesa.py` the base URL switches automatically when keys are set — no code change needed; production = `https://api.safaricom.co.ke`.
6. Smoke test with a real KES 33 push to your own phone before flipping it on for tenants.

Detailed go-live checklist: see [`LAUNCH_nyumbafiti.md`](./LAUNCH_nyumbafiti.md).

---

## 8. Project layout
```
/
├── backend/
│   ├── server.py              # FastAPI entry — import this in uvicorn
│   ├── routers/               # auth, properties, bills, payments, viewings, admin, …
│   ├── mpesa.py               # Daraja STK push + polling + token cache
│   ├── seed_demo_data.py      # demo fixtures (run with --reset)
│   ├── requirements.txt
│   ├── runtime.txt            # python-3.11.9
│   ├── Procfile               # Railway/Render fallback
│   ├── railway.json           # Railway service config
│   └── uploads/               # MUST be a mounted volume in production
├── frontend/
│   ├── src/                   # React 19 + CRACO
│   ├── package.json
│   ├── .env.production
│   ├── serve.json             # SPA rewrites for `npx serve`
│   ├── vercel.json            # SPA rewrites if you ever try Vercel
│   └── railway.json
├── render.yaml                # Render blueprint (both services in one click)
├── memory/
│   ├── PRD.md                 # product spec + changelog
│   └── test_credentials.md
└── LAUNCH_nyumbafiti.md       # go-live checklist
```

---

## Common pitfalls
- **Frontend can't reach backend in prod** → CORS. `server.py` already allows the production domain via `CORSMiddleware` — but if you change the domain, update `ALLOWED_ORIGINS` accordingly.
- **STK pushes return 500** → Safaricom rejects `&`, `%`, `=` in `TransactionDesc`. The codebase already strips them.
- **Uploads vanish after redeploy** → you forgot the persistent volume (Railway Volume / Render Disk) on `/uploads`.
- **`MONGO_URL` rejected on Atlas** → URL-encode the password (`@` becomes `%40`).
- **Confirmations tab empty** → fixed in Round 7 (`_compute_status` no longer overwrites `awaiting_landlord_confirmation`).

---

## Support
Built on the **Emergent** platform. Use **Save to GitHub** in the chat input for any future push.
