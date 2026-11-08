import hashlib
import hmac
import json
from datetime import UTC, datetime
from uuid import uuid4

from app.modules.delivery.providers.base import (
    BaseCourierProvider,
    CourierBookingRequest,
    CourierBookingResult,
    CourierCancelResult,
    CourierLabelResult,
    CourierTrackingCheckpoint,
    CourierTrackingResult,
    CourierWebhookPayload,
)


class MockCourierProvider(BaseCourierProvider):
    """
    Reference mock courier provider for local and automated test environments.
    Guarantees strict contract fulfillment, HMAC signature verification,
    and predictable AWB generation without external network calls.
    """

    DEFAULT_SECRET = "mock_courier_webhook_secret_key"

    def __init__(self, webhook_secret: str = DEFAULT_SECRET):
        self.webhook_secret = webhook_secret

    async def book_shipment(self, request: CourierBookingRequest) -> CourierBookingResult:
        tracking_number = f"MOCK-AWB-{request.shipment_number}-{uuid4().hex[:6].upper()}"
        label_url = f"https://mock-courier.internal/labels/{tracking_number}.pdf"
        return CourierBookingResult(
            success=True,
            tracking_number=tracking_number,
            courier_partner="MockExpress",
            label_url=label_url,
            estimated_delivery_days=2,
            raw_response={"mock_booking_id": str(uuid4()), "awb": tracking_number},
        )

    async def track_shipment(self, tracking_number: str) -> CourierTrackingResult:
        now = datetime.now(UTC)
        checkpoints = [
            CourierTrackingCheckpoint(
                status="PICKED_UP",
                location="Bidar Hub",
                description="Consignment picked up from merchant store",
                timestamp=now,
                checkpoint_id=f"chk_{uuid4().hex[:8]}",
            ),
            CourierTrackingCheckpoint(
                status="IN_TRANSIT",
                location="Regional Sorting Facility",
                description="Arrived at sorting facility",
                timestamp=now,
                checkpoint_id=f"chk_{uuid4().hex[:8]}",
            ),
        ]
        return CourierTrackingResult(
            tracking_number=tracking_number,
            courier_partner="MockExpress",
            current_status="IN_TRANSIT",
            checkpoints=checkpoints,
            raw_response={"awb": tracking_number, "carrier": "MockExpress"},
        )

    async def cancel_shipment(self, tracking_number: str) -> CourierCancelResult:
        return CourierCancelResult(
            success=True,
            tracking_number=tracking_number,
            message="Consignment cancelled successfully with carrier.",
            raw_response={"awb": tracking_number, "status": "CANCELLED"},
        )

    async def generate_label(self, tracking_number: str) -> CourierLabelResult:
        return CourierLabelResult(
            tracking_number=tracking_number,
            label_url=f"https://mock-courier.internal/labels/{tracking_number}.pdf",
            file_format="pdf",
        )

    def verify_webhook_signature(self, raw_body: bytes, headers: dict[str, str]) -> bool:
        signature = headers.get("x-courier-signature") or headers.get("X-Courier-Signature")
        if not signature:
            return False
        expected_sig = hmac.new(
            self.webhook_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected_sig, signature)

    def parse_webhook_payload(
        self, raw_body: bytes, headers: dict[str, str]
    ) -> CourierWebhookPayload:
        data = json.loads(raw_body.decode("utf-8"))
        tracking_number = data.get("tracking_number") or data.get("awb")
        raw_status = data.get("status", "").upper()

        status_mapping = {
            "MANIFESTED": "ASSIGNED",
            "PICKED_UP": "PICKED_UP",
            "IN_TRANSIT": "IN_TRANSIT",
            "OUT_FOR_DELIVERY": "OUT_FOR_DELIVERY",
            "DELIVERED": "DELIVERED",
            "FAILED": "FAILED_ATTEMPT",
            "RTO_INITIATED": "RETURNED_TO_STORE",
            "RETURNED": "RETURNED_TO_STORE",
        }
        normalized_status = status_mapping.get(raw_status, raw_status)
        timestamp_str = data.get("event_timestamp")
        if timestamp_str:
            try:
                event_ts = datetime.fromisoformat(timestamp_str)
            except ValueError:
                event_ts = datetime.now(UTC)
        else:
            event_ts = datetime.now(UTC)

        return CourierWebhookPayload(
            tracking_number=tracking_number,
            status=normalized_status,
            event_timestamp=event_ts,
            location=data.get("location"),
            description=data.get("description", f"Status updated to {normalized_status}"),
            event_id=data.get("event_id") or str(uuid4()),
            raw_payload=data,
        )

    def compute_signature(self, payload_bytes: bytes) -> str:
        """Helper for test suites to construct valid carrier webhook signatures."""
        return hmac.new(
            self.webhook_secret.encode("utf-8"),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()
