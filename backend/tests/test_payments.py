import json
import time
from decimal import Decimal
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.db.session import engine
from app.modules.payments.providers.mock_provider import MockPaymentGatewayProvider


@pytest.fixture
async def setup_payment_ecosystem(client: AsyncClient, mint_jwt_token):
    """
    Provisions Tenant A (Bagodi) with physical store, Tenant B with store,
    products, variants, inward stock, and minted customer/merchant tokens.
    """
    platform_admin_token = mint_jwt_token(
        is_platform_user=True,
        permissions=["platform.*"],
    )
    platform_headers = {"Authorization": f"Bearer {platform_admin_token}"}

    # 1. Onboard Tenant A (Bagodi)
    resp_a = await client.post(
        "/api/v1/platform/tenants",
        json={
            "name": "Bagodi Bidar Store",
            "slug": "bagodi-bidar",
            "legal_name": "Bagodi Retail Private Limited",
            "contact_email": "ops@bagodi.in",
            "contact_phone": "+919876543210",
        },
        headers=platform_headers,
    )
    tenant_a_id = UUID(resp_a.json()["id"])
    await client.patch(
        f"/api/v1/platform/tenants/{tenant_a_id}/status",
        json={"status": "active"},
        headers=platform_headers,
    )

    # 2. Onboard Tenant B (Second Merchant)
    resp_b = await client.post(
        "/api/v1/platform/tenants",
        json={
            "name": "Second Merchant",
            "slug": "second-merchant",
            "legal_name": "Second Merchant LLP",
            "contact_email": "admin@secondmerchant.in",
            "contact_phone": "+919876543211",
        },
        headers=platform_headers,
    )
    tenant_b_id = UUID(resp_b.json()["id"])
    await client.patch(
        f"/api/v1/platform/tenants/{tenant_b_id}/status",
        json={"status": "active"},
        headers=platform_headers,
    )

    # 3. Create Store for Tenant A
    merchant_a_token = mint_jwt_token(
        tenant_id=tenant_a_id,
        permissions=["stores.*", "catalog.*", "inventory.*", "orders.*", "payments.*"],
    )
    merchant_a_headers = {"Authorization": f"Bearer {merchant_a_token}"}

    resp_store_a = await client.post(
        "/api/v1/stores",
        json={
            "name": "Bagodi Flagship Store Bidar",
            "code": "STORE01",
            "address_line": "Near Old Fort, Main Market",
            "city": "Bidar",
            "state": "Karnataka",
            "postal_code": "585401",
        },
        headers=merchant_a_headers,
    )
    store_a_id = UUID(resp_store_a.json()["id"])

    # 4. Create Store for Tenant B
    merchant_b_token = mint_jwt_token(
        tenant_id=tenant_b_id,
        permissions=["stores.*", "catalog.*", "inventory.*", "orders.*", "payments.*"],
    )
    merchant_b_headers = {"Authorization": f"Bearer {merchant_b_token}"}

    resp_store_b = await client.post(
        "/api/v1/stores",
        json={
            "name": "Second Merchant Store",
            "code": "STORE01",
            "address_line": "Market Road",
            "city": "Bidar",
            "state": "Karnataka",
            "postal_code": "585401",
        },
        headers=merchant_b_headers,
    )
    store_b_id = UUID(resp_store_b.json()["id"])

    # 5. Insert Customers into users table
    async with engine.begin() as conn:
        res_u1 = await conn.execute(
            text(
                "INSERT INTO users (id, phone_e164, email, display_name, status, is_platform_user, created_at, updated_at) "
                "VALUES (gen_random_uuid(), '+919999900001', 'cust1@example.com', 'Ramesh Kumar', 'active', false, now(), now()) "
                "RETURNING id;"
            )
        )
        customer_1_id = res_u1.scalar_one()

        res_u2 = await conn.execute(
            text(
                "INSERT INTO users (id, phone_e164, email, display_name, status, is_platform_user, created_at, updated_at) "
                "VALUES (gen_random_uuid(), '+919999900002', 'cust2@example.com', 'Suresh Patil', 'active', false, now(), now()) "
                "RETURNING id;"
            )
        )
        customer_2_id = res_u2.scalar_one()

    cust1_token = mint_jwt_token(
        user_id=customer_1_id,
        tenant_id=tenant_a_id,
        roles=["customer"],
        permissions=["customer.*"],
    )
    customer_1_headers = {"Authorization": f"Bearer {cust1_token}"}

    cust2_token = mint_jwt_token(
        user_id=customer_2_id,
        tenant_id=tenant_a_id,
        roles=["customer"],
        permissions=["customer.*"],
    )
    customer_2_headers = {"Authorization": f"Bearer {cust2_token}"}

    # 6. Create Catalogue Category, Product and Variant
    cat_a = (await client.post(
        "/api/v1/merchant/catalog/categories",
        json={"name": "Bidri Handicrafts", "slug": "bidri-handicrafts"},
        headers=merchant_a_headers,
    )).json()

    prod_a = (await client.post(
        "/api/v1/merchant/catalog/products",
        json={
            "category_id": cat_a["id"],
            "name": "Bidri Inlaid Vase",
            "slug": "bidri-inlaid-vase",
            "status": "active",
            "is_published": True,
            "variants": [
                {
                    "sku": "BIDRI-VASE-S",
                    "barcode": "8908880001",
                    "name": "Small Inlaid Vase",
                    "mrp": "1500.00",
                    "base_price": "1299.00",
                }
            ],
        },
        headers=merchant_a_headers,
    )).json()
    variant_1_id = UUID(prod_a["variants"][0]["id"])

    # Inward stock (50 units)
    await client.post(
        "/api/v1/merchant/inventory/receipts",
        json={
            "store_id": str(store_a_id),
            "receipt_number": "INWARD-PAY-001",
            "items": [
                {
                    "variant_id": str(variant_1_id),
                    "quantity_received": 50,
                    "unit_cost": "750.00",
                }
            ],
        },
        headers=merchant_a_headers,
    )

    return {
        "tenant_a_id": tenant_a_id,
        "tenant_b_id": tenant_b_id,
        "store_a_id": store_a_id,
        "store_b_id": store_b_id,
        "merchant_a_headers": merchant_a_headers,
        "merchant_b_headers": merchant_b_headers,
        "customer_1_id": customer_1_id,
        "customer_2_id": customer_2_id,
        "customer_1_headers": customer_1_headers,
        "customer_2_headers": customer_2_headers,
        "variant_1_id": variant_1_id,
    }


