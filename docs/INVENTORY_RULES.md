# Inventory Design Rules

Inventory is tracked per sellable product variant and store.

## Core quantities

- On hand: physically recorded stock.
- Reserved: quantity committed to active reservations.
- Available: on hand minus reserved, subject to the approved stock policy.
- Damaged/quarantined: tracked separately and not sellable.

`available = on_hand - reserved`

## Mandatory controls

1. Every variant has a merchant-scoped SKU.
2. Barcode values map to a specific sellable variant.
3. Every stock change creates an immutable movement record.
4. Do not directly overwrite stock without an adjustment movement.
5. Reservation and stock balance changes must be transactional.
6. Concurrent checkout must not oversell.
7. Cancellation releases eligible reservations.
8. Return receipt does not automatically make stock saleable.
9. Inspection determines restock, quarantine, or disposal.
10. Physical reconciliation records counted quantity, variance, reason, actor and timestamp.

No stock balances or movements are seeded in this repository.
