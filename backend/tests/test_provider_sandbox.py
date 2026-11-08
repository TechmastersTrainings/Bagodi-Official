import json
from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.modules.delivery.providers.base import CourierBookingRequest
from app.modules.delivery.providers.shiprocket_provider import ShiprocketCourierProvider
from app.modules.notifications.providers.twilio_provider import TwilioNotificationProvider
from app.modules.payments.providers.razorpay_provider import RazorpayPaymentGatewayProvider


# =============================================================================
# 1. Razorpay Payment Gateway Sandbox Tests
# =============================================================================
@pytest.mark.asyncio
async def test_razorpay_sandbox_payment_initiation_and_verification():
    provider = RazorpayPaymentGatewayProvider(
        key_id="rzp_test_bagodi_sandbox_key_001",
        key_secret="rzp_test_secret_32char_key_bagodi",
        webhook_secret="rzp_whsec_32char_key_bagodi",
        is_sandbox=True,
    )

    tenant_id = uuid4()
    transaction_id = uuid4()
    amount = Decimal("2499.00")

    # 1. Initiate Payment
    init_res = await provider.initiate_payment(
        tenant_id=tenant_id,
        transaction_id=transaction_id,
        order_number="ORD-BGD-001",
        amount=amount,
        customer_info={
            "name": "Anita Rao",
            "email": "anita@example.com",
            "contact": "+919876543210",
        },
    )
    assert init_res.status == "initiated"
    assert init_res.gateway_order_id.startswith("order_rzp_")
    assert init_res.checkout_payload["amount"] == 249900

    # 2. Cryptographic Verification (HMAC-SHA256)
    gw_payment_id = "pay_rzp_test_12345"
    valid_sig = provider.generate_payment_signature(init_res.gateway_order_id, gw_payment_id)

    verify_res = await provider.verify_payment(
        tenant_id=tenant_id,
        gateway_order_id=init_res.gateway_order_id,
        gateway_payment_id=gw_payment_id,
        gateway_signature=valid_sig,
        amount=amount,
    )
    assert verify_res.is_valid is True
    assert verify_res.status == "captured"
    assert verify_res.fee > Decimal("0.00")

    # 3. Forged Signature Verification Failure
    bad_verify = await provider.verify_payment(
        tenant_id=tenant_id,
        gateway_order_id=init_res.gateway_order_id,
        gateway_payment_id=gw_payment_id,
        gateway_signature="forged_signature_hex_value",
        amount=amount,
    )
    assert bad_verify.is_valid is False
    assert bad_verify.status == "failed"

    # 4. Webhook Signature Verification and Processing
    webhook_body = json.dumps(
        {
            "event": "payment.captured",
            "account_id": "acc_rzp_01",
            "payload": {
                "payment": {
                    "entity": {
                        "id": gw_payment_id,
                        "order_id": init_res.gateway_order_id,
                        "amount": 249900,
                        "fee": 4998,
                        "tax": 899,
                    }
                }
            },
        }
    ).encode("utf-8")

    wh_sig = provider.generate_webhook_signature(webhook_body)
    wh_res = await provider.process_webhook(
        raw_body=webhook_body,
        headers={"X-Razorpay-Signature": wh_sig},
    )
    assert wh_res.is_valid is True
    assert wh_res.event_type == "payment.captured"
    assert wh_res.amount == Decimal("2499.00")

    # 5. Refund in Sandbox
    refund_res = await provider.process_refund(
        tenant_id=tenant_id,
        transaction_id=transaction_id,
        gateway_payment_id=gw_payment_id,
        amount=amount,
        reason="Customer cancellation",
    )
    assert refund_res.is_valid is True
    assert refund_res.status == "succeeded"
    assert refund_res.gateway_refund_id.startswith("rfnd_rzp_")