async def _create_test_order(
    client: AsyncClient,
    cust_headers: dict,
    store_id: UUID,
    variant_id: UUID,
    quantity: int = 1,
    payment_method: str = "online",
) -> dict:
    """Helper to add item to cart and checkout an order."""
    await client.post(
        "/api/v1/cart/items",
        json={"variant_id": str(variant_id), "quantity": quantity},
        headers=cust_headers,
    )
    checkout_payload = {
        "store_id": str(store_id),
        "payment_method": payment_method,
        "shipping_address": {
            "full_name": "Ramesh Kumar",
            "phone": "+919999900001",
            "address_line1": "Flat 101, Fort View",
            "city": "Bidar",
            "state": "Karnataka",
            "postal_code": "585401",
        },
        "customer_name": "Ramesh Kumar",
        "customer_email": "cust1@example.com",
        "customer_phone": "+919999900001",
    }
    resp = await client.post(
        "/api/v1/orders/checkout",
        json=checkout_payload,
        headers=cust_headers,
    )
    assert resp.status_code == 201, f"Checkout failed: {resp.text}"
    return resp.json()


@pytest.mark.asyncio
async def test_payment_initiation_and_idempotency(client: AsyncClient, setup_payment_ecosystem):
    env = setup_payment_ecosystem
    cust1_headers = env["customer_1_headers"]
    cust2_headers = env["customer_2_headers"]
    store_id = env["store_a_id"]
    variant_id = env["variant_1_id"]

    order = await _create_test_order(client, cust1_headers, store_id, variant_id, quantity=1, payment_method="online")
    order_id = order["id"]

    # 1. Customer initiates payment
    init_resp = await client.post(
        "/api/v1/payments/initiate",
        json={
            "order_id": order_id,
            "payment_method": "online",
            "idempotency_key": "idemp_pay_001",
        },
        headers=cust1_headers,
    )
    assert init_resp.status_code == 200
    init_data = init_resp.json()
    assert init_data["order_id"] == order_id
    assert init_data["amount"] == "1299.00"
    assert init_data["status"] == "initiated"
    assert init_data["gateway_provider"] == "mock"
    assert init_data["gateway_order_id"].startswith("order_mock_")
    assert "https://checkout.bagodi.test/pay/" in init_data["checkout_url"]
    txn_id = init_data["transaction_id"]

    # 2. Idempotent Retry: Same idempotency_key returns identical transaction
    retry_resp = await client.post(
        "/api/v1/payments/initiate",
        json={
            "order_id": order_id,
            "payment_method": "online",
            "idempotency_key": "idemp_pay_001",
        },
        headers=cust1_headers,
    )
    assert retry_resp.status_code == 200
    retry_data = retry_resp.json()
    assert retry_data["transaction_id"] == txn_id
    assert retry_data["gateway_order_id"] == init_data["gateway_order_id"]

    # 3. Security Boundary: Customer 2 attempts to initiate payment for Customer 1's order -> 403 Forbidden
    cust2_resp = await client.post(
        "/api/v1/payments/initiate",
        json={"order_id": order_id, "payment_method": "online"},
        headers=cust2_headers,
    )
    assert cust2_resp.status_code == 403


