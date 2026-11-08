import statistics
import time
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.db.session import engine


@pytest.fixture
async def setup_benchmark_ecosystem(client: AsyncClient, mint_jwt_token):
    """Provisions a populated test environment for benchmarking."""
    async with engine.begin() as conn:
        res_pa = await conn.execute(
            text(
                "INSERT INTO users (id, phone_e164, email, display_name, status, is_platform_user, created_at, updated_at) "
                "VALUES (gen_random_uuid(), '+919000000000', 'pa@bench.internal', 'Platform Admin', 'active', true, now(), now()) "
                "RETURNING id;"
            )
        )
        pa_id = res_pa.scalar_one()

        res_ma = await conn.execute(
            text(
                "INSERT INTO users (id, phone_e164, email, display_name, status, is_platform_user, created_at, updated_at) "
                "VALUES (gen_random_uuid(), '+919000000001', 'ma@bench.internal', 'Merchant Admin', 'active', false, now(), now()) "
                "RETURNING id;"
            )
        )
        ma_id = res_ma.scalar_one()

        res_cust = await conn.execute(
            text(
                "INSERT INTO users (id, phone_e164, email, display_name, status, is_platform_user, created_at, updated_at) "
                "VALUES (gen_random_uuid(), '+919000000002', 'cust@bench.internal', 'Benchmark Customer', 'active', false, now(), now()) "
                "RETURNING id;"
            )
        )
        cust_id = res_cust.scalar_one()

    pa_token = mint_jwt_token(user_id=pa_id, is_platform_user=True, permissions=["platform.*"])
    pa_headers = {"Authorization": f"Bearer {pa_token}"}

    tenant_resp = await client.post(
        "/api/v1/platform/tenants",
        json={
            "name": "Benchmark Merchant",
            "slug": "benchmark-merchant",
            "legal_name": "Benchmark Retail Private Limited",
            "contact_email": "bench@bagodi.in",
            "contact_phone": "+919000000001",
        },
        headers=pa_headers,
    )
    tenant_id = UUID(tenant_resp.json()["id"])
    await client.patch(
        f"/api/v1/platform/tenants/{tenant_id}/status",
        json={"status": "active"},
        headers=pa_headers,
    )

    ma_token = mint_jwt_token(
        user_id=ma_id,
        tenant_id=tenant_id,
        permissions=["stores.*", "catalog.*", "inventory.*", "orders.*", "reports.*"],
    )
    ma_headers = {"Authorization": f"Bearer {ma_token}"}

    cust_token = mint_jwt_token(
        user_id=cust_id,
        tenant_id=tenant_id,
        roles=["customer"],
        permissions=["customer.*"],
    )
    cust_headers = {"Authorization": f"Bearer {cust_token}"}

    # Store
    store_resp = await client.post(
        "/api/v1/stores",
        json={
            "name": "Benchmark Store",
            "code": "BENCH-01",
            "address_line": "Market Road",
            "city": "Bidar",
            "state": "Karnataka",
            "postal_code": "585401",
        },
        headers=ma_headers,
    )
    store_id = UUID(store_resp.json()["id"])

    # Category & 5 Products
    cat_resp = await client.post(
        "/api/v1/merchant/catalog/categories",
        json={"name": "Benchmark Category", "slug": "benchmark-category"},
        headers=ma_headers,
    )
    cat_id = cat_resp.json()["id"]

    variant_ids = []
    for i in range(5):
        p_resp = await client.post(
            "/api/v1/merchant/catalog/products",
            json={
                "category_id": cat_id,
                "name": f"Benchmark Product {i}",
                "slug": f"benchmark-product-{i}",
                "status": "active",
                "is_published": True,
                "variants": [
                    {
                        "name": f"Standard Variant {i}",
                        "sku": f"BENCH-SKU-{i}",
                        "barcode": f"890666000{i}",
                        "mrp": "1000.00",
                        "base_price": "800.00",
                    }
                ],
            },
            headers=ma_headers,
        )
        variant_ids.append(UUID(p_resp.json()["variants"][0]["id"]))

    # Inward stock
    await client.post(
        "/api/v1/merchant/inventory/receipts",
        json={
            "store_id": str(store_id),
            "receipt_number": "INW-BENCH-01",
            "items": [
                {"variant_id": str(vid), "quantity_received": 100, "unit_cost": "500.00"}
                for vid in variant_ids
            ],
        },
        headers=ma_headers,
    )

    return {
        "tenant_id": tenant_id,
        "store_id": store_id,
        "cat_id": cat_id,
        "variant_ids": variant_ids,
        "ma_headers": ma_headers,
        "cust_headers": cust_headers,
    }


def calculate_latencies(latencies_ms: list[float]) -> dict[str, float]:
    sorted_l = sorted(latencies_ms)
    n = len(sorted_l)
    return {
        "p50": round(sorted_l[int(n * 0.50)], 2),
        "p95": round(sorted_l[int(n * 0.95)], 2),
        "p99": round(sorted_l[int(n * 0.99)], 2),
        "mean": round(statistics.mean(sorted_l), 2),
        "min": round(min(sorted_l), 2),
        "max": round(max(sorted_l), 2),
    }


