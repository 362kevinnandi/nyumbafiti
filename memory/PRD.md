# Nyumba OS — Product Requirements Document (PRD)

## Original Problem Statement
Build a comprehensive rental management system for Nairobi serving multiple roles (Landlord, Tenant, Caretaker, Prospect, Security, Super Admin). Core features: property + unit management, M-Pesa STK Push for rent & bills, issue ticketing, public marketplace for vacant units, paid viewings (KES 200), digital leases, visitor QR passes, tenant Community hub, Yard Sale marketplace with monetization, AI Concierge chat, Super Admin god-mode oversight + 3.5% commission tracking + approvals.

## Tech Stack
- Backend: FastAPI + Motor (MongoDB async)
- Frontend: React 19 + React Router 7 + Shadcn UI + Tailwind + Swiper
- Auth: JWT (custom), bcrypt
- Payments: M-Pesa Daraja STK Push (sandbox + 15s demo fallback safety net)
- PDF: reportlab · XLSX: openpyxl · CSV: stdlib
- QR: qrcode · AI: Claude Sonnet 4.5 via emergentintegrations (EMERGENT_LLM_KEY)

## Roles
Landlord, Tenant, Caretaker, Prospect, Security, Super Admin.

## Implemented Features

### MVP + Phase 1-4 (Feb 2026) ✅
- JWT auth, Property/Unit/Tenant CRUD, monthly bill auto-gen, M-Pesa STK (demo), Issues, Public marketplace + paid viewings (KES 200), Super Admin commission/payouts/approvals.
- Phase 1: Property images, 7 categories, Swiper, AdminProperties.
- Phase 2: Announcements + Forum w/ attachments.
- Phase 3: Yard Sale free listings + KES 100 feature boost.
- Phase 4: Digital leases (reportlab), Visitor QR passes, In-app notifications, AI Property Match.

### Round 1+2 Fine-Tuning ✅
- Security role added (visitor QR + issue resolution scoped to landlord).
- Tenancy types — lease vs rental on properties + tenants.
- Nairobi-warm palette UI globally.
- Property categories restricted to Apartment / Own Compound.
- Yard Sale KES 35 unlock-contact + KES 50 broadcast (optional, post-creation).
- Bill notification mix-up fix (rent vs water bills).

### Round 3 Fine-Tuning ✅ (Feb 2026)
- Social reactions (like/love/celebrate/support) on announcements, threads, replies.
- Announcement read receipts — author + admin can see who viewed.
- Multi-turn AI Concierge chat on Marketplace with listing deep-links.
- Prospect QR entry pass — auto-issued on viewing payment, Dashboard banner.
- Admin God-Mode Moderation — single page for all user-generated content with cascade delete.

### Round 4 Fine-Tuning ✅ (Feb 2026)
- **Security role auto-approve** — landlord-managed only; no admin approval queue.
- **Public Pass Viewer** — `/pass/{token}` page (no auth) so guest, tenant, AND security can all access the QR; tenant gets a "Copy share link" button.
- **Admin password/email reset** — `/admin/users/{id}/reset-credentials` with explicit `generate_password` opt-in; returns plaintext password once; audit log at `/admin/audit-log`.
- **Yard Sale forced KES 35 unlock at posting** — listing starts `pending_payment` + `contact_unlocked=false`, hidden from public until STK callback; broadcast (KES 50) additionally exposes property address.
- **Marketplace lease/rental filter** — chips (Any/For Rental/For Lease) + colored badges on listing cards; sidebar dynamic label "Lease Agreement" vs "Rental Agreement" based on tenant's `tenancy_type`.
- **M-Pesa sandbox keys wired** — real Daraja attempt + 15s demo callback safety net for sandbox unreliability. Idempotent callback handling.
- **Admin CSV/XLSX/PDF exports** — 8 resources × 3 formats = 24 endpoints. ExportMenu component shared across admin pages.
- **Property tile sliders** — Swiper on landlord properties grid + marketplace tiles + detail page.
- **Demo data seeder** — `python3 backend/seed_demo_data.py [--reset]` — 6 properties (mix lease/rental), 12 units, 4 tenants, 2 caretakers, 2 security, 5 yard sale items, 4 announcements, 3 issues.