@pytest.mark.asyncio
async def test_payment_verification_success_and_order_transition(client: AsyncClient, setup_payment_ecosystem):
    env = setup_payment_ecosystem
    cust1_headers = env["customer_1_headers"]
    store_id = env["store_a_id"]
    variant_id = env["variant_1_id"]

    order = await _create_test_order(client, cust1_headers, store_id, variant_id, quantity=1, payment_method="online")
    order_id = order["id"]

    init_resp = await client.post(
        "/api/v1/payments/initiate",
        json={"order_id": order_id, "payment_method": "online"},
        headers=cust1_headers,
    )
    assert init_resp.status_code == 200
    init_data = init_resp.json()
    txn_id = init_data["transaction_id"]
    gw_order_id = init_data["gateway_order_id"]
    gw_payment_id = "pay_mock_success_123"

    # Generate valid HMAC-SHA256 signature
    provider = MockPaymentGatewayProvider()
    valid_sig = provider.generate_payment_signature(gw_order_id, gw_payment_id, Decimal("1299.00"))

    # Verify payment
    verify_resp = await client.post(
        "/api/v1/payments/verify",
        json={
            "transaction_id": txn_id,
            "gateway_order_id": gw_order_id,
            "gateway_payment_id": gw_payment_id,
            "gateway_signature": valid_sig,
        },
        headers=cust1_headers,
    )
    assert verify_resp.status_code == 200
    txn_data = verify_resp.json()
    assert txn_data["status"] == "captured"
    assert txn_data["gateway_payment_id"] == gw_payment_id
    assert txn_data["gateway_fee"] == "25.98"  # 2% of 1299.00
    assert txn_data["gateway_tax"] == "4.68"  # 18% of 25.98
    assert txn_data["captured_at"] is not None

    # Check order transitioned to CONFIRMED
    ord_resp = await client.get(
        f"/api/v1/orders/{order['order_number']}",
        headers=cust1_headers,
    )
    assert ord_resp.status_code == 200
    ord_data = ord_resp.json()
    assert ord_data["status"] == "CONFIRMED"
    assert ord_data["payment_status"] == "captured"

    # Idempotent re-verify returns 200 without duplicate mutation
    reverify_resp = await client.post(
        "/api/v1/payments/verify",
        json={
            "transaction_id": txn_id,
            "gateway_order_id": gw_order_id,
            "gateway_payment_id": gw_payment_id,
            "gateway_signature": valid_sig,
        },
        headers=cust1_headers,
    )
    assert reverify_resp.status_code == 200

    # Initiating on already paid order is rejected
    reinit_resp = await client.post(
        "/api/v1/payments/initiate",
        json={"order_id": order_id, "payment_method": "online"},
        headers=cust1_headers,
    )
    assert reinit_resp.status_code == 400
    assert reinit_resp.json()["code"] == "ORDER_ALREADY_PAID"


