# Nyumba OS — Nairobi Rental Management System

## Original Problem Statement
Build a rental management system for tenants in Nairobi where landlords are able to log in and manage apartment houses, posting bills, communication, etc., at the same time, tenants can log in and see rental arrears, post apartment issues to the landlord. And the landlord can be assisted by a caretaker who helps solve tenants' issues. Tenants' payments need to be made via M-Pesa, bills, and rent that is every month.

## User Choices (confirmed)
- M-Pesa: **Full STK Push** integration (running in demo mode until Daraja keys are added)
- Bills: **Auto-generated monthly rent** + manual posting
- Roles: Landlords **self-register**; tenants & caretakers are created by landlord
- Communication: **Simple ticketing system** with threaded messages
- Design: **Modern dashboard with property cards** (Swiss / High-contrast theme)

## Architecture
- **Backend**: FastAPI + Motor (MongoDB async)
  - Routers split per resource: auth, properties, users (tenants+caretakers), bills, payments, issues
  - JWT auth (bcrypt) with role guards (`landlord`, `tenant`, `caretaker`)
  - M-Pesa Daraja STK Push client with demo-mode auto-callback (`mpesa.py`)
- **Frontend**: React 19 + react-router-dom 7 + shadcn/ui + Tailwind
  - AuthContext + axios interceptor
  - Role-aware AppShell sidebar
  - PayDialog polls payment status post STK push
- **Database**: MongoDB collections — users, properties, units, bills, payments, issues, issue_messages

## User Personas
1. **Landlord** — owns properties, manages units/tenants/caretakers, posts bills, sees arrears and payments
2. **Tenant** — sees own bills, pays via M-Pesa STK, reports issues, chats with landlord/caretaker
3. **Caretaker** — claims & resolves tickets in their landlord's network

## Core Requirements (static)
- Multi-role auth (JWT)
- Property → Units → Tenant assignment
- Monthly rent auto-generation
- M-Pesa STK Push + callback handling
- Issue ticketing + threaded conversation
- Role-scoped data access

## Implemented (2026-02 / 2026-05)
- [x] JWT auth, register (landlord), login, /me, suspended-account lockout
- [x] Property + Unit CRUD with image, address
- [x] Tenant onboarding + automatic unit occupancy
- [x] Caretaker creation
- [x] Manual bill creation (rent, water, electricity, service, other)
- [x] One-click monthly rent generation
- [x] M-Pesa STK Push initiation (demo-mode fallback)
- [x] M-Pesa callback handler with secret-path security
- [x] Payment status polling
- [x] Auto-update bill status: pending/partial/paid/overdue
- [x] Issue create/assign/status update
- [x] Issue threaded messages
- [x] Dashboard stats per role
- [x] Login/register hero pages
- [x] Sidebar layout with role-aware nav
- [x] Public marketplace at `/marketplace`
- [x] Paid viewing booking (KES 200 M-Pesa STK Push)
- [x] Auto-prospect account creation with one-time password
- [x] Landlord viewings page + prospect /viewings tracker
- [x] Global ErrorBoundary + formatApiError helper
- [x] **Super-admin role** pre-seeded from `ADMIN_EMAIL` / `ADMIN_PASSWORD` env vars
- [x] **3.5% platform commission** computed on every successful M-Pesa transaction, stored as `commission_amount` + `net_to_landlord` on the Payment record
- [x] **Admin Platform Overview** showing total commission, gross volume, owed-to-landlords, users, properties, by-source revenue breakdown
- [x] **Admin User management** with suspend/reactivate (blocks login + invalidates active sessions)
- [x] **Admin All Payments** with refund flow (rolls back linked bill / cancels linked viewing)
- [x] **Admin Payouts** per-landlord balance owed + mark-as-paid history
- [x] **Admin Settings** to change commission rate (stored in `platform_settings` DB collection)
- [x] **Landlord Payments page** now shows Gross / Fee / Net columns so each landlord sees what they actually receive

## Prioritized Backlog
### P0 / Now
- Provide real Daraja sandbox credentials to switch out of demo mode
- Configure `MPESA_CALLBACK_BASE_URL` for production deployment

### P1 / Next
- Email/SMS notifications when bills are issued or payments succeed
- Rent receipt PDF generation/download
- Tenant statements (period view)
- Image upload (S3) for property photos & issue attachments
- Lease document storage per tenant
- Scheduled job (APScheduler) to auto-generate bills on the 1st of every month
- Email password reset flow

### P2 / Later
- Multi-property analytics (occupancy trends, revenue charts)
- Tenant move-in/move-out workflow
- Maintenance vendor marketplace
- SMS reminders for overdue bills
- Bulk import of tenants via CSV
- Public landing page + marketing site

## Test Coverage
- Backend: 34/34 pytest cases at `/app/backend/tests/test_rental_management.py`
- Frontend: End-to-end Playwright verified by testing subagent (register → property → unit → tenant → monthly rent → tenant login → M-Pesa STK → payment succeeded)

## Demo Credentials
See `/app/memory/test_credentials.md`
