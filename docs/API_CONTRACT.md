# API Contract

Backend OpenAPI (`/openapi.json`) is authoritative. This document records conventions, not invented endpoints.

## Base path

`/api/v1`

## Rules

- Backend developer defines request and response schemas.
- Frontend developer consumes published OpenAPI and generated/shared TypeScript types.
- Breaking changes require coordination and documentation.
- Every merchant-owned endpoint must enforce server-derived tenant scope.
- Frontend route guards are UX controls, not security boundaries.
- Never return fabricated records to make a screen appear populated.

## Planned domains

| Domain | Planned prefix |
|---|---|
| Authentication | `/auth` |
| Users and customers | `/users`, `/customers` |
| Merchants and stores | `/merchants`, `/stores` |
| Catalogue | `/products`, `/categories` |
| Inventory | `/inventory`, `/barcodes`, `/stock-receipts` |
| Cart and checkout | `/cart`, `/checkout` |
| Orders | `/orders` |
| Payments and refunds | `/payments`, `/refunds` |
| Returns and exchanges | `/returns`, `/exchanges` |
| Delivery | `/delivery` |
| Promotions | `/promotions` |
| Notifications | `/notifications` |
| Reports | `/reports` |
| Platform administration | `/platform/admin` |
| Audit | `/audit-logs` |

These are planned domains only. Do not call them until implemented and published in OpenAPI.