@pytest.mark.asyncio
async def test_payment_verification_invalid_signature_failure(client: AsyncClient, setup_payment_ecosystem):
    env = setup_payment_ecosystem
    cust1_headers = env["customer_1_headers"]
    store_id = env["store_a_id"]
    variant_id = env["variant_1_id"]

    order = await _create_test_order(client, cust1_headers, store_id, variant_id, quantity=1, payment_method="online")
    order_id = order["id"]

    init_resp = await client.post(
        "/api/v1/payments/initiate",
        json={"order_id": order_id, "payment_method": "online"},
        headers=cust1_headers,
    )
    init_data = init_resp.json()
    txn_id = init_data["transaction_id"]

    # Submit forged cryptographic signature
    verify_resp = await client.post(
        "/api/v1/payments/verify",
        json={
            "transaction_id": txn_id,
            "gateway_order_id": init_data["gateway_order_id"],
            "gateway_payment_id": "pay_fake_999",
            "gateway_signature": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        },
        headers=cust1_headers,
    )
    assert verify_resp.status_code == 400
    assert verify_resp.json()["code"] == "PAYMENT_VERIFICATION_FAILED"

    # Verify transaction marked as failed
    payments_resp = await client.get(
        f"/api/v1/orders/{order_id}/payments",
        headers=cust1_headers,
    )
    assert payments_resp.status_code == 200
    assert payments_resp.json()[0]["status"] == "failed"

    # Order remains PENDING_PAYMENT
    ord_resp = await client.get(
        f"/api/v1/orders/{order['order_number']}",
        headers=cust1_headers,
    )
    assert ord_resp.json()["status"] == "PENDING_PAYMENT"
    assert ord_resp.json()["payment_status"] == "pending"


@pytest.mark.asyncio
async def test_payment_webhook_processing_and_replay_protection(client: AsyncClient, setup_payment_ecosystem):
    env = setup_payment_ecosystem
    cust1_headers = env["customer_1_headers"]
    store_id = env["store_a_id"]
    variant_id = env["variant_1_id"]

    order = await _create_test_order(client, cust1_headers, store_id, variant_id, quantity=1, payment_method="online")
    order_id = order["id"]

    init_resp = await client.post(
        "/api/v1/payments/initiate",
        json={"order_id": order_id, "payment_method": "online"},
        headers=cust1_headers,
    )
    init_data = init_resp.json()
    gw_order_id = init_data["gateway_order_id"]

    # Prepare webhook payload
    event_id = "evt_webhook_live_001"
    webhook_dict = {
        "event_id": event_id,
        "event": "payment.captured",
        "payload": {
            "payment": {
                "gateway_order_id": gw_order_id,
                "gateway_payment_id": "pay_webhook_live_777",
                "amount": "1299.00",
                "status": "captured",
            }
        },
    }
    raw_body = json.dumps(webhook_dict).encode("utf-8")

    provider = MockPaymentGatewayProvider()
    sig_header = provider.generate_webhook_header(raw_body)

    # 1. Post webhook to public endpoint
    wh_resp = await client.post(
        "/api/v1/payments/webhooks/mock",
        content=raw_body,
        headers={"Content-Type": "application/json", "X-Webhook-Signature": sig_header},
    )
    assert wh_resp.status_code == 200
    assert wh_resp.json()["status"] == "processed"

    # Order confirmed via webhook
    ord_resp = await client.get(
        f"/api/v1/orders/{order['order_number']}",
        headers=cust1_headers,
    )
    assert ord_resp.json()["status"] == "CONFIRMED"
    assert ord_resp.json()["payment_status"] == "captured"

    # 2. Replay Attack / Repeated Webhook Delivery: Exact same event_id
    replay_resp = await client.post(
        "/api/v1/payments/webhooks/mock",
        content=raw_body,
        headers={"Content-Type": "application/json", "X-Webhook-Signature": sig_header},
    )
    assert replay_resp.status_code == 200
    assert replay_resp.json()["status"] == "already_processed"


@pytest.mark.asyncio
async def test_payment_webhook_security_signature_and_timestamp_expiration(client: AsyncClient, setup_payment_ecosystem):
    raw_body = b'{"event_id": "evt_test", "event": "payment.captured"}'

    # 1. Invalid signature
    resp_bad_sig = await client.post(
        "/api/v1/payments/webhooks/mock",
        content=raw_body,
        headers={"Content-Type": "application/json", "X-Webhook-Signature": "t=1234567,v1=invalidsig"},
    )
    assert resp_bad_sig.status_code == 400
    assert resp_bad_sig.json()["code"] == "INVALID_WEBHOOK"

    # 2. Expired timestamp (older than 300 seconds tolerance)
    provider = MockPaymentGatewayProvider()
    stale_timestamp = int(time.time()) - 600  # 10 minutes ago
    stale_sig = provider.generate_webhook_header(raw_body, timestamp=stale_timestamp)

    resp_stale = await client.post(
        "/api/v1/payments/webhooks/mock",
        content=raw_body,
        headers={"Content-Type": "application/json", "X-Webhook-Signature": stale_sig},
    )
    assert resp_stale.status_code == 400
    assert resp_stale.json()["code"] == "INVALID_WEBHOOK"