# =============================================================================
# 2. Twilio Communication Sandbox Tests
# =============================================================================
@pytest.mark.asyncio
async def test_twilio_sandbox_sms_whatsapp_and_dlr():
    provider = TwilioNotificationProvider(
        account_sid="AC_test_bagodi_sandbox_account_sid_001",
        auth_token="auth_token_32char_key_bagodi_sandbox",
        from_number="+15005550006",
        is_sandbox=True,
    )

    tenant_id = uuid4()

    # 1. Send SMS
    sms_res = await provider.send_sms(
        tenant_id=tenant_id,
        recipient_phone="+919876543210",
        message="Your Bagodi order #ORD-001 has been confirmed!",
    )
    assert sms_res.success is True
    assert sms_res.provider_message_id.startswith("SM_test_")
    assert sms_res.status == "sent"

    # 2. Send WhatsApp
    wa_res = await provider.send_whatsapp(
        tenant_id=tenant_id,
        recipient_phone="+919876543210",
        template_name="order_confirmation",
    )
    assert wa_res.success is True
    assert wa_res.provider_message_id.startswith("WA_test_")
    assert wa_res.status == "sent"

    # 3. Status Callback (DLR)
    dlr_body = b"MessageSid=SM_test_12345678&MessageStatus=delivered"
    dlr_res = await provider.parse_delivery_report(raw_body=dlr_body, headers={})
    assert dlr_res.is_valid is True
    assert dlr_res.status == "delivered"
    assert dlr_res.provider_message_id == "SM_test_12345678"


# =============================================================================
# 3. Shiprocket Courier Logistics Sandbox Tests
# =============================================================================
@pytest.mark.asyncio
async def test_shiprocket_sandbox_booking_tracking_label():
    provider = ShiprocketCourierProvider(
        email="sandbox@bagodi.internal",
        password="sandbox_password",
        api_key="sr_whsec_32char_key_bagodi",
        is_sandbox=True,
    )

    req = CourierBookingRequest(
        shipment_id=uuid4(),
        shipment_number="SHP-BGD-001",
        tenant_id=uuid4(),
        store_id=uuid4(),
        recipient_name="Deepa Patil",
        recipient_phone="+919876543210",
        shipping_address={
            "address_line1": "Near Bidar Fort",
            "city": "Bidar",
            "state": "Karnataka",
            "postal_code": "585401",
        },
        total_weight_kg=Decimal("1.50"),
        is_cod=False,
    )

    # 1. Book Shipment
    book_res = await provider.book_shipment(req)
    assert book_res.success is True
    assert book_res.tracking_number.startswith("SRSHPBGD")
    assert "Shiprocket" in book_res.courier_partner

    # 2. Tracking Checkpoints
    track_res = await provider.track_shipment(book_res.tracking_number)
    assert track_res.current_status == "IN_TRANSIT"
    assert len(track_res.checkpoints) >= 2

    # 3. Shipping Label
    label_res = await provider.generate_label(book_res.tracking_number)
    assert label_res.file_format == "pdf"

    # 4. Cancel Shipment
    cancel_res = await provider.cancel_shipment(book_res.tracking_number)
    assert cancel_res.success is True


# =============================================================================
# 4. Production Hardening Configuration Guard Tests
# =============================================================================
def test_production_configuration_guard_blocks_insecure_defaults():
    """
    Mandatory Requirement 16:
    Verify that no development credentials, mock providers or dummy data
    are accidentally enabled in production configuration.
    """
    # 1. Insecure default secrets in production MUST raise ValueError
    insecure_settings = Settings(
        database_url="postgresql+asyncpg://bagodi:secret@localhost:5432/bagodi",
        app_env="production",
        jwt_secret_key="BAGODI_DEV_INSECURE_SECRET_KEY_REPLACE_IN_PRODUCTION_32CHARS",
        payment_gateway_provider="mock",
        notification_default_provider="mock",
    )

    with pytest.raises(ValueError) as excinfo:
        insecure_settings.validate_production_configuration()

    err = str(excinfo.value)
    assert "CRITICAL PRODUCTION CONFIGURATION VIOLATION" in err
    assert "jwt_secret_key" in err
    assert "payment_gateway_provider cannot be 'mock'" in err
    assert "notification_default_provider cannot be 'mock'" in err

    # 2. Secure production configuration passes cleanly
    secure_settings = Settings(
        database_url="postgresql+asyncpg://bagodi:secret@localhost:5432/bagodi",
        app_env="production",
        jwt_secret_key="9f8b2c4e1a7d3f6e8b0c2a4e6f8d0b2c4e6a8d0b2c4e6f8a0c2e4f6a8b0d2e4f",
        payment_gateway_provider="razorpay",
        payment_mock_secret="prod_sec_payment_webhook_secret_key_prod_32chars",
        payment_webhook_secret="prod_sec_payment_webhook_secret_key_prod_32chars",
        notification_default_provider="twilio",
        notification_webhook_secret="prod_sec_notif_webhook_secret_key_prod_32chars",
        otp_provider="twilio",
        debug=False,
    )
    # Should not raise any error
    secure_settings.validate_production_configuration()
