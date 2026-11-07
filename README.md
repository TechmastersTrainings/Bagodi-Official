# Bagodi Platform

A multi-tenant-capable retail e-commerce platform for Bagodi, Bidar, owned and operated as a technology platform by TechMasters Innovations Private Limited.

## Repository layout

- `frontend/`: customer website, merchant admin, platform super admin.
- `backend/`: FastAPI modular-monolith foundation.
- `docs/`: shared architecture and API contracts.
- `infrastructure/`: local development services.

## Locked decisions

- One physical Bagodi store in Bidar initially; schema supports additional stores.
- Manual and barcode-based inventory.
- Bagodi delivery staff and third-party courier delivery.
- Payment provider is undecided; payment integration must remain provider-independent.
- Customer website and Android application.
- Bagodi Admin and TechMasters Super Admin.
- PostgreSQL, FastAPI, SQLAlchemy 2.x, Alembic.
- React, Vite, TypeScript, plain CSS; Capacitor Android packaging is planned.

## No-demo-data policy

This repository intentionally contains no sample products, customers, orders, inventory balances, payment transactions, or fabricated dashboard metrics. Local development starts with an empty database and explicit health/configuration checks.

## Start backend

1. Copy root `.env.example` to root `.env` and set a local PostgreSQL password.
2. Copy `backend/.env.example` to `backend/.env` and set the matching PostgreSQL connection string.
3. Start PostgreSQL using `docker compose -f infrastructure/docker-compose.yml up -d`.
4. From `backend/`, create a virtual environment and install requirements.
5. Run `alembic upgrade head` after the initial migration is generated and reviewed.
6. Run `uvicorn app.main:app --reload`.

See `docs/PHASE_0_FOUNDATION.md` before adding business modules.

## Frontend

The frontend workspace is scaffolded under `frontend/`. Run `pnpm install` and `pnpm dev:customer`, `pnpm dev:merchant`, or `pnpm dev:super-admin`.

The frontend does not contain fake API data. Until an API is implemented, screens must show explicit loading, empty, unavailable, or error states.

## Collaboration

Both developers work in this repository. Backend owns OpenAPI contracts and database migrations. Frontend consumes the published API contract and must not invent endpoint or response shapes. Coordinate changes to `docs/` and shared package configuration before merging.
