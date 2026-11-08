# Phase 11: Provider Sandbox Integration Report

---

## 1. Executive Summary

Mandatory Requirement 15 requires testing real provider integrations using sandbox environments across three critical external dependencies:
1. **Payment Gateway:** Razorpay
2. **Customer Communications:** Twilio (SMS & WhatsApp)
3. **Logistics & Courier Delivery:** Shiprocket

All three adapters were implemented, registered in their respective domain factories, and verified with automated test suites in `backend/tests/test_provider_sandbox.py`.

In addition, an automated production configuration guard (`Settings.validate_production_configuration()`) was implemented to prevent mock providers or sandbox credentials from ever starting in production environments.

---

## 2. Implemented Sandbox Adapters

### 2.1 Razorpay Payment Gateway Adapter (`RazorpayPaymentGatewayProvider`)
- **Module Location:** `backend/app/modules/payments/providers/razorpay_provider.py`
- **Factory Registration:** Registered as `"razorpay"` in `PaymentGatewayFactory`.
- **API Capabilities Implemented:**
  - `initiate_payment`: Generates authentic Razorpay order requests (`amount` in paise, `currency="INR"`, `receipt`, `notes`).
  - `verify_payment`: Computes cryptographic HMAC-SHA256 signature (`hmac.new(key_secret, f"{order_id}|{payment_id}", sha256)`).
  - `verify_webhook_signature`: Verifies incoming webhook authenticity via `X-Razorpay-Signature`.
  - `process_webhook`: Extracts payment capture events, amounts, gateway fees, and taxes.
  - `process_refund`: Initiates full or partial refunds via `/payments/{payment_id}/refund`.
- **Sandbox Test Verification:**
  - Verified in `test_razorpay_sandbox_payment_initiation_and_verification`: order creation, signature match, signature forgery rejection, webhook processing, and sandbox refund.

### 2.2 Twilio Communications Adapter (`TwilioNotificationProvider`)
- **Module Location:** `backend/app/modules/notifications/providers/twilio_provider.py`
- **Factory Registration:** Registered as `"twilio"` in `NotificationProviderFactory`.
- **API Capabilities Implemented:**
  - `send_sms`: Dispatches transactional SMS via Twilio Messages API (`POST /2010-04-01/Accounts/{AccountSid}/Messages.json`).
  - `send_whatsapp`: Dispatches templated WhatsApp messages via `whatsapp:{to}` and `whatsapp:{from}`.
  - `parse_delivery_report`: Parses Twilio Delivery Status Callbacks (DLR) and normalizes `delivered`, `undelivered`, `failed`, `sent`.
- **Sandbox Test Verification:**
  - Verified in `test_twilio_sandbox_sms_whatsapp_and_dlr`: SMS dispatch, WhatsApp dispatch, and status callback parsing.

### 2.3 Shiprocket Logistics Adapter (`ShiprocketCourierProvider`)
- **Module Location:** `backend/app/modules/delivery/providers/shiprocket_provider.py`
- **Factory Registration:** Registered as `"shiprocket"` in `CourierProviderFactory`.
- **API Capabilities Implemented:**
  - `book_shipment`: Creates adhoc courier orders (`POST /orders/create/adhoc`) with dimensions, weight, COD amount, and address details, assigning an Air Waybill (AWB).
  - `track_shipment`: Queries tracking checkpoints (`GET /courier/track/awb/{awb}`) with status mapping (`MANIFESTED`, `IN_TRANSIT`, `OUT_FOR_DELIVERY`, `DELIVERED`, `RETURNED_TO_ORIGIN`).
  - `generate_label`: Generates standard courier PDF shipping labels.
  - `cancel_shipment`: Cancels booked courier shipments before pickup.
  - `parse_webhook_payload`: Normalizes Shiprocket tracking update webhooks.
- **Sandbox Test Verification:**
  - Verified in `test_shiprocket_sandbox_booking_tracking_label`: shipment booking, AWB assignment, tracking checkpoints, and PDF label generation.

---

## 3. Sandbox vs Production Distinction

| Dimension | Sandbox Environment (Verified) | Production Live Environment (Pending Live Credentials) |
| :--- | :--- | :--- |
| **Razorpay** | • Verified with `rzp_test_...` credentials<br>• Real API payload formatting<br>• Authentic HMAC-SHA256 signature verification<br>• Webhook processing and simulated capture | • Requires merchant KYC completion<br>• Active bank account settlement linking<br>• Production API keys (`rzp_live_...`)<br>• Live webhook secret configured in Razorpay Dashboard |
| **Twilio** | • Verified with Twilio test credentials<br>• SMS and WhatsApp request payloads verified<br>• DLR status callback parsing verified | • Requires active Twilio Account SID and Auth Token<br>• DLT registration (India TRAI compliance for SMS)<br>• Approved WhatsApp Business Template approval from Meta |
| **Shiprocket** | • Verified with Shiprocket Sandbox API<br>• Adhoc order creation payload verified<br>• AWB code generation and PDF label verified<br>• Tracking checkpoint mapping verified | • Requires active Shiprocket commercial contract<br>• Configured Bidar warehouse pickup address<br>• Production API user token and wallet recharge |

---

## 4. Production Hardening Guardrails

Mandatory Requirement 16 requires proving that mock providers or development secrets cannot run in production.

- Implemented in `backend/app/core/config.py::validate_production_configuration()`.
- Automatically executed during application startup in `backend/app/main.py::lifespan()`.
- Verified in `backend/tests/test_provider_sandbox.py::test_production_configuration_guard_blocks_insecure_defaults`:
  - Starting in `APP_ENV=production` with `PAYMENT_GATEWAY_PROVIDER=mock` or insecure dev JWT keys raises a fatal startup exception preventing the application from serving requests.
