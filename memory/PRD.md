# Nyumba OS — Product Requirements Document (PRD)

## Original Problem Statement
Build a comprehensive rental management system for Nairobi serving multiple roles (Landlord, Tenant, Caretaker, Prospect, Security, Super Admin). Core features: property + unit management, M-Pesa STK Push for rent & bills, issue ticketing, public marketplace for vacant units, paid viewings (KES 200), digital leases, visitor QR passes, tenant Community hub, Yard Sale marketplace with monetization, AI Concierge chat, Super Admin god-mode oversight + 3.5% commission tracking + approvals.

## Tech Stack
- Backend: FastAPI + Motor (MongoDB async)
- Frontend: React 19 + React Router 7 + Shadcn UI + Tailwind + Swiper
- Auth: JWT (custom), bcrypt
- Payments: M-Pesa Daraja STK Push (DEMO MODE auto-confirm)
- PDF: reportlab · QR: qrcode · AI: Claude Sonnet 4.5 via emergentintegrations (EMERGENT_LLM_KEY)

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
- Yard Sale KES 35 unlock-contact + KES 50 broadcast.
- Bill notification mix-up fix (rent vs water bills).

### Round 3 Fine-Tuning ✅ (Feb 2026)
- **Social reactions** (like/love/celebrate/support) on announcements, threads, replies — `social_router.py` `/api/social/{target_type}/{target_id}/react`.
- **Announcement read receipts** — author + admin can see who viewed and when via `/api/social/announcement/{id}/views`. Auto-recorded when non-author opens Community page.
- **Multi-turn AI Concierge chat** on Marketplace — `/api/ai/chat` persists per-session conversation, replays history for context, deep-links listing_id references as clickable chips. Falls back gracefully if LLM unavailable.
- **Prospect QR entry pass** — auto-issued on viewing payment success (24h expiry, `is_prospect_pass=true`). Prospect sees prominent QR banner on Dashboard + full list at `/visitors`. Security/caretaker scans on arrival.
- **Admin God-Mode Moderation** — new `/api/admin/moderation/*` router + `/admin/moderation` UI page with tabs for Yard Sale, Announcements, Forum, Viewings, Visitor Passes, Issues, Leases, AI Conversations. Search + delete (with cascade for reactions/views/replies) from one place. Summary grid shows live counts.

## Architecture
```
/app/
├── backend/
│   ├── routers/
│   │   ├── auth_router, bills_router, issues_router, payments_router,
│   │   ├── properties_router, users_router, viewings_router,
│   │   ├── admin_router, oversight_router,
│   │   ├── community_router, yardsale_router,
│   │   ├── leases_router, visitors_router,
│   │   ├── notifications_router, ai_router (chat + recommend),
│   │   ├── social_router (reactions + view receipts), ← Round 3
│   │   └── admin_moderation_router (god-mode) ← Round 3
│   ├── tests/test_phase1, test_phase234, test_round2, test_round3
│   ├── notifications.py, auth, db, models, mpesa, server
│   └── uploads/{properties,community,yardsale,leases}/
├── frontend/src/
│   ├── pages/Dashboard (prospect QR banner ← Round 3), Marketplace + AiChatButton,
│   │   Community (ReactionsBar + ViewReceipts ← Round 3), Visitors, ...
│   │   admin/AdminModeration ← Round 3
│   ├── components/AppShell (Moderation tab), AiChatButton ← Round 3,
│   │   ReactionsBar ← Round 3, ViewReceipts ← Round 3,
│   │   NotificationBell, CardImageCarousel, ErrorBoundary
│   └── lib/api, auth
└── memory/PRD.md, test_credentials.md, test_reports/iteration_{1..10}.json
```

## Key API Endpoints (Round 3 additions)
- `POST /api/social/{target_type}/{target_id}/react?reaction=like|love|celebrate|support` — toggle
- `GET /api/social/{target_type}/{target_id}/reactions`
- `POST /api/social/announcement/{id}/view`
- `GET /api/social/announcement/{id}/views` (author + admin)
- `POST /api/ai/chat` (multi-turn, session_id persistence)
- `GET /api/ai/conversations`, `GET /api/ai/conversations/{sid}`
- `GET /api/admin/ai-conversations` (admin)
- `GET /api/admin/moderation/summary` — live counts
- `GET/DELETE /api/admin/moderation/{yard-sale|announcements|forum/threads|viewings|visitor-passes|issues|leases|ai-conversations}/{id?}`
- `GET /api/visitor-passes` — now returns prospect's own passes with QR data URL

## DB Collections (Round 3 additions)
`reactions`, `announcement_views`, `ai_conversations`.

## Demo Mode Notes
- M-Pesa STK auto-confirms after ~4s
- AI fallback to deterministic answer if EMERGENT_LLM_KEY missing or LLM errors
- Notifications poll every 30s

## Test Coverage
- Backend: test_phase1_properties (19) + test_phase234 (30) + test_round2 + test_round3 (17) — all passing.
- Frontend: smoke screenshots through testing_agent; multi-iteration regression `/app/test_reports/iteration_*.json`.

## Roadmap (Backlog)

### P5 — Production Hardening
- Real M-Pesa Daraja credentials
- Email/SMS notification channel (Resend/Twilio)
- Async file I/O via aiofiles
- Rate limiting on public endpoints
- Cleanup orphaned attachment files on cascade delete
- Move lease PDF template to dedicated module

### P6 — Engagement Boosters (suggestions)
- Paid "Featured Property" for landlords on marketplace
- Tenant referral credits
- Mobile-first native camera QR scan for caretaker

## Last Updated
Feb 2026 — Round 3 complete (social reactions, view receipts, AI chat, prospect QR pass, admin god-mode moderation). Backend tests 17/17 + previous 49/49 still passing.
