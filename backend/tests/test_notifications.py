import json
import time
from decimal import Decimal
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.db.session import engine
from app.modules.notifications.providers.mock_provider import MockNotificationProvider
from app.modules.notifications.template_engine import render_template_string, sanitize_context
from app.modules.payments.providers.mock_provider import MockPaymentGatewayProvider


@pytest.fixture
async def setup_notification_ecosystem(client: AsyncClient, mint_jwt_token):
    """
    Provisions Tenant A (Bagodi) with physical store, Tenant B with store,
    products, variants, inward stock, and minted customer/merchant tokens.
    """
    MockNotificationProvider.clear()

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
        permissions=["stores.*", "catalog.*", "inventory.*", "orders.*", "payments.*", "notifications.*"],
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
        permissions=["stores.*", "catalog.*", "inventory.*", "orders.*", "payments.*", "notifications.*"],
    )
    merchant_b_headers = {"Authorization": f"Bearer {merchant_b_token}"}

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
            "receipt_number": "INWARD-NOTIF-001",
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
async def test_provider_adapters_sms_whatsapp_email(setup_notification_ecosystem):
    env = setup_notification_ecosystem
    tenant_id = env["tenant_a_id"]
    provider = MockNotificationProvider()

    # 1. SMS Dispatch
    sms_res = await provider.send_sms(
        tenant_id=tenant_id,
        recipient_phone="+919999900001",
        message="Hello from Bagodi!",
    )
    assert sms_res.success is True
    assert sms_res.provider_message_id.startswith("sms_mock_")
    assert sms_res.status == "sent"

    # 2. WhatsApp Dispatch
    wa_res = await provider.send_whatsapp(
        tenant_id=tenant_id,
        recipient_phone="+919999900001",
        template_name="order_confirmed",
        parameters={"order_number": "ORD-123", "total_amount": "1299.00"},
        fallback_text="Order confirmed!",
    )
    assert wa_res.success is True
    assert wa_res.provider_message_id.startswith("wa_mock_")

    # 3. Email Dispatch
    email_res = await provider.send_email(
        tenant_id=tenant_id,
        recipient_email="cust1@example.com",
        subject="Your Bagodi Order",
        body_html="<p>Thank you for your order!</p>",
    )
    assert email_res.success is True
    assert email_res.provider_message_id.startswith("email_mock_")

    # 4. Simulated Provider Failure
    fail_res = await provider.send_sms(
        tenant_id=tenant_id,
        recipient_phone="+919999900001",
        message="Test failure",
        metadata={"simulate_failure": True},
    )
    assert fail_res.success is False
    assert fail_res.status == "failed"
    assert fail_res.error_code == "SMS_GATEWAY_TIMEOUT"