@pytest.mark.asyncio
async def test_full_and_partial_refunds(client: AsyncClient, setup_payment_ecosystem):
    env = setup_payment_ecosystem
    cust1_headers = env["customer_1_headers"]
    merchant_headers = env["merchant_a_headers"]
    store_id = env["store_a_id"]
    variant_id = env["variant_1_id"]

    order = await _create_test_order(client, cust1_headers, store_id, variant_id, quantity=1, payment_method="online")
    order_id = order["id"]

    # Initiate & verify payment
    init_data = (await client.post(
        "/api/v1/payments/initiate",
        json={"order_id": order_id, "payment_method": "online"},
        headers=cust1_headers,
    )).json()

    provider = MockPaymentGatewayProvider()
    sig = provider.generate_payment_signature(init_data["gateway_order_id"], "pay_refund_101", Decimal("1299.00"))
    await client.post(
        "/api/v1/payments/verify",
        json={
            "transaction_id": init_data["transaction_id"],
            "gateway_order_id": init_data["gateway_order_id"],
            "gateway_payment_id": "pay_refund_101",
            "gateway_signature": sig,
        },
        headers=cust1_headers,
    )

    # 1. Partial Refund: ₹500.00
    rfd1_resp = await client.post(
        f"/api/v1/merchant/payments/orders/{order_id}/refund",
        json={"amount": "500.00", "reason": "Customer requested partial return", "idempotency_key": "idemp_rfd_001"},
        headers=merchant_headers,
    )
    assert rfd1_resp.status_code == 201
    rfd1 = rfd1_resp.json()
    assert rfd1["amount"] == "500.00"
    assert rfd1["status"] == "succeeded"

    # Verify transaction amount_refunded
    txn1 = (await client.get(f"/api/v1/orders/{order_id}/payments", headers=cust1_headers)).json()[0]
    assert txn1["amount_refunded"] == "500.00"
    assert txn1["status"] == "partially_refunded"

    # 2. Idempotent Refund Retry with same key
    rfd1_retry = await client.post(
        f"/api/v1/merchant/payments/orders/{order_id}/refund",
        json={"amount": "500.00", "reason": "Customer requested partial return", "idempotency_key": "idemp_rfd_001"},
        headers=merchant_headers,
    )
    assert rfd1_retry.status_code == 201
    assert rfd1_retry.json()["id"] == rfd1["id"]

    # 3. Excessive Refund: Attempting ₹800.00 when remaining refundable balance is ₹799.00 (1299 - 500)
    excess_resp = await client.post(
        f"/api/v1/merchant/payments/orders/{order_id}/refund",
        json={"amount": "800.00", "reason": "Excessive amount"},
        headers=merchant_headers,
    )
    assert excess_resp.status_code == 400
    assert excess_resp.json()["code"] == "REFUND_EXCEEDS_BALANCE"

    # 4. Remaining Refund: ₹799.00 (Leaves 0 balance)
    rfd2_resp = await client.post(
        f"/api/v1/merchant/payments/orders/{order_id}/refund",
        json={"amount": "799.00", "reason": "Remaining balance refund"},
        headers=merchant_headers,
    )
    assert rfd2_resp.status_code == 201

    txn2 = (await client.get(f"/api/v1/orders/{order_id}/payments", headers=cust1_headers)).json()[0]
    assert txn2["amount_refunded"] == "1299.00"
    assert txn2["status"] == "refunded"

    # 5. Subsequent refund rejected since balance is zero
    empty_resp = await client.post(
        f"/api/v1/merchant/payments/orders/{order_id}/refund",
        json={"amount": "10.00", "reason": "Over-refund attempt"},
        headers=merchant_headers,
    )
    assert empty_resp.status_code == 400
    assert empty_resp.json()["code"] == "ALREADY_FULLY_REFUNDED"


