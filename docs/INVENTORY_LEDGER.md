# Transactional Inventory Engine & Stock Ledger Architecture

This document specifies the authoritative double-entry accounting model, concurrency controls, multi-store partitioning, and operational workflows for inventory management in the Bagodi E-Commerce Platform.

---

## 1. Core Architectural Principles

1. **Immutable Append-Only Ledger (`inventory_ledger`):**
   - Direct manual updates to stock columns (e.g. `UPDATE stock_balances SET on_hand_qty = 10`) are **strictly prohibited**.
   - Every physical and logical stock alteration is recorded as an immutable ledger transaction with a source event, movement type, store reference, quantity delta, and audit user.
2. **Materialized Stock Balances (`stock_balances`):**
   - To support high-throughput customer browsing and POS barcode checkout without recalculating millions of ledger rows, an authoritative snapshot table `stock_balances` maintains current balances per `(tenant_id, store_id, variant_id)`.
   - Updates to `stock_balances` are strictly transactional and **must always** be executed synchronously within the same ACID transaction as the corresponding `inventory_ledger` entry.
3. **Strict Concurrency Control & Row Locking:**
   - Any operation altering or reserving inventory must acquire a pessimistic row lock (`SELECT ... FOR UPDATE`) on the target `stock_balances` row.
   - This eliminates race conditions during flash sales or simultaneous in-store POS checkouts.
4. **Three-State Stock Tracking:**
   - **`on_hand_qty`:** Physical inventory physically present in the store or warehouse.
   - **`reserved_qty`:** Stock allocated to pending orders/checkouts awaiting dispatch or payment confirmation.
   - **`available_qty`:** Net sellable stock calculated as `on_hand_qty - reserved_qty`. Available quantity can never drop below zero.

---

## 2. Ledger Movement Types

| Movement Type | `on_hand_delta` | `reserved_delta` | Net Available Impact | Trigger Event |
|---|---|---|---|---|
| `PURCHASE_RECEIPT` | `+N` | `0` | `+N` | Goods inward received against a supplier purchase order or invoice. |
| `SALES_RESERVATION` | `0` | `+N` | `-N` | Order placed at customer checkout or POS held for fulfillment. |
| `SALES_RELEASE` | `0` | `-N` | `+N` | Order cancelled, abandoned, or expired prior to dispatch. |
| `SALES_DISPATCH` | `-N` | `-N` | `0` | Goods picked, packed, and physically dispatched/handed to customer. |
| `CUSTOMER_RETURN` | `+N` | `0` | `+N` | Returned item accepted back into inventory after quality inspection. |
| `ADJUSTMENT_DAMAGE` | `-N` | `0` | `-N` | Item damaged in storage or handling, removed from sellable stock. |
| `ADJUSTMENT_LOSS` | `-N` | `0` | `-N` | Shrinkage, theft, or unaccounted missing units. |
| `RECONCILIATION` | `+/-N` | `0` | `+/-N` | Periodic physical audit cycle count discrepancy correction. |
| `TRANSFER_OUT` | `-N` | `0` | `-N` | Multi-store branch transfer outbound dispatch. |
| `TRANSFER_IN` | `+N` | `0` | `+N` | Multi-store branch transfer inbound arrival and receipt. |

---

## 3. Multi-Store Architecture

- Inventory is partitioned at the triple: `(tenant_id, store_id, variant_id)`.
- **Initial Store Deployment:** Bagodi physical flagship store in Bidar, Karnataka (`stores.code = 'STORE01'`).
- The data model and service interfaces natively support future expansion to multiple physical branches, warehouses, or dark stores per merchant.
- A product variant can have different stock levels across different stores. Online orders are routed to a specific fulfilling store based on proximity and stock availability.

---

## 4. Inward Stock Procurement Workflow

1. **Purchase Order (`purchase_orders`):**
   - Created with `po_number`, `supplier_name`, destination `store_id`, and expected item lines with `variant_id`, `quantity_ordered`, and `unit_cost`.
   - Initial status: `draft` -> `ordered`.
2. **Stock Receipt (`stock_receipts`):**
   - When goods arrive at the store, warehouse/store staff record a stock receipt against the PO.
   - Allows partial or full receipts.
   - Records invoice number, received quantities, and receiving staff.
   - Automatically posts `PURCHASE_RECEIPT` ledger entries and increments store `on_hand_qty` and `available_qty`.
   - Automatically updates PO item `quantity_received` and advances PO status to `partially_received` or `received`.
