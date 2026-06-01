# NYUMBA FITI — User Guides

Welcome to **NYUMBA FITI**, your Nairobi rental management platform. This document is a complete step-by-step guide for every type of user.

---

## Table of Contents
1. [Quick Tour — What Each Role Can Do](#quick-tour)
2. [Landlord Guide](#landlord-guide)
3. [Tenant Guide](#tenant-guide)
4. [Caretaker Guide](#caretaker-guide)
5. [Prospect (Home Seeker) Guide](#prospect-guide)
6. [M-Pesa Payment Walkthrough](#m-pesa-payments)
7. [FAQs](#faqs)

---

## Quick Tour
| Role | How they get in | What they can do |
|---|---|---|
| **Super Admin** | Pre-seeded on backend startup from env vars | Full platform visibility, suspend users, set commission rate, manage payouts, refund payments |
| **Landlord** | Self-register at `/register` | Manage properties, units, tenants, caretakers, bills, payments, viewings |
| **Tenant** | Login created by their landlord | See rent arrears, pay via M-Pesa, report issues |
| **Caretaker** | Login created by their landlord | Pick up tenant issue tickets, mark resolved |
| **Prospect** | Auto-created when booking a viewing on the public marketplace | Track viewing appointments |

> **Platform commission**: 3.5% (adjustable from Admin → Settings) is automatically deducted from every successful M-Pesa transaction. The landlord receives the net amount, the platform keeps the fee.

---

## Landlord Guide

### 1. Create your account
1. Open the home page → click **List property** (top-right) or visit `/register`.
2. Fill in: full name, email, Kenyan phone (e.g. `0712345678`), password (min 6 chars).
3. Click **Create landlord account**. You're taken straight to your dashboard.

### 2. Add your first property
1. Sidebar → **Properties** → click **Add Property**.
2. Enter:
   - **Name** (e.g. "Riverside Apartments")
   - **Address** (e.g. "Riverside Drive, Westlands, Nairobi")
   - **Description** (optional — appears on the public listing)
   - **Image URL** (optional — paste a URL from Unsplash, your phone's cloud, etc.)
3. Click **Create**. The property appears as a card on the page.

### 3. Add units to that property
1. Still on **Properties** → click **Add Unit**.
2. Pick the property → enter unit number (e.g. "A-101"), monthly rent (e.g. `45000`), bedrooms.
3. Save. The unit is now **vacant** and visible on the public marketplace at `/marketplace`.

### 4. Onboard a tenant
1. Sidebar → **Tenants** → click **Add Tenant**.
2. Enter the tenant's full name, email, phone, initial password (you share this with them via WhatsApp/SMS), and select a **vacant unit** to assign them to.
3. Save. The unit is now occupied — it **automatically disappears from the public marketplace**.
4. Send the tenant their email + password — they log in at `/login`.

### 5. Add a caretaker
1. Sidebar → **Caretakers** → **Add Caretaker** → fill name/email/phone/password → save.
2. They can now log in and pick up tenant issue tickets.

### 6. Generate monthly rent bills
1. Sidebar → **Bills** → click **Generate Monthly Rent** (top-right).
2. Confirm. The system creates a rent invoice for every occupied unit for the current month, with a due date of the 5th of next month.
3. Tenants now see these bills in their portal.

### 7. Create one-off bills (water, electricity, service)
1. Sidebar → **Bills** → **New Bill**.
2. Pick a tenant → choose bill type → enter amount, period (YYYY-MM), due date → save.

### 8. View incoming viewing requests
1. Sidebar → **Viewings**. You see every prospect who paid KES 200 to view your units.
2. Each card shows: name, phone, email, scheduled date/time, and any notes.
3. Call/email the prospect to confirm — or hand-off to your caretaker.

### 9. Handle tenant issues
1. Sidebar → **Issues**. You see every ticket your tenants opened.
2. For each ticket: assign a **caretaker** from the dropdown and set its **status**.
3. Click **Discussion** to chat with the tenant + caretaker in a shared thread.

### 10. Track payments
1. Sidebar → **Payments**. Every successful M-Pesa receipt is logged here with phone, amount, receipt code, and timestamp.
2. The **Dashboard Overview** shows arrears, total collected, occupancy, and open issues at a glance.

---

## Tenant Guide

### 1. Get your login
Your landlord creates your account and shares the email + password.
- Open `/login` → enter credentials → land on your **Overview** showing:
  - Outstanding arrears
  - Pending / paid bills
  - Open issues

### 2. View your bills
1. Sidebar → **My Bills**. You see every bill issued to you (rent + utilities).
2. Each row shows amount, paid so far, balance, due date, and status.

### 3. Pay a bill via M-Pesa
1. On a pending bill, click the green **Pay** button.
2. Confirm your M-Pesa phone number (defaults to the one your landlord registered).
3. Optionally adjust the amount (for partial payments).
4. Click **Pay KES X**. A prompt is sent to your phone — enter your M-Pesa PIN.
5. The dialog shows real-time status; within seconds you'll see "Payment received! Receipt: NXXXXXXX".
6. The bill status flips to **paid** (or **partial** if you paid less than the full amount).

### 4. Report an issue
1. Sidebar → **Report Issues** → click **Report Issue**.
2. Enter title (e.g. "Kitchen tap dripping"), full description, priority (low / medium / high / urgent).
3. Submit. The landlord + any caretaker can see it immediately.

### 5. Chat with your landlord / caretaker
1. On any issue card, click **Discussion**.
2. Type messages and hit send. Replies appear in the same thread.

### 6. Payment history
1. Sidebar → **Payment History**. Every M-Pesa receipt for every payment you ever made.

---

## Caretaker Guide

### 1. Login
Your landlord creates your account. Sign in at `/login`.

### 2. Pick up open tickets
1. Sidebar → **Tickets**. You'll see:
   - **Unassigned tickets** waiting for someone to take ownership
   - **Your tickets** that the landlord assigned to you
3. On any unassigned ticket click **Pick up** — it auto-assigns to you and moves to **in progress**.

### 3. Resolve a ticket
1. Click **Mark resolved** when you're done.
2. Use **Discussion** to coordinate with the tenant (e.g. "I'll come by tomorrow at 10am").

### 4. Your stats
The Overview dashboard shows your open tickets, unassigned tickets available to claim, and how many you've resolved.

---

## Prospect (Home Seeker) Guide

### 1. Browse listings
1. Open the marketplace: `/marketplace` (no login required).
2. Use the **search bar** (area, building, unit number) and the **Max rent KES** filter to narrow down.

### 2. View a listing
Click any card. You see:
- Property name, address, rent/month, bedrooms, unit number
- A description
- The KES 200 viewing fee panel

### 3. Book a viewing
1. Click **Book Viewing**.
2. Fill in: your name, email, M-Pesa phone, preferred date + time, and any notes (e.g. "I prefer evenings").
3. Click **Pay KES 200**. An M-Pesa STK Push is sent to your phone.
4. Enter your M-Pesa PIN on your phone to confirm.
5. Within seconds the dialog shows:
   - ✅ **Confirmed!** with the M-Pesa receipt
   - The full property address
   - The caretaker's name + phone (call them to coordinate the actual visit)
   - The landlord's name + phone (backup contact)
   - **Your auto-created login** (email + one-time password) — **save these**

### 4. Track your viewings (optional)
1. Open `/login` → sign in with the email + password the confirmation panel showed you.
2. Sidebar → **My Viewings**. You see every appointment you've booked, with addresses and status.
3. You can book more viewings on different listings using the same account.

---

## M-Pesa Payments

All payments on NYUMBA FITI use **Safaricom's M-Pesa STK Push**. Here's what happens behind the scenes:

1. You click a Pay button.
2. NYUMBA FITI asks Safaricom to "push" a payment prompt to your registered phone.
3. Your phone vibrates with a popup asking for your M-Pesa PIN.
4. You enter the PIN. Safaricom processes the transaction in seconds.
5. Safaricom sends a **confirmation receipt** back to NYUMBA FITI.
6. The bill (or viewing) is automatically marked **paid** and you see the M-Pesa receipt code on screen.

### Phone number formats accepted
- `0712345678` (Kenyan local)
- `254712345678` (international)
- `+254712345678` (with plus)

All three are normalized to `254712345678` automatically.

### When it doesn't work
- **No prompt on phone?** Check the M-Pesa app's *Notifications* tab — sometimes the push gets buried. Wait 60s, then retry.
- **"Insufficient funds"** — top up M-Pesa and retry.
- **Failed transactions** are logged in your Payment History with the failure reason.

---

## FAQs

**Q: Can a tenant register themselves?**
No — only landlords self-register. Tenants and caretakers are created by their landlord (this prevents impersonation). Prospects are auto-created when booking a viewing.

**Q: What happens to a listing once I rent out the unit?**
The moment you assign a tenant to a unit, the unit's `occupied` flag flips and it disappears from `/marketplace` automatically. No manual delisting needed.

**Q: Can a prospect become a tenant?**
Yes. When the landlord onboards them, they need to use a **different email** than the prospect account (currently the system keeps prospect and tenant emails separate). We can change this in a future update.

**Q: Is the KES 200 viewing fee refundable?**
The platform marks it as "Refundable if landlord no-shows" but actual refunds are handled manually by the landlord (e.g. they M-Pesa it back). A built-in dispute / refund flow is on the roadmap.

**Q: Can I generate rent bills automatically every month?**
Right now it's a one-click button on the Bills page. A scheduled job that runs on the 1st of each month is on the roadmap (P1).

**Q: Where do I see all the M-Pesa receipts from my tenants?**
Sidebar → **Payments** as a landlord. Each row shows the phone, amount, M-Pesa receipt code, and status.

---

*Last updated: Feb 2026 · NYUMBA FITI v1.0*
