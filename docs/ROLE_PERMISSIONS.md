# Role and Permission Design

## Principal categories

- Customer: personal shopping and own account resources.
- Merchant staff: access limited to a tenant and assigned permissions.
- Merchant administrator: merchant-level configuration and staff governance.
- Platform administrator: platform governance; no implicit unrestricted access to merchant business records.

## Initial permission domains

- `users.*`
- `staff.*`
- `roles.*`
- `stores.*`
- `catalog.*`
- `inventory.*`
- `orders.*`
- `payments.*`
- `refunds.*`
- `returns.*`
- `exchanges.*`
- `delivery.*`
- `promotions.*`
- `reports.*`
- `merchant.settings.*`
- `platform.merchants.*`
- `platform.configuration.*`
- `platform.audit.*`

Permission assignment and enforcement must be implemented by the backend. Frontend navigation may hide inaccessible actions but cannot replace backend authorization.

Detailed role-to-permission assignments require Bagodi approval and must not be guessed.
