import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import get_settings
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


class ShiprocketCourierProvider(BaseCourierProvider):
    """
    Shiprocket Courier Sandbox & Production Adapter.
    Adheres strictly to the BaseCourierProvider interface.
    """

    def __init__(
        self,
        email: str | None = None,
        password: str | None = None,
        api_key: str | None = None,
        base_url: str = "https://apiv2.shiprocket.in/v1/external",
        is_sandbox: bool | None = None,
    ):
        settings = get_settings()
        self.email = (
            email or getattr(settings, "shiprocket_email", None) or "sandbox@bagodi.internal"
        )
        self.password = (
            password or getattr(settings, "shiprocket_password", None) or "sandbox_pass_123"
        )
        self.api_key = (
            api_key
            or getattr(settings, "shiprocket_webhook_secret", None)
            or "sr_whsec_32char_key_bagodi"
        )
        self.api_token = getattr(settings, "shiprocket_api_token", None) or ""
        self._cached_token: str | None = None
        self.base_url = base_url
        if is_sandbox is None:
            self.is_sandbox = settings.app_env.lower() != "production"
        else:
            self.is_sandbox = is_sandbox

    def _is_sandbox_active(self) -> bool:
        return self.is_sandbox and (self.email == "sandbox@bagodi.internal" or not self.email)

    @property
    def provider_name(self) -> str:
        return "shiprocket"

    async def book_shipment(self, request: CourierBookingRequest) -> CourierBookingResult:
        if self._is_sandbox_active():
            awb = f"SR{request.shipment_number.replace('-', '')[:10]}IN"
            return CourierBookingResult(
                success=True,
                tracking_number=awb,
                courier_partner="Shiprocket - Delhivery Air",
                label_url=f"https://shiprocket.co/tracking/label/{awb}",
                estimated_delivery_days=3,
                raw_response={
                    "order_id": str(request.shipment_id),
                    "shipment_id": str(request.shipment_id),
                    "awb_code": awb,
                    "courier_name": "Delhivery Air",
                    "status": "AWB Assigned",
                },
            )

        token = await self._get_auth_token()
        async with httpx.AsyncClient(base_url=self.base_url, timeout=15.0) as client:
            resp = await client.post(
                "/orders/create/adhoc",
                json={
                    "order_id": str(request.shipment_id),
                    "order_date": datetime.now(UTC).strftime("%Y-%m-%d %H:%M"),
                    "billing_customer_name": request.recipient_name,
                    "billing_phone": request.recipient_phone,
                    "weight": float(request.total_weight_kg),
                    "payment_method": "COD" if request.is_cod else "Prepaid",
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            data = resp.json()
            if resp.status_code >= 400:
                return CourierBookingResult(
                    success=False,
                    tracking_number="",
                    courier_partner="Shiprocket",
                    error_message=str(data.get("message")),
                    raw_response=data,
                )
            awb = data.get("awb_code", f"SR{request.shipment_number}IN")
            return CourierBookingResult(
                success=True,
                tracking_number=awb,
                courier_partner=data.get("courier_name", "Shiprocket"),
                label_url=data.get("label_url"),
                raw_response=data,
            )

    async def _get_auth_token(self) -> str:
        if self._cached_token:
            return self._cached_token
        if self.api_token:
            self._cached_token = self.api_token
            return self.api_token
        async with httpx.AsyncClient(base_url=self.base_url, timeout=15.0) as client:
            resp = await client.post(
                "/auth/login",
                json={"email": self.email, "password": self.password},
            )
            data = resp.json()
            if resp.status_code >= 400 or not data.get("token"):
                raise RuntimeError(f"Shiprocket authentication failed: {data}")
            self._cached_token = data["token"]
            return self._cached_token

    async def track_shipment(
        self, tracking_number: str, metadata: dict[str, Any] | None = None
    ) -> CourierTrackingResult:
        if self._is_sandbox_active():
            now = datetime.now(UTC)
            return CourierTrackingResult(
                tracking_number=tracking_number,
                courier_partner="Shiprocket",
                current_status="IN_TRANSIT",
                checkpoints=[
                    CourierTrackingCheckpoint(
                        status="MANIFESTED",
                        location="Bidar Hub",
                        description="Shipment manifested and ready for pickup",
                        timestamp=now,
                    ),
                    CourierTrackingCheckpoint(
                        status="IN_TRANSIT",
                        location="Hub Transit",
                        description="In transit to destination facility",
                        timestamp=now,
                    ),
                ],
                raw_response={"awb": tracking_number, "status": "IN_TRANSIT"},
            )

        token = await self._get_auth_token()
        async with httpx.AsyncClient(base_url=self.base_url, timeout=15.0) as client:
            resp = await client.get(
                f"/courier/track/awb/{tracking_number}",
                headers={"Authorization": f"Bearer {token}"},
            )
            data = resp.json()
            td = data.get("tracking_data", {})
            activities = td.get("shipment_track_activities") or []
            checkpoints = [
                CourierTrackingCheckpoint(
                    status=str(act.get("sr-status-label") or act.get("activity") or "IN_TRANSIT").upper(),
                    location=act.get("location") or "Transit Hub",
                    description=act.get("activity") or "Carrier scan update",
                    timestamp=datetime.now(UTC),
                )
                for act in activities
            ]
            current = "IN_TRANSIT"
            if td.get("shipment_track"):
                current = str(td["shipment_track"][0].get("current_status") or "IN_TRANSIT").upper()
            return CourierTrackingResult(
                tracking_number=tracking_number,
                courier_partner="Shiprocket",
                current_status=current,
                checkpoints=checkpoints,
                raw_response=data,
            )

    async def cancel_shipment(
        self, tracking_number: str, reason: str | None = None
    ) -> CourierCancelResult:
        if self._is_sandbox_active():
            return CourierCancelResult(
                success=True,
                tracking_number=tracking_number,
                message="Shipment cancelled successfully in Shiprocket sandbox",
                raw_response={"awb": tracking_number, "status": "CANCELLED"},
            )

        token = await self._get_auth_token()
        async with httpx.AsyncClient(base_url=self.base_url, timeout=15.0) as client:
            resp = await client.post(
                "/orders/cancel/shipment/awbs",
                json={"awbs": [tracking_number]},
                headers={"Authorization": f"Bearer {token}"},
            )
            data = resp.json()
            return CourierCancelResult(
                success=resp.status_code < 400,
                tracking_number=tracking_number,
                message=str(data.get("message", "Shiprocket cancellation processed")),
                raw_response=data,
            )

    async def generate_label(self, tracking_number: str) -> CourierLabelResult:
        if self._is_sandbox_active():
            return CourierLabelResult(
                tracking_number=tracking_number,
                file_format="pdf",
                label_url=f"https://shiprocket.co/tracking/label/{tracking_number}",
            )
        token = await self._get_auth_token()
        async with httpx.AsyncClient(base_url=self.base_url, timeout=15.0) as client:
            resp = await client.post(
                "/courier/generate/label",
                json={"shipment_id": [tracking_number]},
                headers={"Authorization": f"Bearer {token}"},
            )
            data = resp.json()
            return CourierLabelResult(
                tracking_number=tracking_number,
                file_format="pdf",
                label_url=data.get("label_url"),
            )

    def verify_webhook_signature(self, raw_body: bytes, headers: dict[str, str]) -> bool:
        sig = headers.get("x-shiprocket-signature") or headers.get("X-Api-Key") or headers.get("x-api-key")
        if not sig or not self.api_key:
            return False
        expected = hmac.new(self.api_key.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, sig) or hmac.compare_digest(self.api_key, sig)

    def parse_webhook_payload(
        self, raw_body: bytes, headers: dict[str, str]
    ) -> CourierWebhookPayload:
        payload = json.loads(raw_body.decode("utf-8"))
        awb = payload.get("awb", payload.get("awb_code", "UNKNOWN"))
        raw_status = payload.get("current_status", "IN_TRANSIT").upper()

        status_map = {
            "DELIVERED": "DELIVERED",
            "CANCELED": "CANCELLED",
            "OUT FOR DELIVERY": "OUT_FOR_DELIVERY",
            "RTO INITIATED": "RETURNED_TO_ORIGIN",
            "IN TRANSIT": "IN_TRANSIT",
        }
        normalized = status_map.get(raw_status, "IN_TRANSIT")

        return CourierWebhookPayload(
            tracking_number=awb,
            status=normalized,
            description=payload.get("status_description", "Shiprocket webhook update"),
            event_timestamp=datetime.now(UTC),
            raw_payload=payload,
        )
