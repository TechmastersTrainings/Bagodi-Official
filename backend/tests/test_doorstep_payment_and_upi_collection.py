"""
Integration tests for Bagodi Doorstep Delivery Operations, Dynamic UPI QR Collection,
Backend Payment Verification, and TechMasters 2% Platform Commission Ledger.
"""

from decimal import Decimal
from uuid import UUID

import pytest
from httpx import AsyncClient

from tests.test_delivery import _create_test_order, setup_delivery_ecosystem


@pytest.mark.asyncio
async def test_doorstep_upi_qr_generation_and_backend_verification(
    client: AsyncClient, setup_delivery_ecosystem
):
    eco = setup_delivery_ecosystem
    merchant_headers = eco["merchant_a_headers"]
    customer_headers = eco["customer_1_headers"]
    staff_headers = eco["delivery_staff_headers"]
    store_id = eco["store_a_id"]
    variant_id = eco["variant_id"]
    personnel_id = eco["personnel_id"]

    # 1. Customer places order with UPI on Delivery / COD
    order_data = await _create_test_order(
        client,
        customer_headers,
        store_id,
        variant_id,
        quantity=1,
        payment_method="cod",
    )
    order_id = order_data["id"]

    # 2. Merchant creates shipment and assigns internal delivery agent
    shipment_resp = await client.post(
        "/api/v1/merchant/delivery/shipments",
        json={"order_id": order_id, "delivery_type": "INTERNAL"},
        headers=merchant_headers,
    )
    assert shipment_resp.status_code == 201
    shipment_id = shipment_resp.json()["id"]

    assign_resp = await client.post(
        f"/api/v1/merchant/delivery/shipments/{shipment_id}/assign-internal",
        json={"personnel_id": str(personnel_id)},
        headers=merchant_headers,
    )
    assert assign_resp.status_code == 200
    assert assign_resp.json()["status"] == "ASSIGNED"

    # 3. Agent picks up package and marks out for delivery
    pickup_resp = await client.post(
        f"/api/v1/delivery-staff/shipments/{shipment_id}/pickup",
        headers=staff_headers,
    )
    assert pickup_resp.status_code == 200
    assert pickup_resp.json()["status"] == "PICKED_UP"

    out_resp = await client.post(
        f"/api/v1/delivery-staff/shipments/{shipment_id}/out-for-delivery",
        headers=staff_headers,
    )
    assert out_resp.status_code == 200
    assert out_resp.json()["status"] == "OUT_FOR_DELIVERY"

    # 4. Agent checks payment status
    status_resp = await client.get(
        f"/api/v1/delivery-staff/shipments/{shipment_id}/payment-status",
        headers=staff_headers,
    )
    assert status_resp.status_code == 200
    p_status = status_resp.json()
    assert p_status["is_paid"] is False
    assert float(p_status["amount_payable"]) > 0
    # Verify TechMasters 2% commission calculation
    expected_commission = round(float(p_status["amount_payable"]) * 0.02, 2)
    assert float(p_status["techmasters_commission_amount"]) == expected_commission

    # 5. Agent generates dynamic UPI QR code
    qr_resp = await client.post(
        f"/api/v1/delivery-staff/shipments/{shipment_id}/generate-upi-qr",
        headers=staff_headers,
    )
    assert qr_resp.status_code == 200
    qr_data = qr_resp.json()
    assert qr_data["upi_intent_uri"].startswith("upi://pay?")
    assert "<svg" in qr_data["qr_code_svg"]
    assert qr_data["payee_vpa"] == "bagodi.payments@okaxis"
    assert qr_data["transaction_reference"].startswith("TXN-UPI-")

    # 6. Customer can track live shipment with rider and vehicle details
    track_resp = await client.get(
        f"/api/v1/customer/delivery/orders/{order_id}/shipment",
        headers=customer_headers,
    )
    assert track_resp.status_code == 200
    track_data = track_resp.json()
    assert track_data["rider_name"] == "Anand Kumar"
    assert track_data["status"] == "OUT_FOR_DELIVERY"
    assert track_data["delivery_otp"] is not None
    customer_otp = track_data["delivery_otp"]

    # 7. Agent triggers backend verification of UPI payment
    verify_resp = await client.post(
        f"/api/v1/delivery-staff/shipments/{shipment_id}/verify-upi-payment",
        json={"notes": "UPI payment verified via dynamic QR scan"},
        headers=staff_headers,
    )
    assert verify_resp.status_code == 200
    verify_data = verify_resp.json()
    assert verify_data["verified"] is True
    assert verify_data["status"] == "captured"
    assert float(verify_data["techmasters_commission_amount"]) == expected_commission

    # 8. Agent completes delivery with customer OTP
    deliver_resp = await client.post(
        f"/api/v1/delivery-staff/shipments/{shipment_id}/deliver",
        json={
            "recipient_name": "Ramesh Kumar",
            "recipient_phone": "+919999900001",
            "relationship_to_customer": "SELF",
            "delivery_otp": customer_otp,
            "notes": "Delivered in person, verified with OTP and dynamic UPI",
        },
        headers=staff_headers,
    )
    assert deliver_resp.status_code == 200
    assert deliver_resp.json()["delivery_otp_verified"] is True

    # 9. Verify final order & shipment status is DELIVERED
    final_track = await client.get(
        f"/api/v1/customer/delivery/orders/{order_id}/shipment",
        headers=customer_headers,
    )
    assert final_track.json()["status"] == "DELIVERED"
    assert final_track.json()["payment_status"] == "captured"

