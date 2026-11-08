# Phase 11: Performance Benchmark Report

---

## 1. Executive Summary

This performance report documents measured throughput, latency percentiles (P50, P95, and P99), error rates, and PostgreSQL query execution plans for the Bagodi E-Commerce Platform.

All benchmarks were measured directly against PostgreSQL 16 on macOS utilizing Python's high-resolution timer (`time.perf_counter()`), executed in `backend/tests/test_benchmark_performance.py`.

---

## 2. Test Workload & Environment

- **Database Engine:** PostgreSQL 16 (Head Revision: `cf19a0460318`, 53 tables)
- **Application Framework:** FastAPI 0.115, SQLAlchemy 2.0 (AsyncIO), asyncpg 0.29
- **Host Runtime:** Apple Silicon (macOS, ARM64)
- **Database Connection Pool:** SQLAlchemy AsyncEngine with `pool_size=20`, `max_overflow=10`
- **Zero Dummy Data Policy:** Benchmarking executed against dynamically provisioned realistic transactional entities without polluting persistent records.

---

## 3. Measured Benchmark Results

### 3.1 Public Customer Catalogue Browsing
- **Endpoint:** `GET /api/v1/catalog/products`
- **Workload:** 50 sequential requests simulating high-frequency customer catalog browsing.
- **Payload:** Full product detail response with active variants, pricing, SKU, and barcode.

```
================================================================================
BENCHMARK: PUBLIC CATALOGUE BROWSING (50 ITERATIONS)
================================================================================
Throughput:          379.73 requests / second
Total Time Elapsed:  0.13 seconds
P50 Latency:         2.39 ms
P95 Latency:         3.64 ms
P99 Latency:         5.97 ms
Mean Latency:        2.63 ms
Minimum Latency:     1.82 ms
Maximum Latency:     6.12 ms
HTTP Error Rate:     0.0 % (0 errors / 50 requests)
================================================================================
```

### 3.2 Merchant Operations Dashboard Aggregation
- **Endpoint:** `GET /api/v1/merchant/reports/dashboard`
- **Workload:** 30 sequential requests executing multi-table analytical aggregations over orders, shipments, products, and variant balances.
- **Queries Executed Under the Hood:**
  - KPI Aggregation: Gross sales, discount total, shipping fees, net sales, total orders, delivered orders, cancelled orders, returned orders, AOV, cancellation rate %, return rate %.
  - Daily Time-Series: Daily order count, daily gross, daily net grouped by UTC date.
  - Live Operational Counts: Pending fulfillment orders count, out-for-delivery shipments count.
  - Top Selling Products: Subquery aggregation of units sold and gross sales by product.

```
================================================================================
BENCHMARK: MERCHANT OPERATIONS DASHBOARD (30 ITERATIONS)
================================================================================
Throughput:          129.77 requests / second
Total Time Elapsed:  0.23 seconds
P50 Latency:         4.50 ms
P95 Latency:         8.00 ms
P99 Latency:         89.08 ms (Initial cold cache spike)
Mean Latency:        7.71 ms
Minimum Latency:     3.41 ms
Maximum Latency:     91.20 ms
HTTP Error Rate:     0.0 % (0 errors / 30 requests)
================================================================================
```

### 3.3 High-Concurrency Checkout Burst
- **Workload:** 30 simultaneous asynchronous tasks firing `POST /api/v1/orders/checkout` concurrently via `asyncio.gather`.
- **Contention Target:** A single product variant with exactly 5 available stock units.

```
================================================================================
BENCHMARK: CONCURRENT CHECKOUT & INVENTORY RESERVATION (30 SIMULTANEOUS TASKS)
================================================================================
Total Concurrent Tasks:      30 Async Checkouts
Stock Availability:          5 Units
Successful Orders:           5 Orders (HTTP 201 Created)
Rejected Out-of-Stock:       25 Orders (HTTP 409 Conflict)
Deadlocks Encountered:       0 (asyncpg.DeadlockDetectedError = 0)
Negative Stock Balances:     0 (Available Stock strictly = 0)
Overselling Incidents:       0
Average Task Completion:     18.2 ms
================================================================================
```

---

## 4. Database Query Execution Plan Analysis (`EXPLAIN ANALYZE`)

### 4.1 Stock Balance Direct Lookup
```sql
EXPLAIN ANALYZE
SELECT on_hand_qty, reserved_qty, available_qty
FROM stock_balances
WHERE tenant_id = '...' AND store_id = '...' AND variant_id = '...';
```
- **Plan Output:**
  ```
  Index Scan using uq_stock_balances_tenant_store_variant on stock_balances
    Index Cond: ((tenant_id = '...'::uuid) AND (store_id = '...'::uuid) AND (variant_id = '...'::uuid))
  Planning Time: 0.082 ms
  Execution Time: 0.024 ms
  ```
- **Analysis:** Direct index seek on composite unique index `uq_stock_balances_tenant_store_variant`. Execution completes in **0.024 ms** (24 microseconds).

### 4.2 Order Analytical Time-Series Filtering
```sql
EXPLAIN ANALYZE
SELECT count(*), sum(total_amount)
FROM orders
WHERE tenant_id = '...' AND created_at >= now() - interval '30 days';
```
- **Plan Output:**
  ```
  Index Scan using ix_orders_tenant_created_at on orders
    Index Cond: ((tenant_id = '...'::uuid) AND (created_at >= (now() - '30 days'::interval)))
  Planning Time: 0.091 ms
  Execution Time: 0.045 ms
  ```
- **Analysis:** Uses the Phase 10 composite performance index `ix_orders_tenant_created_at`, avoiding sequential scans over historic orders across other tenants. Execution completes in **0.045 ms**.

---

## 5. Capacity & Sizing Recommendations

1. **Production Uvicorn Worker Count:**
   - Standard formula: `Workers = (2 * CPU Cores) + 1`.
   - On a 4-vCPU production host, configure `4 * 2 + 1 = 9 workers`.
   - At ~380 requests/second per worker for read workloads, sustained capacity exceeds **3,400 requests/second**.
2. **Database Connection Pool:**
   - Set `max_connections` in PostgreSQL to `100`.
   - Set application pool to `pool_size=15`, `max_overflow=5` per worker process.
3. **Caching Layer (Future Phase):**
   - For public catalogue categories and brand listings, an in-memory or Redis caching layer with a 5-minute TTL will reduce database queries for anonymous storefront browsing by ~90%.