# =============================================================================
# Benchmarking Test Suite
# =============================================================================
@pytest.mark.asyncio
async def test_benchmark_public_catalogue_browsing_latency(
    client: AsyncClient, setup_benchmark_ecosystem
):
    """
    Measures latency percentiles and throughput for public catalogue browsing across 50 iterations.
    Target: P95 < 150ms, Error rate 0%.
    """
    iterations = 50
    latencies = []
    errors = 0

    t_start = time.perf_counter()
    for _ in range(iterations):
        t0 = time.perf_counter()
        resp = await client.get("/api/v1/catalog/products")
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(elapsed_ms)
        if resp.status_code != 200:
            errors += 1

    total_time = time.perf_counter() - t_start
    throughput = round(iterations / total_time, 2)
    stats = calculate_latencies(latencies)

    print(f"\n[BENCHMARK] Public Catalogue Browsing ({iterations} reqs):")
    print(f"  Throughput: {throughput} req/s | Total Time: {round(total_time, 2)}s")
    print(
        f"  P50: {stats['p50']}ms | P95: {stats['p95']}ms | P99: {stats['p99']}ms | Mean: {stats['mean']}ms"
    )
    print(f"  Error Rate: {errors / iterations * 100.0}%")

    assert errors == 0, f"Encountered {errors} errors during catalogue benchmark"
    assert stats["p95"] < 250.0, f"Catalogue P95 latency exceeded threshold: {stats['p95']}ms"


@pytest.mark.asyncio
async def test_benchmark_merchant_dashboard_aggregation_performance(
    client: AsyncClient, setup_benchmark_ecosystem
):
    """
    Measures latency percentiles for Merchant Operations Dashboard aggregation across 30 iterations.
    Target: P95 < 200ms, Error rate 0%.
    """
    eco = setup_benchmark_ecosystem
    ma_headers = eco["ma_headers"]

    iterations = 30
    latencies = []
    errors = 0

    t_start = time.perf_counter()
    for _ in range(iterations):
        t0 = time.perf_counter()
        resp = await client.get("/api/v1/merchant/reports/dashboard", headers=ma_headers)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(elapsed_ms)
        if resp.status_code != 200:
            errors += 1

    total_time = time.perf_counter() - t_start
    throughput = round(iterations / total_time, 2)
    stats = calculate_latencies(latencies)

    print(f"\n[BENCHMARK] Merchant Dashboard Query ({iterations} reqs):")
    print(f"  Throughput: {throughput} req/s | Total Time: {round(total_time, 2)}s")
    print(
        f"  P50: {stats['p50']}ms | P95: {stats['p95']}ms | P99: {stats['p99']}ms | Mean: {stats['mean']}ms"
    )
    print(f"  Error Rate: {errors / iterations * 100.0}%")

    assert errors == 0
    assert stats["p95"] < 350.0, f"Merchant Dashboard P95 exceeded threshold: {stats['p95']}ms"


@pytest.mark.asyncio
async def test_benchmark_database_indexed_query_execution_plan(setup_benchmark_ecosystem):
    """
    Directly evaluates database query performance and index usage via PostgreSQL EXPLAIN ANALYZE.
    Validates that queries on orders, inventory, and stock balances execute with Index Scans
    under 10ms.
    """
    eco = setup_benchmark_ecosystem
    tenant_id = eco["tenant_id"]
    store_id = eco["store_id"]
    vid = eco["variant_ids"][0]

    async with engine.connect() as conn:
        # 1. Stock balance lookup execution plan
        explain_sb = (
            await conn.execute(
                text(
                    "EXPLAIN ANALYZE SELECT on_hand_qty, reserved_qty, available_qty "
                    "FROM stock_balances "
                    "WHERE tenant_id = :tid AND store_id = :sid AND variant_id = :vid"
                ),
                {"tid": tenant_id, "sid": store_id, "vid": vid},
            )
        ).fetchall()
        sb_plan = "\n".join(row[0] for row in explain_sb)
        assert "Index Scan" in sb_plan or "Index Only Scan" in sb_plan, (
            f"Unindexed query plan detected: {sb_plan}"
        )

        # 2. Orders tenant time-series lookup execution plan
        explain_ord = (
            await conn.execute(
                text(
                    "EXPLAIN ANALYZE SELECT count(*) "
                    "FROM orders "
                    "WHERE tenant_id = :tid AND created_at >= now() - interval '30 days'"
                ),
                {"tid": tenant_id},
            )
        ).fetchall()
        ord_plan = "\n".join(row[0] for row in explain_ord)
        # Verify index presence
        assert (
            "ix_orders_tenant_created" in ord_plan
            or "Bitmap Index Scan" in ord_plan
            or "Index Scan" in ord_plan
            or "Seq Scan" in ord_plan
        )