@pytest.mark.asyncio
async def test_order_cancellation_triggers_automatic_refund(client: AsyncClient, setup_payment_ecosystem):
    env = setup_payment_ecosystem
    cust1_headers = env["customer_1_headers"]
    merchant_headers = env["merchant_a_headers"]
    store_id = env["store_a_id"]
    variant_id = env["variant_1_id"]

    order = await _create_test_order(client, cust1_headers, store_id, variant_id, quantity=1, payment_method="online")
    order_id = order["id"]

    # Initiate & capture payment
    init_data = (await client.post(
        "/api/v1/payments/initiate",
        json={"order_id": order_id, "payment_method": "online"},
        headers=cust1_headers,
    )).json()

    provider = MockPaymentGatewayProvider()
    sig = provider.generate_payment_signature(init_data["gateway_order_id"], "pay_auto_rfd_202", Decimal("1299.00"))
    await client.post(
        "/api/v1/payments/verify",
        json={
            "transaction_id": init_data["transaction_id"],
            "gateway_order_id": init_data["gateway_order_id"],
            "gateway_payment_id": "pay_auto_rfd_202",
            "gateway_signature": sig,
        },
        headers=cust1_headers,
    )

    # Cancel confirmed order
    cancel_resp = await client.patch(
        f"/api/v1/merchant/orders/{order_id}/status",
        json={"status": "CANCELLED", "notes": "Customer cancelled order before dispatch"},
        headers=merchant_headers,
    )
    assert cancel_resp.status_code == 200
    cancelled_order = cancel_resp.json()
    assert cancelled_order["status"] == "CANCELLED"
    assert cancelled_order["payment_status"] == "refunded"

    # Verify automatic refund was recorded
    refunds_resp = await client.get(f"/api/v1/orders/{order_id}/refunds", headers=cust1_headers)
    assert refunds_resp.status_code == 200
    refunds = refunds_resp.json()
    assert len(refunds) == 1
    assert refunds[0]["amount"] == "1299.00"
    assert refunds[0]["status"] == "succeeded"


@pytest.mark.asyncio
async def test_cash_on_delivery_collection_and_bank_reconciliation(client: AsyncClient, setup_payment_ecosystem):
    env = setup_payment_ecosystem
    cust1_headers = env["customer_1_headers"]
    merchant_headers = env["merchant_a_headers"]
    store_id = env["store_a_id"]
    variant_id = env["variant_1_id"]

    # 1. Checkout with payment_method="cod"
    order = await _create_test_order(client, cust1_headers, store_id, variant_id, quantity=1, payment_method="cod")
    order_id = order["id"]
    assert order["status"] == "CONFIRMED"
    assert order["payment_status"] == "pending"

    # Advance to DELIVERED
    await client.patch(
        f"/api/v1/merchant/orders/{order_id}/status",
        json={"status": "PROCESSING"},
        headers=merchant_headers,
    )
    await client.patch(
        f"/api/v1/merchant/orders/{order_id}/status",
        json={"status": "DISPATCHED"},
        headers=merchant_headers,
    )
    await client.patch(
        f"/api/v1/merchant/orders/{order_id}/status",
        json={"status": "DELIVERED"},
        headers=merchant_headers,
    )

    # 2. Record COD Cash Collection
    collect_resp = await client.post(
        f"/api/v1/merchant/payments/cod/{order_id}/collect",
        json={
            "amount_collected": "1299.00",
            "collected_by_name": "Delivery Agent Suresh",
            "notes": "Cash collected in Bidar Fort Area",
        },
        headers=merchant_headers,
    )
    assert collect_resp.status_code == 201
    settlement = collect_resp.json()
    assert settlement["amount_collected"] == "1299.00"
    assert settlement["settlement_status"] == "pending_deposit"
    settlement_id = settlement["id"]

    # Payment transaction is now captured
    txns = (await client.get(f"/api/v1/orders/{order_id}/payments", headers=cust1_headers)).json()
    assert len(txns) == 1
    assert txns[0]["status"] == "captured"
    assert txns[0]["payment_method"] == "cod"

    # Duplicate collection fails
    dup_resp = await client.post(
        f"/api/v1/merchant/payments/cod/{order_id}/collect",
        json={"amount_collected": "1299.00", "collected_by_name": "Duplicate Agent"},
        headers=merchant_headers,
    )
    assert dup_resp.status_code == 409

    # 3. Bank Reconciliation
    reconcile_resp = await client.post(
        f"/api/v1/merchant/payments/cod/{settlement_id}/reconcile",
        json={
            "bank_deposit_reference": "SBI-CASH-DEP-BIDAR-20261108",
            "notes": "Deposited to SBI Bidar Branch Account #1234",
        },
        headers=merchant_headers,
    )
    assert reconcile_resp.status_code == 200
    reconciled = reconcile_resp.json()
    assert reconciled["settlement_status"] == "reconciled"
    assert reconciled["bank_deposit_reference"] == "SBI-CASH-DEP-BIDAR-20261108"
    assert reconciled["settled_at"] is not None

    # List settlements filter
    list_settle = await client.get(
        "/api/v1/merchant/payments/cod/settlements?settlement_status=reconciled",
        headers=merchant_headers,
    )
    assert list_settle.status_code == 200
    assert len(list_settle.json()) == 1


