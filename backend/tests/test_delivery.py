import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text

from app.db.session import engine
from app.modules.delivery.models import (
    DeliveryPersonnel,
    DeliveryTrackingEvent,
    ProofOfDelivery,
    Shipment,
)
from app.modules.delivery.providers.mock_courier import MockCourierProvider
from app.modules.notifications.models import NotificationOutbox
from app.modules.orders.models import Order
from app.modules.payments.models import CodSettlement
from app.modules.payments.providers.mock_provider import MockPaymentGatewayProvider


@pytest.fixture
async def setup_delivery_ecosystem(client: AsyncClient, mint_jwt_token):
    """
    Provisions a comprehensive multi-tenant testing ecosystem:
    - Tenant A (Bagodi) with Store A, products, stock in ledger
    - Tenant B (Second Merchant) with Store B
    - Delivery zones and PIN codes for Tenant A
    - Delivery vehicles and internal delivery staff for Tenant A
    - Customer accounts for Customer 1 and Customer 2
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
        permissions=[
            "stores.*",
            "catalog.*",
            "inventory.*",
            "orders.*",
            "payments.*",
            "delivery.*",
            "notifications.*",
        ],
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
        permissions=[
            "stores.*",
            "catalog.*",
            "inventory.*",
            "orders.*",
            "payments.*",
            "delivery.*",
            "notifications.*",
        ],
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

    # 5. Insert Customers & Staff Users
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

        res_staff = await conn.execute(
            text(
                "INSERT INTO users (id, phone_e164, email, display_name, status, is_platform_user, created_at, updated_at) "
                "VALUES (gen_random_uuid(), '+919888800001', 'rider1@bagodi.in', 'Anand Kumar', 'active', false, now(), now()) "
                "RETURNING id;"
            )
        )
        staff_user_id = res_staff.scalar_one()

    customer_1_token = mint_jwt_token(
        user_id=customer_1_id,
        tenant_id=tenant_a_id,
        roles=["customer"],
        permissions=["customer.*"],
    )
    customer_1_headers = {"Authorization": f"Bearer {customer_1_token}"}

    customer_2_token = mint_jwt_token(
        user_id=customer_2_id,
        tenant_id=tenant_a_id,
        roles=["customer"],
        permissions=["customer.*"],
    )
    customer_2_headers = {"Authorization": f"Bearer {customer_2_token}"}

    delivery_staff_token = mint_jwt_token(
        user_id=staff_user_id,
        tenant_id=tenant_a_id,
        roles=["delivery_staff"],
        permissions=["delivery:staff", "delivery.*"],
    )
    delivery_staff_headers = {"Authorization": f"Bearer {delivery_staff_token}"}

    # 6. Create Catalogue Category & Product with Variants
    cat_a = (
        await client.post(
            "/api/v1/merchant/catalog/categories",
            json={"name": "Bidri Handicrafts", "slug": "bidri-handicrafts"},
            headers=merchant_a_headers,
        )
    ).json()

    prod_a = (
        await client.post(
            "/api/v1/merchant/catalog/products",
            json={
                "category_id": cat_a["id"],
                "name": "Bidri Inlaid Vase",
                "slug": "bidri-inlaid-vase",
                "status": "active",
                "is_published": True,
                "variants": [
                    {
                        "name": "Small Inlaid Vase",
                        "sku": "BIDRI-VASE-S",
                        "barcode": "8908880001",
                        "mrp": "1500.00",
                        "base_price": "1200.00",
                    }
                ],
            },
            headers=merchant_a_headers,
        )
    ).json()
    variant_id = UUID(prod_a["variants"][0]["id"])

    # 7. Inward Stock into Store A
    await client.post(
        "/api/v1/merchant/inventory/receipts",
        json={
            "store_id": str(store_a_id),
            "receipt_number": "INWARD-DELIV-001",
            "items": [
                {
                    "variant_id": str(variant_id),
                    "quantity_received": 100,
                    "unit_cost": "800.00",
                }
            ],
        },
        headers=merchant_a_headers,
    )

    # 8. Configure Delivery Zone & PIN Codes for Tenant A
    zone_resp = await client.post(
        "/api/v1/merchant/delivery/zones",
        json={
            "code": "BIDAR_URBAN",
            "name": "Bidar Urban Express",
            "description": "Local city center delivery zone",
            "is_active": True,
            "supports_internal_delivery": True,
            "supports_courier": True,
            "supports_cod": True,
            "base_delivery_fee": "50.00",
            "free_delivery_threshold": "1000.00",
            "estimated_delivery_hours": 24,
        },
        headers=merchant_a_headers,
    )
    zone_id = UUID(zone_resp.json()["id"])

    # Add PIN codes: 585401 (standard base fee) & 585402 (override 30.00)
    await client.post(
        f"/api/v1/merchant/delivery/zones/{zone_id}/pincodes",
        json={"pincodes": ["585401"], "is_serviceable": True},
        headers=merchant_a_headers,
    )
    await client.post(
        f"/api/v1/merchant/delivery/zones/{zone_id}/pincodes",
        json={"pincodes": ["585402"], "is_serviceable": True, "delivery_charge_override": "30.00"},
        headers=merchant_a_headers,
    )

    # 9. Register Delivery Vehicles for Tenant A
    vehicle_resp = await client.post(
        "/api/v1/merchant/delivery/vehicles",
        json={
            "store_id": str(store_a_id),
            "vehicle_type": "MOTORCYCLE",
            "registration_number": "KA-38-E-1001",
            "brand_model": "Hero Splendor Plus",
            "max_weight_capacity_kg": "25.00",
            "status": "AVAILABLE",
            "is_active": True,
        },
        headers=merchant_a_headers,
    )
    assert vehicle_resp.status_code == 201, (
        f"Vehicle creation failed: {vehicle_resp.status_code} {vehicle_resp.text}"
    )
    vehicle_id = UUID(vehicle_resp.json()["id"])

    # 10. Register Delivery Personnel for Tenant A
    personnel_resp = await client.post(
        "/api/v1/merchant/delivery/personnel",
        json={
            "store_id": str(store_a_id),
            "user_id": str(staff_user_id),
            "employee_code": "DEL-001",
            "full_name": "Anand Kumar",
            "phone_number": "+919888800001",
            "driving_license_number": "KA38-2022-0001234",
            "assigned_vehicle_id": str(vehicle_id),
            "verification_status": "VERIFIED",
            "duty_status": "AVAILABLE",
            "is_active": True,
        },
        headers=merchant_a_headers,
    )
    personnel_id = UUID(personnel_resp.json()["id"])

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
        "staff_user_id": staff_user_id,
        "delivery_staff_headers": delivery_staff_headers,
        "variant_id": variant_id,
        "zone_id": zone_id,
        "vehicle_id": vehicle_id,
        "personnel_id": personnel_id,
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


async def _pay_order_online(
    client: AsyncClient,
    cust_headers: dict,
    order_id: str,
    amount: Decimal,
) -> dict:
    """Helper to initiate and verify online payment for an order."""
    init_resp = await client.post(
        "/api/v1/payments/initiate",
        json={"order_id": order_id, "payment_method": "online"},
        headers=cust_headers,
    )
    assert init_resp.status_code == 200, f"Payment init failed: {init_resp.text}"
    init_data = init_resp.json()
    txn_id = init_data["transaction_id"]
    gw_order_id = init_data["gateway_order_id"]
    gw_payment_id = f"pay_mock_{order_id[:8]}"

    provider = MockPaymentGatewayProvider()
    valid_sig = provider.generate_payment_signature(gw_order_id, gw_payment_id, amount)

    verify_resp = await client.post(
        "/api/v1/payments/verify",
        json={
            "transaction_id": txn_id,
            "gateway_order_id": gw_order_id,
            "gateway_payment_id": gw_payment_id,
            "gateway_signature": valid_sig,
        },
        headers=cust_headers,
    )
    assert verify_resp.status_code == 200, f"Payment verify failed: {verify_resp.text}"
    return verify_resp.json()


# =============================================================================
# 1. Delivery Zone & Dynamic Serviceability Tests
# =============================================================================
@pytest.mark.asyncio
async def test_delivery_zone_and_serviceability_rules(
    client: AsyncClient, setup_delivery_ecosystem
):
    eco = setup_delivery_ecosystem
    tenant_a_id = eco["tenant_a_id"]
    merchant_a_headers = eco["merchant_a_headers"]

    # 1. Standard base fee for serviceable PIN 585401
    resp = await client.post(
        "/api/v1/delivery/serviceability/check",
        json={"tenant_id": str(tenant_a_id), "pincode": "585401", "order_amount": "400.00"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["serviceable"] is True
    assert data["zone_code"] == "BIDAR_URBAN"
    assert Decimal(data["delivery_fee"]) == Decimal("50.00")
    assert data["supports_internal_delivery"] is True

    # 2. Free delivery threshold met (order_amount >= 1000.00)
    resp_free = await client.post(
        "/api/v1/delivery/serviceability/check",
        json={"tenant_id": str(tenant_a_id), "pincode": "585401", "order_amount": "1200.00"},
    )
    assert resp_free.status_code == 200
    assert Decimal(resp_free.json()["delivery_fee"]) == Decimal("0.00")

    # 3. Delivery charge override for PIN 585402
    resp_override = await client.post(
        "/api/v1/delivery/serviceability/check",
        json={"tenant_id": str(tenant_a_id), "pincode": "585402", "order_amount": "300.00"},
    )
    assert resp_override.status_code == 200
    assert Decimal(resp_override.json()["delivery_fee"]) == Decimal("30.00")

    # 4. Unserviceable PIN code
    resp_unserv = await client.post(
        "/api/v1/delivery/serviceability/check",
        json={"tenant_id": str(tenant_a_id), "pincode": "560001"},
    )
    assert resp_unserv.status_code == 200
    assert resp_unserv.json()["serviceable"] is False

    # 5. Zone duplicate code rejection
    resp_dup = await client.post(
        "/api/v1/merchant/delivery/zones",
        json={"code": "BIDAR_URBAN", "name": "Duplicate Urban Zone"},
        headers=merchant_a_headers,
    )
    assert resp_dup.status_code == 409


# =============================================================================
# 2. Delivery Personnel & Vehicle Capacity Tests
# =============================================================================
@pytest.mark.asyncio
async def test_personnel_duty_status_and_vehicle_capacity(
    client: AsyncClient, setup_delivery_ecosystem
):
    eco = setup_delivery_ecosystem
    merchant_a_headers = eco["merchant_a_headers"]
    staff_headers = eco["delivery_staff_headers"]

    # 1. Staff queries profile
    prof_resp = await client.get("/api/v1/delivery-staff/me/profile", headers=staff_headers)
    assert prof_resp.status_code == 200
    assert prof_resp.json()["employee_code"] == "DEL-001"
    assert prof_resp.json()["duty_status"] == "AVAILABLE"

    # 2. Staff updates duty status to OFFLINE
    duty_resp = await client.put(
        "/api/v1/delivery-staff/me/duty-status",
        json={
            "duty_status": "OFFLINE",
            "current_latitude": "17.9104",
            "current_longitude": "77.5199",
        },
        headers=staff_headers,
    )
    assert duty_resp.status_code == 200
    assert duty_resp.json()["duty_status"] == "OFFLINE"

    # 3. Duplicate vehicle registration rejection
    dup_veh = await client.post(
        "/api/v1/merchant/delivery/vehicles",
        json={
            "vehicle_type": "SCOOTER",
            "registration_number": "KA-38-E-1001",
            "max_weight_capacity_kg": "15.00",
        },
        headers=merchant_a_headers,
    )
    assert dup_veh.status_code == 409

    # Re-enable staff to AVAILABLE
    await client.put(
        "/api/v1/delivery-staff/me/duty-status",
        json={"duty_status": "AVAILABLE"},
        headers=staff_headers,
    )


# =============================================================================
# 3. Third-Party Courier Adapter Integration Contract Tests
# =============================================================================
@pytest.mark.asyncio
async def test_courier_adapter_booking_and_contracts(client: AsyncClient, setup_delivery_ecosystem):
    eco = setup_delivery_ecosystem
    store_a_id = eco["store_a_id"]
    variant_id = eco["variant_id"]
    merchant_a_headers = eco["merchant_a_headers"]
    cust1_headers = eco["customer_1_headers"]

    # 1. Place and pay order
    order = await _create_test_order(
        client, cust1_headers, store_a_id, variant_id, quantity=1, payment_method="online"
    )
    order_id = UUID(order["id"])
    await _pay_order_online(client, cust1_headers, str(order_id), Decimal(order["total_amount"]))

    # 2. Create Shipment from Order
    shipment_resp = await client.post(
        "/api/v1/merchant/delivery/shipments",
        json={"order_id": str(order_id), "delivery_type": "COURIER", "total_weight_kg": "2.50"},
        headers=merchant_a_headers,
    )
    assert shipment_resp.status_code == 201
    shipment_id = UUID(shipment_resp.json()["id"])
    assert shipment_resp.json()["status"] == "PENDING_ASSIGNMENT"

    # 3. Book Courier with Mock Adapter
    book_resp = await client.post(
        f"/api/v1/merchant/delivery/shipments/{shipment_id}/book-courier",
        json={"courier_provider": "mock"},
        headers=merchant_a_headers,
    )
    assert book_resp.status_code == 200
    ship_data = book_resp.json()
    assert ship_data["status"] == "ASSIGNED"
    assert ship_data["courier_provider"] == "mock"
    assert ship_data["courier_awb"].startswith("MOCK-AWB-")
    assert ship_data["courier_label_url"].endswith(".pdf")

    # 4. Check Tracking Checkpoints from Courier
    tracking_resp = await client.get(
        f"/api/v1/merchant/delivery/shipments/{shipment_id}/tracking-history",
        headers=merchant_a_headers,
    )
    assert tracking_resp.status_code == 200
    events = tracking_resp.json()["tracking_events"]
    assert len(events) >= 2


# =============================================================================
# 4. Full Internal Fleet Lifecycle & Inventory Dispatch Tests
# =============================================================================
@pytest.mark.asyncio
async def test_internal_shipment_lifecycle_and_inventory_dispatch(
    client: AsyncClient, setup_delivery_ecosystem
):
    eco = setup_delivery_ecosystem
    tenant_a_id = eco["tenant_a_id"]
    store_a_id = eco["store_a_id"]
    variant_id = eco["variant_id"]
    merchant_a_headers = eco["merchant_a_headers"]
    cust1_headers = eco["customer_1_headers"]
    staff_headers = eco["delivery_staff_headers"]
    personnel_id = eco["personnel_id"]
    vehicle_id = eco["vehicle_id"]

    # 1. Place and Confirm Order
    order = await _create_test_order(
        client, cust1_headers, store_a_id, variant_id, quantity=2, payment_method="online"
    )
    order_id = UUID(order["id"])
    await _pay_order_online(client, cust1_headers, str(order_id), Decimal(order["total_amount"]))

    # 2. Create Shipment
    shipment_resp = await client.post(
        "/api/v1/merchant/delivery/shipments",
        json={"order_id": str(order_id), "delivery_type": "INTERNAL", "total_weight_kg": "4.00"},
        headers=merchant_a_headers,
    )
    shipment_id = UUID(shipment_resp.json()["id"])

    # 3. Assign internal delivery personnel
    assign_resp = await client.post(
        f"/api/v1/merchant/delivery/shipments/{shipment_id}/assign-internal",
        json={"personnel_id": str(personnel_id), "vehicle_id": str(vehicle_id)},
        headers=merchant_a_headers,
    )
    assert assign_resp.status_code == 200
    assert assign_resp.json()["status"] == "ASSIGNED"
    assert assign_resp.json()["assigned_personnel_id"] == str(personnel_id)

    # 4. Delivery staff picks up shipment -> Triggers Phase 4 Inventory Dispatch!
    pickup_resp = await client.post(
        f"/api/v1/delivery-staff/shipments/{shipment_id}/pickup",
        headers=staff_headers,
    )
    assert pickup_resp.status_code == 200
    assert pickup_resp.json()["status"] == "PICKED_UP"

    # Verify Order transitioned to DISPATCHED
    async with engine.connect() as conn:
        res = await conn.execute(
            select(Order.status, Order.fulfillment_status).where(Order.id == order_id)
        )
        order_status, order_fulf = res.one()
        assert order_status == "DISPATCHED"
        assert order_fulf == "fulfilled"

    # 5. Delivery staff marks OUT_FOR_DELIVERY -> Generates Delivery OTP
    ofd_resp = await client.post(
        f"/api/v1/delivery-staff/shipments/{shipment_id}/out-for-delivery",
        headers=staff_headers,
    )
    assert ofd_resp.status_code == 200
    assert ofd_resp.json()["status"] == "OUT_FOR_DELIVERY"

    # Verify OTP was saved on shipment and sent via Notification Outbox
    async with engine.connect() as conn:
        otp = (
            await conn.execute(select(Shipment.delivery_otp).where(Shipment.id == shipment_id))
        ).scalar_one()
        assert otp is not None

        outbox_payload = (
            await conn.execute(
                select(NotificationOutbox.payload).where(
                    NotificationOutbox.tenant_id == tenant_a_id,
                    NotificationOutbox.event_type == "shipment.out_for_delivery",
                    NotificationOutbox.aggregate_id == str(shipment_id),
                )
            )
        ).scalar_one()
        assert outbox_payload["delivery_otp"] == otp

    # 6. Attempt delivery with invalid OTP fails
    bad_otp_resp = await client.post(
        f"/api/v1/delivery-staff/shipments/{shipment_id}/deliver",
        json={
            "recipient_name": "Ramesh Kumar",
            "recipient_phone": "+919999900001",
            "delivery_otp": "000000",
        },
        headers=staff_headers,
    )
    assert bad_otp_resp.status_code == 400
    assert bad_otp_resp.json()["code"] == "INVALID_DELIVERY_OTP"

    # 7. Complete delivery with valid OTP -> Creates POD and marks order DELIVERED
    good_deliv_resp = await client.post(
        f"/api/v1/delivery-staff/shipments/{shipment_id}/deliver",
        json={
            "recipient_name": "Ramesh Kumar",
            "recipient_phone": "+919999900001",
            "relationship_to_customer": "SELF",
            "delivery_otp": otp,
            "signature_url": "https://storage.internal/signatures/sig_123.png",
        },
        headers=staff_headers,
    )
    assert good_deliv_resp.status_code == 200
    assert good_deliv_resp.json()["delivery_otp_verified"] is True

    # Verify shipment is DELIVERED and order is DELIVERED
    async with engine.connect() as conn:
        ship_status, delivered_at = (
            await conn.execute(
                select(Shipment.status, Shipment.delivered_at).where(Shipment.id == shipment_id)
            )
        ).one()
        assert ship_status == "DELIVERED"
        assert delivered_at is not None

        order_status = (
            await conn.execute(select(Order.status).where(Order.id == order_id))
        ).scalar_one()
        assert order_status == "DELIVERED"

        # Check ProofOfDelivery
        pod_recipient, pod_otp_verified = (
            await conn.execute(
                select(ProofOfDelivery.recipient_name, ProofOfDelivery.delivery_otp_verified).where(
                    ProofOfDelivery.shipment_id == shipment_id
                )
            )
        ).one()
        assert pod_recipient == "Ramesh Kumar"
        assert pod_otp_verified is True


# =============================================================================
# 5. Cash on Delivery (COD) Integration Tests
# =============================================================================
@pytest.mark.asyncio
async def test_cod_delivery_and_settlement_integration(
    client: AsyncClient, setup_delivery_ecosystem
):
    eco = setup_delivery_ecosystem
    store_a_id = eco["store_a_id"]
    variant_id = eco["variant_id"]
    merchant_a_headers = eco["merchant_a_headers"]
    cust1_headers = eco["customer_1_headers"]
    staff_headers = eco["delivery_staff_headers"]
    personnel_id = eco["personnel_id"]

    # 1. Place COD order
    order = await _create_test_order(
        client, cust1_headers, store_a_id, variant_id, quantity=1, payment_method="cod"
    )
    order_id = UUID(order["id"])
    assert order["status"] == "CONFIRMED"
    assert order["payment_status"] == "pending"

    # 2. Create COD Shipment
    shipment_resp = await client.post(
        "/api/v1/merchant/delivery/shipments",
        json={"order_id": str(order_id), "delivery_type": "INTERNAL"},
        headers=merchant_a_headers,
    )
    shipment_id = UUID(shipment_resp.json()["id"])
    assert shipment_resp.json()["is_cod"] is True
    assert Decimal(shipment_resp.json()["cod_amount"]) > Decimal("0.00")

    # 3. Assign, Pickup, Out for Delivery
    await client.post(
        f"/api/v1/merchant/delivery/shipments/{shipment_id}/assign-internal",
        json={"personnel_id": str(personnel_id)},
        headers=merchant_a_headers,
    )
    await client.post(
        f"/api/v1/delivery-staff/shipments/{shipment_id}/pickup", headers=staff_headers
    )
    await client.post(
        f"/api/v1/delivery-staff/shipments/{shipment_id}/out-for-delivery", headers=staff_headers
    )

    # Get OTP
    async with engine.connect() as conn:
        otp = (
            await conn.execute(select(Shipment.delivery_otp).where(Shipment.id == shipment_id))
        ).scalar_one()

    # 4. Deliver and collect cash
    deliv_resp = await client.post(
        f"/api/v1/delivery-staff/shipments/{shipment_id}/deliver",
        json={
            "recipient_name": "Ramesh Kumar",
            "recipient_phone": "+919999900001",
            "relationship_to_customer": "SELF",
            "delivery_otp": otp,
        },
        headers=staff_headers,
    )
    assert deliv_resp.status_code == 200

    # 5. Verify COD Settlement was created in Phase 7 Payment Architecture
    async with engine.connect() as conn:
        collected_by, amount_col, cod_st = (
            await conn.execute(
                select(
                    CodSettlement.collected_by_name,
                    CodSettlement.amount_collected,
                    CodSettlement.settlement_status,
                ).where(CodSettlement.order_id == order_id)
            )
        ).one()
        assert collected_by == "Anand Kumar"
        assert amount_col == Decimal(shipment_resp.json()["cod_amount"])
        assert cod_st == "pending_deposit"

        ord_pay_status = (
            await conn.execute(select(Order.payment_status).where(Order.id == order_id))
        ).scalar_one()
        assert ord_pay_status == "captured"


# =============================================================================
# 6. Failed Delivery Attempts & Auto-RTO Tests
# =============================================================================
@pytest.mark.asyncio
async def test_failed_delivery_attempts_and_auto_rto(client: AsyncClient, setup_delivery_ecosystem):
    eco = setup_delivery_ecosystem
    store_a_id = eco["store_a_id"]
    variant_id = eco["variant_id"]
    merchant_a_headers = eco["merchant_a_headers"]
    cust1_headers = eco["customer_1_headers"]
    staff_headers = eco["delivery_staff_headers"]
    personnel_id = eco["personnel_id"]

    # 1. Place and Confirm Order
    order = await _create_test_order(
        client, cust1_headers, store_a_id, variant_id, quantity=1, payment_method="online"
    )
    order_id = UUID(order["id"])
    await _pay_order_online(client, cust1_headers, str(order_id), Decimal(order["total_amount"]))

    # 2. Create and Dispatch Shipment
    ship_resp = await client.post(
        "/api/v1/merchant/delivery/shipments",
        json={"order_id": str(order_id), "delivery_type": "INTERNAL"},
        headers=merchant_a_headers,
    )
    shipment_id = UUID(ship_resp.json()["id"])
    await client.post(
        f"/api/v1/merchant/delivery/shipments/{shipment_id}/assign-internal",
        json={"personnel_id": str(personnel_id)},
        headers=merchant_a_headers,
    )
    await client.post(
        f"/api/v1/delivery-staff/shipments/{shipment_id}/pickup", headers=staff_headers
    )
    await client.post(
        f"/api/v1/delivery-staff/shipments/{shipment_id}/out-for-delivery", headers=staff_headers
    )

    # 3. Attempt 1 Failed
    tomorrow = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    fail1 = await client.post(
        f"/api/v1/delivery-staff/shipments/{shipment_id}/fail-attempt",
        json={"reason": "CUSTOMER_UNAVAILABLE", "next_attempt_date": tomorrow},
        headers=staff_headers,
    )
    assert fail1.status_code == 200
    assert fail1.json()["status"] == "FAILED_ATTEMPT"
    assert fail1.json()["attempt_count"] == 1

    # 4. Out for delivery again & Attempt 2 Failed
    await client.post(
        f"/api/v1/delivery-staff/shipments/{shipment_id}/out-for-delivery", headers=staff_headers
    )
    fail2 = await client.post(
        f"/api/v1/delivery-staff/shipments/{shipment_id}/fail-attempt",
        json={"reason": "UNREACHABLE", "next_attempt_date": tomorrow},
        headers=staff_headers,
    )
    assert fail2.status_code == 200
    assert fail2.json()["attempt_count"] == 2

    # 5. Out for delivery again & Attempt 3 Failed -> Exceeds max 3 attempts -> Auto-RTO!
    await client.post(
        f"/api/v1/delivery-staff/shipments/{shipment_id}/out-for-delivery", headers=staff_headers
    )
    fail3 = await client.post(
        f"/api/v1/delivery-staff/shipments/{shipment_id}/fail-attempt",
        json={"reason": "CUSTOMER_UNAVAILABLE"},
        headers=staff_headers,
    )
    assert fail3.status_code == 200
    assert fail3.json()["status"] == "RETURNED_TO_STORE"

    # Verify Order was restocked and marked RETURNED in Phase 4 / Phase 5
    async with engine.connect() as conn:
        order_st = (
            await conn.execute(select(Order.status).where(Order.id == order_id))
        ).scalar_one()
        assert order_st == "RETURNED"

        # Verify staff duty status was freed back to AVAILABLE
        staff_duty = (
            await conn.execute(
                select(DeliveryPersonnel.duty_status).where(DeliveryPersonnel.id == personnel_id)
            )
        ).scalar_one()
        assert staff_duty == "AVAILABLE"


# =============================================================================
# 7. Customer Rejection Immediate RTO Test
# =============================================================================
@pytest.mark.asyncio
async def test_customer_doorstep_rejection_triggers_immediate_rto(
    client: AsyncClient, setup_delivery_ecosystem
):
    eco = setup_delivery_ecosystem
    store_a_id = eco["store_a_id"]
    variant_id = eco["variant_id"]
    merchant_a_headers = eco["merchant_a_headers"]
    cust1_headers = eco["customer_1_headers"]
    staff_headers = eco["delivery_staff_headers"]
    personnel_id = eco["personnel_id"]

    order = await _create_test_order(
        client, cust1_headers, store_a_id, variant_id, quantity=1, payment_method="cod"
    )
    order_id = UUID(order["id"])
    ship_resp = await client.post(
        "/api/v1/merchant/delivery/shipments",
        json={"order_id": str(order_id), "delivery_type": "INTERNAL"},
        headers=merchant_a_headers,
    )
    shipment_id = UUID(ship_resp.json()["id"])
    await client.post(
        f"/api/v1/merchant/delivery/shipments/{shipment_id}/assign-internal",
        json={"personnel_id": str(personnel_id)},
        headers=merchant_a_headers,
    )
    await client.post(
        f"/api/v1/delivery-staff/shipments/{shipment_id}/pickup", headers=staff_headers
    )
    await client.post(
        f"/api/v1/delivery-staff/shipments/{shipment_id}/out-for-delivery", headers=staff_headers
    )

    # Customer rejects package at doorstep
    reject_resp = await client.post(
        f"/api/v1/delivery-staff/shipments/{shipment_id}/fail-attempt",
        json={"reason": "CUSTOMER_REJECTED", "notes": "Customer refused to accept parcel"},
        headers=staff_headers,
    )
    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "RETURNED_TO_STORE"


# =============================================================================
# 8. Courier Webhook Signature Verification & Idempotency Tests
# =============================================================================
@pytest.mark.asyncio
async def test_courier_webhook_verification_and_idempotency(
    client: AsyncClient, setup_delivery_ecosystem
):
    eco = setup_delivery_ecosystem
    store_a_id = eco["store_a_id"]
    variant_id = eco["variant_id"]
    merchant_a_headers = eco["merchant_a_headers"]
    cust1_headers = eco["customer_1_headers"]

    # Book courier shipment
    order = await _create_test_order(
        client, cust1_headers, store_a_id, variant_id, quantity=1, payment_method="online"
    )
    order_id = UUID(order["id"])
    await _pay_order_online(client, cust1_headers, str(order_id), Decimal(order["total_amount"]))
    ship_resp = await client.post(
        "/api/v1/merchant/delivery/shipments",
        json={"order_id": str(order_id), "delivery_type": "COURIER"},
        headers=merchant_a_headers,
    )
    shipment_id = UUID(ship_resp.json()["id"])
    book_resp = await client.post(
        f"/api/v1/merchant/delivery/shipments/{shipment_id}/book-courier",
        json={"courier_provider": "mock"},
        headers=merchant_a_headers,
    )
    awb = book_resp.json()["courier_awb"]

    # 1. Invalid signature rejected
    mock_provider = MockCourierProvider()
    payload = {
        "event_id": "evt_webhook_001",
        "awb": awb,
        "status": "IN_TRANSIT",
        "location": "Hyderabad Hub",
        "description": "Package reached transit hub",
    }
    payload_bytes = json.dumps(payload).encode("utf-8")

    bad_sig_resp = await client.post(
        "/api/v1/delivery/webhooks/mock",
        content=payload_bytes,
        headers={"x-courier-signature": "invalid_sig", "Content-Type": "application/json"},
    )
    assert bad_sig_resp.status_code == 401

    # 2. Valid signature accepted and processed
    valid_sig = mock_provider.compute_signature(payload_bytes)
    ok_resp = await client.post(
        "/api/v1/delivery/webhooks/mock",
        content=payload_bytes,
        headers={"x-courier-signature": valid_sig, "Content-Type": "application/json"},
    )
    assert ok_resp.status_code == 200
    assert ok_resp.json()["status"] == "processed"
    assert ok_resp.json()["new_status"] == "IN_TRANSIT"

    # 3. Duplicate webhook event is idempotent
    dup_resp = await client.post(
        "/api/v1/delivery/webhooks/mock",
        content=payload_bytes,
        headers={"x-courier-signature": valid_sig, "Content-Type": "application/json"},
    )
    assert dup_resp.status_code == 200
    assert dup_resp.json()["status"] == "idempotent_duplicate"

    # Verify only 1 tracking event exists with evt_webhook_001
    async with engine.connect() as conn:
        count = (
            await conn.execute(
                select(DeliveryTrackingEvent).where(
                    DeliveryTrackingEvent.idempotency_key == "evt_webhook_001"
                )
            )
        ).fetchall()
        assert len(count) == 1


# =============================================================================
# 9. Customer Ownership & Cross-Tenant Isolation Tests
# =============================================================================
@pytest.mark.asyncio
async def test_customer_isolation_and_cross_tenant_denial(
    client: AsyncClient, setup_delivery_ecosystem
):
    eco = setup_delivery_ecosystem
    store_a_id = eco["store_a_id"]
    variant_id = eco["variant_id"]
    merchant_a_headers = eco["merchant_a_headers"]
    merchant_b_headers = eco["merchant_b_headers"]
    cust1_headers = eco["customer_1_headers"]
    cust2_headers = eco["customer_2_headers"]

    # Customer 1 creates an order and shipment
    order = await _create_test_order(
        client, cust1_headers, store_a_id, variant_id, quantity=1, payment_method="online"
    )
    order_id = UUID(order["id"])
    await _pay_order_online(client, cust1_headers, str(order_id), Decimal(order["total_amount"]))
    ship_resp = await client.post(
        "/api/v1/merchant/delivery/shipments",
        json={"order_id": str(order_id), "delivery_type": "INTERNAL"},
        headers=merchant_a_headers,
    )
    shipment_id = UUID(ship_resp.json()["id"])

    # 1. Customer 1 can track own shipment
    track_ok = await client.get(
        f"/api/v1/customer/delivery/shipments/{shipment_id}/track", headers=cust1_headers
    )
    assert track_ok.status_code == 200
    assert track_ok.json()["shipment_id"] == str(shipment_id)

    # 2. Customer 2 cannot track Customer 1's shipment
    track_forbidden = await client.get(
        f"/api/v1/customer/delivery/shipments/{shipment_id}/track", headers=cust2_headers
    )
    assert track_forbidden.status_code == 404

    # 3. Merchant B cannot access Tenant A's shipment
    merch_b_access = await client.get(
        f"/api/v1/merchant/delivery/shipments/{shipment_id}", headers=merchant_b_headers
    )
    assert merch_b_access.status_code == 404

    # 4. Merchant B cannot list Tenant A's delivery zones
    zones_b = await client.get("/api/v1/merchant/delivery/zones", headers=merchant_b_headers)
    assert zones_b.status_code == 200
    assert len(zones_b.json()) == 0


# =============================================================================
# 10. Operational Dashboard Metrics Test
# =============================================================================
@pytest.mark.asyncio
async def test_merchant_dashboard_metrics(client: AsyncClient, setup_delivery_ecosystem):
    eco = setup_delivery_ecosystem
    merchant_a_headers = eco["merchant_a_headers"]

    dash_resp = await client.get("/api/v1/merchant/delivery/dashboard", headers=merchant_a_headers)
    assert dash_resp.status_code == 200
    metrics = dash_resp.json()
    assert "total_shipments" in metrics
    assert "pending_assignment_count" in metrics
    assert "active_riders_count" in metrics
    assert metrics["active_riders_count"] >= 1