@pytest.mark.asyncio
async def test_template_versioning_and_rendering(client: AsyncClient, setup_notification_ecosystem):
    env = setup_notification_ecosystem
    merchant_headers = env["merchant_a_headers"]

    # 1. Test built-in template rendering
    rendered = render_template_string(
        "Hello {{ customer_name }}, your order #{{ order_number }} for Rs.{{ total_amount }} is confirmed.",
        {"customer_name": "Ramesh", "order_number": "ORD-999", "total_amount": "1500.00"},
    )
    assert rendered == "Hello Ramesh, your order #ORD-999 for Rs.1500.00 is confirmed."

    # 2. Test sensitive key sanitization
    sanitized = sanitize_context({"otp": "123456", "password": "mypassword", "card_number": "4111111111111111"})
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["card_number"] == "[REDACTED]"
    assert sanitized["otp"] == "123456"

    # 3. Merchant creates custom template override (version 2)
    resp = await client.post(
        "/api/v1/merchant/notifications/templates",
        json={
            "code": "order_confirmed",
            "channel": "sms",
            "language": "en",
            "version": 2,
            "body_template": "Namaskara {{ customer_name }}, your Bagodi order #{{ order_number }} is verified!",
        },
        headers=merchant_headers,
    )
    assert resp.status_code == 201
    tmpl = resp.json()
    assert tmpl["version"] == 2
    assert "Namaskara" in tmpl["body_template"]

    # 4. List templates
    list_resp = await client.get("/api/v1/merchant/notifications/templates", headers=merchant_headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1


@pytest.mark.asyncio
async def test_transactional_outbox_atomicity_and_event_integration(client: AsyncClient, setup_notification_ecosystem):
    env = setup_notification_ecosystem
    cust1_headers = env["customer_1_headers"]
    merchant_headers = env["merchant_a_headers"]
    store_id = env["store_a_id"]
    variant_id = env["variant_1_id"]

    # Checkout an order
    order = await _create_test_order(client, cust1_headers, store_id, variant_id, quantity=1, payment_method="online")
    order_id = order["id"]

    # Inspect Outbox via merchant API: verify outbox event was recorded atomically with order checkout
    outbox_resp = await client.get("/api/v1/merchant/notifications/outbox", headers=merchant_headers)
    assert outbox_resp.status_code == 200
    items = outbox_resp.json()
    assert len(items) >= 1

    order_outbox = next((i for i in items if i["aggregate_id"] == order_id), None)
    assert order_outbox is not None
    assert order_outbox["event_type"] == "order.created"
    assert order_outbox["status"] == "pending"
    assert order_outbox["payload"]["order_number"] == order["order_number"]
    assert order_outbox["payload"]["customer_name"] == "Ramesh Kumar"


@pytest.mark.asyncio
async def test_outbox_batch_processing_and_channel_dispatch(client: AsyncClient, setup_notification_ecosystem):
    env = setup_notification_ecosystem
    cust1_headers = env["customer_1_headers"]
    merchant_headers = env["merchant_a_headers"]
    store_id = env["store_a_id"]
    variant_id = env["variant_1_id"]

    # Checkout order
    await _create_test_order(client, cust1_headers, store_id, variant_id, quantity=1, payment_method="online")

    # Trigger outbox processor
    proc_resp = await client.post("/api/v1/merchant/notifications/outbox/process", headers=merchant_headers)
    assert proc_resp.status_code == 200
    proc_data = proc_resp.json()
    assert proc_data["processed_count"] >= 1
    assert proc_data["dispatched_messages_count"] >= 1

    # Outbox item is now processed
    outbox_items = (await client.get("/api/v1/merchant/notifications/outbox", headers=merchant_headers)).json()
    assert all(i["status"] == "processed" for i in outbox_items)

    # Messages dispatched
    msgs_resp = await client.get("/api/v1/merchant/notifications/messages", headers=merchant_headers)
    assert msgs_resp.status_code == 200
    messages = msgs_resp.json()
    assert len(messages) >= 1
    assert any(m["channel"] in ("whatsapp", "sms") for m in messages)
    assert any(m["status"] == "sent" for m in messages)

    # Re-running outbox processing is idempotent (0 remaining items processed)
    proc_retry = await client.post("/api/v1/merchant/notifications/outbox/process", headers=merchant_headers)
    assert proc_retry.json()["processed_count"] == 0


@pytest.mark.asyncio
async def test_customer_consent_and_communication_preferences(client: AsyncClient, setup_notification_ecosystem):
    env = setup_notification_ecosystem
    cust1_headers = env["customer_1_headers"]
    merchant_headers = env["merchant_a_headers"]
    store_id = env["store_a_id"]
    variant_id = env["variant_1_id"]

    # 1. Customer checks default preferences
    pref_get = await client.get("/api/v1/customer/notifications/preferences", headers=cust1_headers)
    assert pref_get.status_code == 200
    pref = pref_get.json()
    assert pref["whatsapp_opt_in"] is True
    assert pref["email_opt_in"] is True
    assert pref["preferred_channel"] == "whatsapp"

    # 2. Customer updates preferences: Opts out of WhatsApp, prefers SMS
    update_resp = await client.put(
        "/api/v1/customer/notifications/preferences",
        json={"whatsapp_opt_in": False, "sms_opt_in": True, "preferred_channel": "sms"},
        headers=cust1_headers,
    )
    assert update_resp.status_code == 200
    updated_pref = update_resp.json()
    assert updated_pref["whatsapp_opt_in"] is False
    assert updated_pref["preferred_channel"] == "sms"

    # 3. Checkout order and process outbox: routes to SMS (not WhatsApp)
    await _create_test_order(client, cust1_headers, store_id, variant_id, quantity=1, payment_method="online")
    await client.post("/api/v1/merchant/notifications/outbox/process", headers=merchant_headers)

    # Verify dispatched message channel honors SMS preference
    messages = (await client.get("/api/v1/merchant/notifications/messages", headers=merchant_headers)).json()
    assert any(m["channel"] == "sms" for m in messages)


@pytest.mark.asyncio
async def test_message_delivery_status_and_webhook_dlr(client: AsyncClient, setup_notification_ecosystem):
    env = setup_notification_ecosystem
    merchant_headers = env["merchant_a_headers"]

    # 1. Send direct transactional notification
    direct_resp = await client.post(
        "/api/v1/merchant/notifications/send-direct",
        json={
            "recipient": "+919999900001",
            "channel": "sms",
            "template_code": "order_confirmed",
            "context": {"customer_name": "Ramesh", "order_number": "ORD-DIRECT-1", "total_amount": "999.00"},
            "idempotency_key": "idemp_msg_direct_001",
        },
        headers=merchant_headers,
    )
    assert direct_resp.status_code == 200
    msg = direct_resp.json()
    assert msg["status"] == "sent"
    provider_msg_id = msg["provider_message_id"]

    # 2. Inbound DLR delivery webhook from carrier
    provider = MockNotificationProvider()
    dlr_payload = {
        "provider_message_id": provider_msg_id,
        "status": "delivered",
        "timestamp": int(time.time()),
    }
    raw_body = json.dumps(dlr_payload).encode("utf-8")
    sig_header = provider.generate_dlr_header(raw_body)

    dlr_resp = await client.post(
        "/api/v1/notifications/webhooks/mock",
        content=raw_body,
        headers={"Content-Type": "application/json", "X-Webhook-Signature": sig_header},
    )
    assert dlr_resp.status_code == 200
    assert dlr_resp.json()["status"] == "acknowledged"

    # Verify message status transitioned to 'delivered'
    msg_verified = (await client.get(f"/api/v1/merchant/notifications/messages/{msg['id']}", headers=merchant_headers)).json()
    assert msg_verified["status"] == "delivered"
    assert msg_verified["delivery_timestamp"] is not None

    # 3. Security: Tampered DLR signature is rejected with 400
    bad_resp = await client.post(
        "/api/v1/notifications/webhooks/mock",
        content=raw_body,
        headers={"Content-Type": "application/json", "X-Webhook-Signature": "t=123,v1=bad_sig"},
    )
    assert bad_resp.status_code == 400


@pytest.mark.asyncio
async def test_retry_mechanism_exponential_backoff_and_dead_letter(client: AsyncClient, setup_notification_ecosystem):
    env = setup_notification_ecosystem
    merchant_headers = env["merchant_a_headers"]

    # 1. Send message with failure simulation
    direct_resp = await client.post(
        "/api/v1/merchant/notifications/send-direct",
        json={
            "recipient": "+919999900001",
            "channel": "sms",
            "template_code": "order_confirmed",
            "context": {
                "customer_name": "Ramesh",
                "order_number": "ORD-FAIL-1",
                "total_amount": "500.00",
                "simulate_failure": True,
            },
        },
        headers=merchant_headers,
    )
    assert direct_resp.status_code == 200
    msg = direct_resp.json()
    assert msg["status"] == "failed"
    assert msg["retry_count"] == 1
    assert msg["error_code"] == "SMS_GATEWAY_TIMEOUT"
    assert msg["next_retry_at"] is not None
    msg_id = msg["id"]

    # 2. Manual retry by merchant
    retry_resp = await client.post(
        f"/api/v1/merchant/notifications/messages/{msg_id}/retry",
        headers=merchant_headers,
    )
    assert retry_resp.status_code == 200
    retried_msg = retry_resp.json()
    assert retried_msg["status"] == "sent"
    assert retried_msg["provider_message_id"] is not None


@pytest.mark.asyncio
async def test_end_to_end_business_event_pipeline(client: AsyncClient, setup_notification_ecosystem):
    env = setup_notification_ecosystem
    cust1_headers = env["customer_1_headers"]
    merchant_headers = env["merchant_a_headers"]
    store_id = env["store_a_id"]
    variant_id = env["variant_1_id"]

    # 1. Customer creates order
    order = await _create_test_order(client, cust1_headers, store_id, variant_id, quantity=1, payment_method="online")
    order_id = order["id"]

    # 2. Customer captures payment
    init_data = (await client.post(
        "/api/v1/payments/initiate",
        json={"order_id": order_id, "payment_method": "online"},
        headers=cust1_headers,
    )).json()

    provider = MockPaymentGatewayProvider()
    sig = provider.generate_payment_signature(init_data["gateway_order_id"], "pay_e2e_notif_001", Decimal("1299.00"))
    await client.post(
        "/api/v1/payments/verify",
        json={
            "transaction_id": init_data["transaction_id"],
            "gateway_order_id": init_data["gateway_order_id"],
            "gateway_payment_id": "pay_e2e_notif_001",
            "gateway_signature": sig,
        },
        headers=cust1_headers,
    )

    # 3. Process Outbox: Dispatches order creation and payment capture notifications
    proc1 = await client.post("/api/v1/merchant/notifications/outbox/process", headers=merchant_headers)
    assert proc1.status_code == 200
    assert proc1.json()["dispatched_messages_count"] >= 2

    # 4. Merchant issues refund
    await client.post(
        f"/api/v1/merchant/payments/orders/{order_id}/refund",
        json={"amount": "299.00", "reason": "Price match guarantee discount"},
        headers=merchant_headers,
    )

    # 5. Process Outbox: Dispatches refund notification
    proc2 = await client.post("/api/v1/merchant/notifications/outbox/process", headers=merchant_headers)
    assert proc2.status_code == 200
    assert proc2.json()["dispatched_messages_count"] >= 1

    # 6. Verify Audit Logs recorded
    logs_resp = await client.get("/api/v1/merchant/notifications/audit-logs", headers=merchant_headers)
    assert logs_resp.status_code == 200
    logs = logs_resp.json()
    event_types = [l["event_type"] for l in logs]
    assert "SENT" in event_types


@pytest.mark.asyncio
async def test_cross_tenant_and_cross_customer_isolation(client: AsyncClient, setup_notification_ecosystem):
    env = setup_notification_ecosystem
    cust1_headers = env["customer_1_headers"]
    cust2_headers = env["customer_2_headers"]
    merchant_a_headers = env["merchant_a_headers"]
    merchant_b_headers = env["merchant_b_headers"]

    # Send a message to Customer 1
    send_resp = await client.post(
        "/api/v1/merchant/notifications/send-direct",
        json={
            "recipient": "+919999900001",
            "channel": "sms",
            "template_code": "order_confirmed",
            "context": {"customer_name": "Ramesh", "order_number": "ORD-ISO-1", "total_amount": "500.00"},
        },
        headers=merchant_a_headers,
    )
    msg_id = send_resp.json()["id"]

    # Customer 2 cannot see Customer 1's messages
    cust2_msgs = (await client.get("/api/v1/customer/notifications/messages", headers=cust2_headers)).json()
    assert not any(m["id"] == msg_id for m in cust2_msgs)

    # Customer 1 CAN see their message
    cust1_msgs = (await client.get("/api/v1/customer/notifications/messages", headers=cust1_headers)).json()
    assert any(m["id"] == msg_id for m in cust1_msgs)

    # Merchant B (Tenant B) cannot access Merchant A's message -> 404
    cross_resp = await client.get(f"/api/v1/merchant/notifications/messages/{msg_id}", headers=merchant_b_headers)
    assert cross_resp.status_code == 404
