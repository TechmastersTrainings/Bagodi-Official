# Reports, Analytics & Merchant Operations Dashboard Engine Specification

**Document Version:** 1.0.0  
**Status:** Approved Architecture  
**Author:** Principal Backend & Application Security Architect  
**Platform Owner:** TechMasters Innovations Private Limited  
**Anchor Merchant:** Bagodi (Bidar, Karnataka)  

---

## 1. Overview & Architectural Principles

The Reporting and Analytics Engine delivers enterprise operational visibility, financial reconciliation, inventory accountability, and executive dashboards across the multi-tenant Bagodi platform.

### Core Principles
1. **Authoritative Transactional Derivation (No Duplication):**
   All metrics, KPIs, and reports are calculated directly from authoritative transaction tables (`orders`, `order_items`, `payment_transactions`, `cod_settlements`, `refunds`, `inventory_ledger`, `stock_balances`, `shipments`, `users`). No separate shadow ledgers, cached summary tables, or unverifiable numbers are introduced.
2. **Zero Dummy Data:**
   Empty states return exact numerical zero (`0.00`, `0`) and empty collection lists. No synthetic numbers or mock charts are ever injected.
3. **Strict Multi-Tenant & Store Isolation:**
   All merchant reporting queries are strictly filtered by the server-resolved `tenant_id`. Store-level filters (`store_id`) validate store ownership against the authenticated tenant. Cross-tenant reads are prevented at the database query level.
4. **Timezone & Temporal Boundary Determinism:**
   - Database storage is strictly in UTC (`timestamp with time zone`).
   - Query filters accept ISO-8601 date strings.
   - Date range queries apply half-open intervals `[start_datetime_utc, end_datetime_utc)` to avoid missing or double-counting edge boundary records.
5. **Audited Exports:**
   Every CSV or structured report generation is logged in `report_export_logs` capturing actor, tenant, IP address, query parameters, format, and row count.

---

## 2. Metric Formulas & Financial Logic

### A. Sales & Revenue

| Metric | Formula | Explanation |
|---|---|---|
| **Gross Sales** | $\sum \text{orders.subtotal}$ | Sum of line-item list prices before discounts for non-cancelled orders |
| **Discounts** | $\sum \text{orders.discount\_amount}$ | Total promotional and coupon discounts granted |
| **Shipping Fees** | $\sum \text{orders.shipping\_fee}$ | Total delivery charges collected |
| **Net Sales (Payable)** | $\sum \text{orders.total\_amount}$ | Subtotal - Discounts + Shipping Fees for non-cancelled orders |
| **Captured Revenue** | $\sum \text{payments.amount}$ | Total payments successfully captured in payment gateway or COD collected |
| **Refunded Amount** | $\sum \text{refunds.amount}$ | Total refunds successfully processed (`status = 'succeeded'`) |
| **Net Realized Revenue** | $\text{Captured Revenue} - \text{Refunded Amount}$ | Actual cash in bank/gateway net of refunds |
| **Average Order Value (AOV)** | $\frac{\text{Net Sales}}{\text{Total Non-Cancelled Orders}}$ | Average basket size per completed order |

### B. Treatment of Order Statuses in Sales Calculations
- **`CONFIRMED`, `PROCESSING`, `DISPATCHED`, `DELIVERED`:** Included in Gross Sales, Discounts, Shipping, and Net Sales.
- **`PENDING_PAYMENT`:** Excluded from sales reports; tracked separately in order funnel conversion reports.
- **`CANCELLED`:** Excluded from sales reports; tracked in cancellation analytics with reason codes.
- **`RETURNED`:** Kept in historical Gross Sales; counted in Return Rate ($\frac{\text{Returned Orders}}{\text{Total Fulfilled Orders}} \times 100$) and customer return valuation.

---

## 3. Inventory Valuation & Stock Movement Formulas

