# Phase 0 — Foundation

## Scope

Phase 0 establishes repository conventions, runtime configuration, database connectivity, initial platform entities, and the API health endpoint. It does not implement customer authentication, OTP delivery, payments, inventory transactions, orders, or courier integrations.

## Architecture

Use a modular monolith. Each business domain will live in `backend/app/modules/<domain>/` and own its models, schemas, service layer, routes, and tests. Cross-domain business logic belongs in services, not route handlers.

## Tenant model

- `tenants` represent merchant organizations.
- `stores` represent physical operating locations belonging to a tenant.
- Tenant-owned records must be scoped using the authenticated tenant context.
- Platform-level identities may have no tenant membership; this must never grant implicit access to merchant data.
- Never accept a client-supplied `tenant_id` as proof of authorization.
- Every tenant-scoped query and mutation must derive tenant scope from validated server-side identity and permissions.
- Database constraints should include tenant identifiers where uniqueness is merchant-specific.

The first merchant and first store are created through a controlled provisioning operation after the relevant business details are confirmed. No fabricated merchant or store records are seeded.

## Identity and RBAC foundation

The initial schema defines users, roles, permissions, user-role assignments, and role-permission assignments. It does not yet define an OTP provider or issue tokens. Authentication provider selection and operational security policy must be agreed before implementation.

## Initial database entities

- `tenants`
- `stores`
- `users`
- `roles`
- `permissions`
- `user_roles`
- `role_permissions`

UUID primary keys are used. Timestamps are UTC-aware. Tenant and store records are not seeded.

## API conventions

- Prefix: `/api/v1`
- JSON request and response bodies.
- OpenAPI is the authoritative API contract.
- Standard HTTP status codes.
- No endpoint may expose cross-tenant records.
- Error response conventions will be finalized before the first business module.

## Development environments

- Use environment variables for secrets and connection strings.
- `.env.example` documents required configuration without containing credentials.
- PostgreSQL is the source of truth.
- Do not silently fall back to SQLite or in-memory storage.
- Database migrations are mandatory for schema changes.

## Acceptance criteria

1. Backend starts with valid environment configuration.
2. `/api/v1/health` reports application health without exposing secrets.
3. PostgreSQL connectivity can be checked separately from process health.
4. Alembic can apply the initial schema.
5. Empty database contains no fabricated commercial records.
6. Frontend applications start independently.
7. Frontend API base URLs are environment-configurable.
8. API contract ownership and integration workflow are documented.