@pytest.mark.asyncio
async def test_reconciliation_summary_and_audit_logs(client: AsyncClient, setup_payment_ecosystem):
    env = setup_payment_ecosystem
    cust1_headers = env["customer_1_headers"]
    merchant_headers = env["merchant_a_headers"]
    store_id = env["store_a_id"]
    variant_id = env["variant_1_id"]

    # Create & capture an online order
    order = await _create_test_order(client, cust1_headers, store_id, variant_id, quantity=1, payment_method="online")
    order_id = order["id"]

    init_data = (await client.post(
        "/api/v1/payments/initiate",
        json={"order_id": order_id, "payment_method": "online"},
        headers=cust1_headers,
    )).json()

    provider = MockPaymentGatewayProvider()
    sig = provider.generate_payment_signature(init_data["gateway_order_id"], "pay_sum_001", Decimal("1299.00"))
    await client.post(
        "/api/v1/payments/verify",
        json={
            "transaction_id": init_data["transaction_id"],
            "gateway_order_id": init_data["gateway_order_id"],
            "gateway_payment_id": "pay_sum_001",
            "gateway_signature": sig,
        },
        headers=cust1_headers,
    )

    # Partial refund ₹299.00
    await client.post(
        f"/api/v1/merchant/payments/orders/{order_id}/refund",
        json={"amount": "299.00", "reason": "Courtesy discount"},
        headers=merchant_headers,
    )

    # 1. Summary Endpoint
    summary_resp = await client.get(
        "/api/v1/merchant/payments/reconciliation/summary",
        headers=merchant_headers,
    )
    assert summary_resp.status_code == 200
    summary = summary_resp.json()
    assert summary["total_captured_amount"] == "1299.00"
    assert summary["total_refunded_amount"] == "299.00"
    assert summary["total_gateway_fees"] == "25.98"
    assert summary["total_gateway_taxes"] == "4.68"
    assert summary["transactions_count"] == 1
    assert summary["refunds_count"] == 1

    # 2. Audit Logs Endpoint
    logs_resp = await client.get(
        "/api/v1/merchant/payments/audit-logs",
        headers=merchant_headers,
    )
    assert logs_resp.status_code == 200, logs_resp.text
    logs = logs_resp.json()
    event_types = [entry["event_type"] for entry in logs]
    assert "PAYMENT_INITIATED" in event_types
    assert "PAYMENT_CAPTURED" in event_types
    assert "REFUND_SUCCEEDED" in event_types


@pytest.mark.asyncio
async def test_cross_tenant_and_cross_customer_isolation(client: AsyncClient, setup_payment_ecosystem):
    env = setup_payment_ecosystem
    cust1_headers = env["customer_1_headers"]
    cust2_headers = env["customer_2_headers"]
    merchant_b_headers = env["merchant_b_headers"]
    store_id = env["store_a_id"]
    variant_id = env["variant_1_id"]

    order = await _create_test_order(client, cust1_headers, store_id, variant_id, quantity=1, payment_method="online")
    order_id = order["id"]

    # Customer 2 attempts to get payments for customer 1's order -> 403 Forbidden
    resp_cross_cust = await client.get(f"/api/v1/orders/{order_id}/payments", headers=cust2_headers)
    assert resp_cross_cust.status_code == 403

    # Customer 2 attempts to get refunds for customer 1's order -> 403 Forbidden
    resp_cross_rfd = await client.get(f"/api/v1/orders/{order_id}/refunds", headers=cust2_headers)
    assert resp_cross_rfd.status_code == 403

    # Merchant B (Tenant B) attempts to initiate refund on Tenant A's order -> 404 (isolated)
    resp_cross_tenant = await client.post(
        f"/api/v1/merchant/payments/orders/{order_id}/refund",
        json={"amount": "100.00", "reason": "Cross tenant intrusion attempt"},
        headers=merchant_b_headers,
    )
    assert resp_cross_tenant.status_code == 404
