# VyapaarSetu — Kirana Store Commerce Platform

A full-stack commerce and inventory platform built for Indian kirana (local grocery)
stores — automated inventory from supplier invoice uploads, real payments, WhatsApp
order notifications, and a customer credit ledger ("Udhaar") modeling how these
stores actually extend trust-based credit to regular customers.

**Live demo:** https://vypaarsetu-1.onrender.com/login.html

## Tech Stack

- **Backend:** FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2
- **Database:** PostgreSQL (Neon), Redis (Upstash) for OTP/session/reset-token storage
- **Auth:** JWT with two identity flows — merchant (password + Google OAuth,
  server-side ID token verification) and customer (email OTP, passwordless)
- **Payments:** Razorpay Checkout.js with server-side signature verification;
  idempotent webhook handling via a Saga pattern (payment → immutable ledger entry →
  inventory decrement → merchant notification)
- **Real-time:** WebSockets for live merchant dashboard order notifications
- **Email:** Resend HTTPS API for OTP and password-reset delivery — chosen over raw
  SMTP because most cloud hosts (including Render) block outbound SMTP ports
  (465/587) to prevent spam abuse; Resend delivers over standard HTTPS (port 443),
  which is never blocked, giving reliable email delivery in production
- **Messaging:** Twilio WhatsApp — outbound order alerts with an inbound reply
  handler (merchant replies "1"/"2" to accept or reject an order directly from WhatsApp)
- **Document processing:** pdfplumber for real invoice text extraction, auto-populating
  inventory from supplier PDF bills
- **Frontend:** Vanilla JS + Tailwind CSS (CDN), no build step
- **Deployment:** Docker, Render (Web Service + Static Site), Neon Postgres, Upstash Redis

## Key Features

- **Automated inventory from invoices** — upload a supplier PDF, the system parses
  line items and adds them to stock automatically
- **Udhaar (credit ledger)** — merchants extend per-customer credit limits; customers
  can pay on credit instead of Razorpay; merchants track and settle outstanding
  balances from a dedicated book view
- **Real-time order notifications** — WebSocket push to the merchant dashboard the
  instant an order is paid, with polling fallback if the socket drops
- **Nearby store discovery** — haversine-distance product search across registered
  stores (self-contained discovery layer)
- **Graceful third-party degradation** — Razorpay, Twilio, and email all fall back to
  safe dev-mode behavior instead of crashing the request if credentials are missing
  or invalid, with clear logging for debugging

## Architecture
