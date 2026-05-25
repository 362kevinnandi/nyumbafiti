# Nyumba OS — Product Requirements Document (PRD)

## Original Problem Statement
Build a comprehensive rental management system for Nairobi serving multiple roles (Landlord, Tenant, Caretaker, Prospect, Super Admin). Core features: property + unit management, M-Pesa STK Push for rent & bills, issue ticketing, public marketplace for vacant units, paid viewings (KES 200), Super Admin oversight panel with 3.5% commission tracking + approval workflows.

## Tech Stack
- Backend: FastAPI + Motor (MongoDB async)
- Frontend: React 19 + React Router 7 + Shadcn UI + Tailwind + Swiper
- Auth: JWT (custom), bcrypt
- Payments: M-Pesa Daraja STK Push (DEMO MODE auto-confirm)
- PDF: reportlab · QR: qrcode · AI: Claude Sonnet 4.5 via emergentintegrations (EMERGENT_LLM_KEY)

## Roles
- Landlord, Tenant, Caretaker, Prospect, Super Admin

## Implemented Features

### MVP
- JWT Auth, Property/Unit/Tenant CRUD, monthly bill auto-gen, M-Pesa STK Push (demo), Issue ticketing, Public marketplace + paid viewings, Super Admin (3.5% commission, payouts, settings, approvals queue).

### Phase 1 — Property Foundations (Feb 2026) ✅
- Local image uploads (≤5 per property) at `/api/uploads/properties/`
- 7 property categories
- Marketplace Swiper carousel (4×2/slide, autoplay 5s)
- Admin `/admin/properties` (Edit/Delete/Feature with gold badge)
- `mediaUrl()` helper + K8s-routable `/api/uploads` mount

### Phase 2 — Community Hub (Feb 2026) ✅
- **Announcements**: landlord→tenants (own property), admin→global. Pin, attach PDF/images (5MB max), audience notification fan-out.
- **Per-property Forums**: tenants post + reply within own property; landlord/admin can pin/lock/delete; reply notifies thread author.
- **Attachments**: PDF + image only, 5MB max, MIME validated.

### Phase 3 — Yard Sale Marketplace (Feb 2026) ✅
- Free listings (tenant/landlord/caretaker) with up to 5 images, 8 categories.
- Filter chips, featured-first sorting.
- **KES 100 "Feature for 7 days"** via M-Pesa STK Push (purpose `yard_sale_feature`). Auto-expires after 7 days.

### Phase 4 — Smart Features (Feb 2026) ✅
- **Digital Lease**: reportlab PDF generation, tenant e-sign with IP+timestamp, re-renders PDF post-signature.
- **QR Visitor Passes**: tenant creates one-time pass (24h expiry); caretaker scans token to log entry; auto-expire stale; tenant notified on arrival.
- **In-app Notifications**: bell icon (top-right, polls every 30s), unread badge, mark-read on click. Fired on: bill created/auto-gen, payment success, announcement, forum reply, lease pending/signed, visitor arrived, yard sale featured.
- **AI Property Match** on `/marketplace`: Claude Sonnet 4.5 via Emergent LLM key. Falls back to "cheapest 3 matching filters" if LLM unavailable.

## Architecture

```
/app/
├── backend/
│   ├── routers/
│   │   ├── auth_router.py, bills_router.py, issues_router.py, payments_router.py,
│   │   ├── properties_router.py, users_router.py, viewings_router.py,
│   │   ├── admin_router.py, oversight_router.py,
│   │   ├── community_router.py    ← Phase 2
│   │   ├── yardsale_router.py     ← Phase 3
│   │   ├── leases_router.py       ← Phase 4 (PDF lease)
│   │   ├── visitors_router.py     ← Phase 4 (QR)
│   │   ├── notifications_router.py← Phase 4
│   │   └── ai_router.py           ← Phase 4 (Claude Sonnet 4.5)
│   ├── tests/test_phase1_properties.py (19), test_phase234.py (30)
│   ├── notifications.py (helpers)
│   ├── auth.py, db.py, models.py, mpesa.py, server.py
│   └── uploads/{properties,community,yardsale,leases}/
├── frontend/src/
│   ├── pages/
│   │   ├── Marketplace.jsx (Swiper + AI Match button)
│   │   ├── MarketplaceDetail.jsx, Properties.jsx, Tenants.jsx, ...
│   │   ├── Community.jsx       ← P2
│   │   ├── YardSale.jsx        ← P3
│   │   ├── Leases.jsx          ← P4
│   │   ├── Visitors.jsx        ← P4
│   │   └── admin/AdminProperties.jsx, Admin*.jsx
│   ├── components/
│   │   ├── AppShell.jsx (sidebar updated, top-right bell)
│   │   ├── NotificationBell.jsx ← P4
│   │   └── AiRecommendButton.jsx ← P4
│   └── lib/api.js (mediaUrl, formatKES, formatApiError)
├── memory/PRD.md, test_credentials.md
├── test_reports/iteration_1..7.json
└── TESTING_SCENARIOS_PHASE_234.md
```

## Key API Endpoints (Phase 2/3/4)
- Announcements: `POST/GET/DELETE /api/announcements`, `PATCH /api/announcements/{id}/pin`
- Forum: `POST/GET /api/forum/threads`, `GET /api/forum/threads/{id}`, `POST /api/forum/threads/{id}/replies`, `PATCH /api/forum/threads/{id}/moderate`, `DELETE /api/forum/threads/{id}`
- Yard sale: `POST/GET/PATCH/DELETE /api/yard-sale/listings`, `POST /api/yard-sale/listings/{id}/feature`
- Leases: `POST/GET /api/leases`, `GET /api/leases/{id}`, `POST /api/leases/{id}/sign`, `DELETE /api/leases/{id}`
- Visitor passes: `POST/GET /api/visitor-passes`, `POST /api/visitor-passes/scan/{token}`, `DELETE /api/visitor-passes/{id}`
- Notifications: `GET /api/notifications`, `PATCH /api/notifications/{id}/read`, `POST /api/notifications/mark-all-read`
- AI: `POST /api/ai/recommend-properties`

## DB Collections (Phase 2/3/4)
`announcements`, `forum_threads`, `forum_replies`, `yard_sale`, `leases`, `visitor_passes`, `notifications`

## Roadmap (Backlog)

### P5 — Production Hardening
- Real M-Pesa Daraja credentials
- Image size/MIME advanced validation, virus scan
- Async file I/O via aiofiles
- Rate limiting on public endpoints
- DRY shared `uploads.py` for attachment helpers (community + yardsale)
- Move lease PDF template to `backend/pdf/lease_template.py`
- Email/SMS notifications channel (Resend / Twilio) — currently in-app only

### P6 — Engagement Boosters (suggestions)
- Paid "Featured Property" for landlords on marketplace (KES 500/mo) — natural extension of yard sale boost
- Tenant referral credits
- Caretaker mobile-first scan UI with native camera QR decoding

## Demo Mode Notes
- M-Pesa STK auto-confirms after ~4s (no Daraja keys)
- AI fallback to "lowest rent matching" if EMERGENT_LLM_KEY missing or LLM error
- Notifications poll every 30s (no websockets yet)

## Last Updated
Feb 2026 — Phases 1+2+3+4 complete. Backend 49/49 tests pass. Manual test scenarios in `/app/TESTING_SCENARIOS_PHASE_234.md`.