| Metric | Formula | Source Table |
|---|---|---|
| **On-Hand Quantity** | $\sum \text{stock\_balances.on\_hand\_qty}$ | `stock_balances` |
| **Reserved Quantity** | $\sum \text{stock\_balances.reserved\_qty}$ | `stock_balances` |
| **Available Quantity** | $\sum \text{stock\_balances.available\_qty}$ | `stock_balances` |
| **In-Transit Quantity** | $\sum \text{stock\_balances.in\_transit\_qty}$ | `stock_balances` |
| **Stock Valuation (At Retail)** | $\sum (\text{on\_hand\_qty} \times \text{product\_variants.base\_price})$ | `stock_balances` $\bowtie$ `product_variants` |
| **Stock Valuation (At Cost)** | $\sum (\text{on\_hand\_qty} \times \text{latest stock\_receipt\_items.unit\_cost})$ | `stock_balances` $\bowtie$ `stock_receipt_items` |
| **Low-Stock Alert Count** | $\text{Count}(variant) \text{ where } \text{available\_qty} \le \text{reorder\_threshold}$ | `stock_balances` |
| **Out-of-Stock Count** | $\text{Count}(variant) \text{ where } \text{available\_qty} \le 0$ | `stock_balances` |
| **Damaged / Loss Units** | $\sum \text{ledger.quantity} \text{ where movement\_type} \in ('DAMAGE', 'LOSS')$ | `inventory_ledger` |

---

## 4. Fulfillment, Delivery & Rider Performance Metrics

| Metric | Formula | Explanation |
|---|---|---|
| **First-Attempt Delivery Rate** | $\frac{\text{Delivered Shipments with attempt\_count = 1}}{\text{Total Delivered Shipments}} \times 100$ | Deliveries completed without re-attempts |
| **Overall Delivery Success Rate** | $\frac{\text{Total Delivered Shipments}}{\text{Total Processed Shipments}} \times 100$ | Successful vs RTO/failed shipments |
| **RTO Rate** | $\frac{\text{Shipments in RETURNED\_TO\_STORE}}{\text{Total Dispatched Shipments}} \times 100$ | Undelivered packages returned to store |
| **Avg Fulfillment Lead Time** | $\text{Avg}(\text{shipments.dispatched\_at} - \text{orders.created\_at})$ | Warehouse processing & packing duration |
| **Avg Transit Duration** | $\text{Avg}(\text{shipments.delivered\_at} - \text{shipments.dispatched\_at})$ | Courier / rider road transit time |
| **Rider Success Rate** | $\frac{\text{Rider Delivered}}{\text{Rider Assigned}} \times 100$ | Efficiency per delivery personnel |

---

## 5. Customer Analytics & Lifetime Value

| Metric | Formula | Explanation |
|---|---|---|
| **Total Customers** | $\text{Count}(\text{distinct customer\_id})$ | Customers having placed $\ge 1$ order |
| **New Customers** | Customers whose very first order occurred in date range | Cohort acquisition |
| **Repeat Customers** | Customers with $\ge 2$ lifetime orders who placed an order in period | Retention health |
| **Repeat Purchase Rate** | $\frac{\text{Customers with } \ge 2 \text{ orders}}{\text{Total Customers}} \times 100$ | Loyalty metric |
| **Customer Lifetime Value (CLV)** | $\sum \text{orders.total\_amount}$ across all orders for customer | Total value delivered to merchant |

---

## 6. Multi-Store Reporting & Comparison

Merchant accounts manage one or more physical branches (e.g. Bagodi Flagship Store Bidar, future branches).
- The reporting APIs accept an optional `store_id` filter parameter.
- When `store_id` is supplied, the report reflects branch operations.
- When `store_id` is omitted, the report consolidates all branches across the merchant tenant.
- The `/stores` endpoint outputs a side-by-side branch comparison matrix:
  - Branch Code & Name
  - Order Volume
  - Net Sales & Share of Merchant Revenue (%)
  - Stock Units & Valuation
  - Active Shipments

---

## 7. Platform Super Admin Analytics (TechMasters)

Platform super administrators have access to platform-wide macro analytics:
- Total onboarded tenants and active stores.
- Platform Gross Merchandise Value (GMV).
- Tenant performance rankings by GMV, order volume, and active catalog size.
- Cross-merchant delivery and fulfillment velocity.
- Platform notification delivery health and error rates.

---

## 8. Export Standards & Security

1. **RFC 4180 CSV Export:**
   - MIME type: `text/csv; charset=utf-8`
   - Prefixed with UTF-8 Byte Order Mark (`\ufeff`) to ensure seamless automatic encoding detection in Microsoft Excel on Windows and macOS.
   - Filename convention: `bagodi_<report_type>_<start_date>_<end_date>.csv`.
2. **Access Control:**
   - Merchant reports: Requires authenticated JWT with permission `reports.read`.
   - Exports: Requires `reports.export` or `reports.*`.
   - Platform reports: Requires `is_platform_user = true` and `platform.reports:read` or `platform.*`.
3. **Audit Log:**
   Every export writes an immutable record to `report_export_logs` with actor UUID, tenant UUID, report type, format, query filters, row count, and client IP address.