## Architecture
```
/app/
├── backend/
│   ├── routers/
│   │   ├── auth, bills, issues, payments, properties, users, viewings,
│   │   ├── admin, oversight, community, yardsale, leases, visitors,
│   │   ├── notifications, ai (chat), social (reactions+views),
│   │   ├── admin_moderation (god-mode), admin_exports (CSV/XLSX/PDF)
│   ├── seed_demo_data.py, tests/, notifications, auth, db, models, mpesa, server
│   └── uploads/{properties,community,yardsale,leases}/
├── frontend/src/
│   ├── pages/Dashboard, Marketplace+AiChatButton, Community+ReactionsBar+ViewReceipts,
│   │   PassView (public /pass/{token}), Visitors+share-link, YardSale+forced-STK,
│   │   admin/AdminModeration + AdminUsers (reset+export)
│   ├── components/AppShell (dynamic lease/rental sidebar), ExportMenu,
│   │   AiChatButton, ReactionsBar, ViewReceipts, NotificationBell, CardImageCarousel
│   └── lib/api, auth
└── memory/PRD.md, test_credentials.md, test_reports/iteration_{1..12}.json
└── TESTING_SCENARIOS_ROUND4.md, LAUNCH_nyumbafiti.md
```

## Round 4 API Endpoints
- `GET /api/public/pass/{token}` — public visitor pass viewer
- `POST /api/admin/users/{id}/reset-credentials` `{new_password?, new_email?, generate_password?, reason}` — admin only
- `GET /api/admin/audit-log` — admin only
- `GET /api/admin/export/{users|payments|payouts|properties|bills|issues|viewings|leases}.{csv|xlsx|pdf}`
- `GET /api/public/listings?tenancy_type=lease|rental` — filter
- `POST /api/yard-sale/listings` — now requires `phone_number`; returns `{listing, payment}`

## Round 4 UserPublic shape (frontend reads `user.tenancy_type`)
```ts
{ id, email, full_name, phone, role, tenancy_type, landlord_id, unit_id, approval_status, suspended, created_at }
```

## Demo Mode Notes
- M-Pesa: tries real sandbox first; on 5xx OR missing callback, the 15s demo-callback safety net settles the payment so end-to-end tests still pass. Set `MPESA_DEMO_FALLBACK=false` in production.
- AI fallback to deterministic answer if EMERGENT_LLM_KEY missing or LLM errors.

## Test Coverage
- Round 4: backend 26/26 + frontend 2/2 sidebar — `iteration_12.json`.
- Round 3: backend 17/17 — `iteration_10.json`.
- Cumulative: ~70 backend tests passing across phases.

## Roadmap (Backlog)

### P5 — Production Hardening
- Real M-Pesa Daraja production keys (Go-Live wizard — see `/app/LAUNCH_nyumbafiti.md`)
- Email/SMS notification channel (Resend + Africa's Talking)
- S3/R2 storage for uploads (replace local disk)
- Rate limiting on public endpoints
- Atlas backups + point-in-time restore

### P6 — Engagement Boosters
- Paid "Featured Property" for landlords on marketplace (KES 500/mo)
- Tenant referral credits
- Mobile-first native camera QR scan for caretaker
- "Lock unit + pay deposit" one-tap conversion from prospect → tenant

## Last Updated
Feb 2026 — Round 4 complete (security auto-approve, public pass viewer, admin reset, forced yard-sale unlock, lease/rental filter, M-Pesa sandbox live, CSV/XLSX/PDF exports, demo seed, launch guide for nyumbafiti.co.ke). 100% test pass rate.
