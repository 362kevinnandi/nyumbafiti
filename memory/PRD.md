# Nyumba OS — Product Requirements Document (PRD)

## Original Problem Statement
Build a comprehensive rental management system for Nairobi serving multiple roles (Landlord, Tenant, Caretaker, Prospect, Super Admin). Core features:
- Property + unit management
- M-Pesa STK Push for rent & bills
- Issue ticketing with caretaker assignment
- Public marketplace for vacant units
- Paid viewings (KES 200) via M-Pesa
- Super Admin oversight panel with 3.5% commission tracking + approval workflows

## Tech Stack
- Backend: FastAPI + Motor (MongoDB async)
- Frontend: React 19 + React Router 7 + Shadcn UI + Tailwind + Swiper (carousel)
- Auth: JWT (custom), bcrypt password hashing
- Payments: M-Pesa Daraja STK Push (currently DEMO MODE — auto-resolves after ~4s)

## Roles
- **Landlord**: Manages own properties, units, tenants, caretakers, bills, issues
- **Tenant**: Views own bills, pays via M-Pesa, raises issues
- **Caretaker**: Assigned issues by landlord, resolves tickets
- **Prospect**: Auto-created when booking a viewing; tracks own viewings
- **Admin (Super)**: Pre-seeded from env vars. Platform-wide visibility, approvals, payouts, commission settings, property edit/delete/feature

## Implemented Features (cumulative)

### MVP (prior to this session)
- Auth (register/login) with JWT
- Property + Unit CRUD per landlord
- Tenant assignment to units
- Caretaker creation
- Monthly bill auto-generation
- M-Pesa STK Push (demo mode)
- Issue ticketing with messages
- Public marketplace + paid viewings
- Super Admin dashboard (3.5% commission tracking, payouts, settings, approvals queue)

### Phase 1: Property Foundations — COMPLETED Feb 2026
1. **Local image uploads** — up to 5 images per property, stored under `backend/uploads/properties/`, served via `/api/uploads/...` (K8s ingress-compatible)
2. **7 fixed property categories** — `apartment`, `bedsitter`, `single_room`, `self_contained`, `standalone`, `compound`, `airbnb`
3. **Marketplace carousel** — Swiper-based, 4 cards/row × 2 rows = 8 per slide, autoplay 5s, navigation arrows + clickable pagination dots, category filter chips, search + max-rent
4. **Admin Property Management** — `/admin/properties` page: list all, search, Edit (name/address/description/category), Delete (cascades units), Feature/Unfeature (gold badge, sorts first on marketplace)
5. **`mediaUrl()` helper** in `frontend/src/lib/api.js` — builds correct absolute URLs that work both locally and through K8s preview/production

## Architecture

```
/app/
├── backend/
│   ├── routers/ (auth_router, properties_router, users_router, bills_router,
│   │             payments_router, issues_router, viewings_router,
│   │             admin_router, oversight_router)
│   ├── tests/   (test_phase1_properties.py — 19 tests, 100% pass)
│   ├── uploads/properties/  (local image storage)
│   ├── auth.py, db.py, models.py, mpesa.py, server.py
│   └── .env
├── frontend/
│   ├── src/
│   │   ├── components/ (AppShell.jsx, ErrorBoundary.jsx, ui/*)
│   │   ├── lib/ (api.js — exports mediaUrl helper, auth.jsx)
│   │   ├── pages/ (Marketplace, MarketplaceDetail with Swiper, Properties,
│   │   │            Tenants, Caretakers, Bills, Payments, Issues, Viewings,
│   │   │            admin/AdminProperties, admin/Admin*)
│   │   └── App.js, index.js
│   └── .env
├── memory/
│   ├── PRD.md
│   └── test_credentials.md
└── test_reports/  (iteration_1..6.json)
```

## Key API Endpoints (new in Phase 1)
- `POST /api/properties` (multipart): name, address, description, category, images[]
- `PATCH /api/properties/{id}`: landlord can edit own (name/address/description/category); admin can edit any + toggle `featured`
- `DELETE /api/properties/{id}`: landlord deletes own; admin deletes any (cascades units)
- `GET /api/public/listings?category=X`: returns vacant listings, featured-first, with `category` & `featured` fields on property
- `GET /api/admin/properties`: admin view of all properties + landlord names
- `GET /api/uploads/properties/{file}`: serves uploaded images (K8s-routable)

## Key DB Schema additions
- `properties.category`: PropertyCategory enum, default `"apartment"`
- `properties.featured`: bool, default `false`

## Backlog / Roadmap

### P2 — Phase 2: Tenant Community Hub
- Landlord/admin announcements broadcast to tenants per property
- Per-property forum threads (tenant-only)
- File sharing in threads (rules, notices, PDFs)
- Admin moderation dashboard

### P3 — Phase 3: Tenant Marketplace / Yard Sale
- Tenants list items for sale within their property/landlord network
- Optional KES listing fee via M-Pesa
- Featured listings (paid boost)

### P4 — Phase 4: Smart Features
- AI property recommendations (Emergent LLM key, Claude Sonnet 4.5)
- Digital lease agreements with e-signature
- QR-code visitor management at the gate (caretaker scans on entry)
- Auto reminders (SMS/WhatsApp) for due bills

### P5 — Production Hardening
- Real M-Pesa Daraja credentials (replace demo mode)
- Image size/MIME validation, virus scan
- Async file I/O (aiofiles)
- Rate limiting on public endpoints

## Known Issues / Mocks
- M-Pesa runs in DEMO MODE — auto-confirms after ~4 seconds (no Daraja keys set)
- No size limit / MIME validation on uploaded property images (advisory)

## Last Updated
Feb 2026 — Phase 1 complete (image uploads, categories, marketplace carousel, admin property management). Backend 19/19 tests pass. Frontend smoke-tested.
