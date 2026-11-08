# Order Lifecycle & Checkout State Machine

This document specifies the authoritative order states, transition validation rules, inventory integration hooks, and audit requirements for the Bagodi E-Commerce Platform.

---

## 1. Order Status State Machine

```
              [ Customer Checkout ]
                        |
                        v
               +-----------------+
               | PENDING_PAYMENT | <--- (Stock Reserved via SALES_RESERVATION)
               +-----------------+
                 /             \
  [ Payment Confirmed / COD ]    [ Cancelled / Timeout ]
               v                 v
        +-----------+     +-----------+
        | CONFIRMED |     | CANCELLED | <--- (Stock Released via SALES_RELEASE)
        +-----------+     +-----------+
              |                 ^
      [ Pick & Pack ]           |
              v                 |
       +------------+           |
       | PROCESSING | ----------+
       +------------+
              |
      [ Dispatch Outward ]
              v
       +------------+  <--- (Stock Dispatched via SALES_DISPATCH)
       | DISPATCHED |
       +------------+
              |
     [ Courier / Delivery ]
              v
       +-----------+
       | DELIVERED |
       +-----------+
              |
      [ RMA Restock ]
              v
       +-----------+  <--- (Stock Restocked via CUSTOMER_RETURN)
       | RETURNED  |
       +-----------+
```

---

## 2. Permitted State Transitions

| Current Status | Allowed Target Statuses | Inventory Action |
|---|---|---|
| `PENDING_PAYMENT` | `CONFIRMED`, `CANCELLED` | On `CANCELLED`: execute `SALES_RELEASE` to restore available stock. |
| `CONFIRMED` | `PROCESSING`, `CANCELLED` | On `CANCELLED`: execute `SALES_RELEASE` to restore available stock. |
| `PROCESSING` | `DISPATCHED`, `CANCELLED` | On `CANCELLED`: execute `SALES_RELEASE`. On `DISPATCHED`: execute `SALES_DISPATCH`. |
| `DISPATCHED` | `DELIVERED` | Physical goods already left building; cannot be directly cancelled. Must use returns workflow. |
| `DELIVERED` | `RETURNED` | On `RETURNED`: customer return inspected, execute `CUSTOMER_RETURN` into store stock. |
| `CANCELLED` | *None (Terminal)* | Terminal state. No further transitions permitted. |
| `RETURNED` | *None (Terminal)* | Terminal state. |

---

## 3. Inventory Integration Rules

1. **Checkout Stock Reservation:**
   - At checkout creation, each line item acquires a row lock and posts `SALES_RESERVATION` via `InventoryService.reserve_stock`.
   - Reference: `reference_type = 'ORDER_RESERVATION'`, `reference_id = order.order_number`.
   - If any variant has insufficient available stock, checkout transaction rolls back atomically.
2. **Order Dispatch:**
   - When order advances to `DISPATCHED`, the reserved stock is physically written off via `InventoryService.dispatch_stock` (`SALES_DISPATCH`).
   - Decrements `on_hand_qty` and clears `reserved_qty`.
3. **Order Cancellation:**
   - If cancelled while in `PENDING_PAYMENT`, `CONFIRMED`, or `PROCESSING`, the reservation is returned to the available stock pool via `InventoryService.release_reservation` (`SALES_RELEASE`).
   - Restores `available_qty`.
4. **Customer Return:**
   - When returned items are accepted back into sellable inventory, `InventoryService.return_customer_stock` increments `on_hand_qty` and `available_qty`.

---

## 4. Multi-Tenant and Store Fulfillment Model

- Every order is pinned to a specific merchant tenant (`tenant_id`) and fulfilling store (`store_id`).
- For the initial Bagodi deployment, orders are fulfilled by the Bidar physical store (`STORE01`).
- The schema is architected to allow dynamic store fulfillment routing across multiple physical stores or fulfillment centers in future phases.

