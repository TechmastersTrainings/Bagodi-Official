from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.identity.models import User
from app.modules.notifications.models import (
    CustomerCommunicationPreference,
    NotificationAuditLog,
    NotificationMessage,
    NotificationOutbox,
    NotificationTemplate,
)
from app.modules.notifications.providers import (
    NotificationChannel,
    NotificationProviderFactory,
)
from app.modules.notifications.schemas import (
    CustomerCommunicationPreferenceUpdateRequest,
    OutboxProcessResponse,
)
from app.modules.notifications.template_engine import (
    DEFAULT_TEMPLATES,
    render_template_string,
)


async def _resolve_user_id(db: AsyncSession, user_id: UUID | None) -> UUID | None:
    if not user_id:
        return None
    stmt = select(User.id).where(User.id == user_id)
    return (await db.execute(stmt)).scalar_one_or_none()


class NotificationService:
    @staticmethod
    async def log_audit_event(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        event_type: str,
        payload: dict[str, Any],
        message_id: UUID | None = None,
        actor_id: UUID | None = None,
    ) -> NotificationAuditLog:
        valid_actor_id = await _resolve_user_id(db, actor_id)
        audit = NotificationAuditLog(
            tenant_id=tenant_id,
            message_id=message_id,
            event_type=event_type,
            actor_id=valid_actor_id,
            payload=payload,
            created_at=datetime.now(UTC),
        )
        db.add(audit)
        return audit

    @staticmethod
    async def enqueue_outbox_event(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> NotificationOutbox:
        """
        Atomically records a domain event into the transactional outbox.
        Called within the originating database transaction.
        """
        if idempotency_key:
            stmt_idemp = select(NotificationOutbox).where(
                NotificationOutbox.tenant_id == tenant_id,
                NotificationOutbox.idempotency_key == idempotency_key,
            )
            existing = (await db.execute(stmt_idemp)).scalar_one_or_none()
            if existing:
                return existing

        settings = get_settings()
        outbox_entry = NotificationOutbox(
            tenant_id=tenant_id,
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=payload,
            status="pending",
            idempotency_key=idempotency_key,
            retry_count=0,
            max_retries=settings.notification_max_retries,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db.add(outbox_entry)
        await db.flush()
        return outbox_entry

    @staticmethod
    async def get_or_create_customer_preferences(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        customer_id: UUID,
    ) -> CustomerCommunicationPreference:
        stmt = select(CustomerCommunicationPreference).where(
            CustomerCommunicationPreference.tenant_id == tenant_id,
            CustomerCommunicationPreference.customer_id == customer_id,
        )
        pref = (await db.execute(stmt)).scalar_one_or_none()
        if not pref:
            pref = CustomerCommunicationPreference(
                tenant_id=tenant_id,
                customer_id=customer_id,
                email_opt_in=True,
                sms_opt_in=True,
                whatsapp_opt_in=True,
                preferred_channel="whatsapp",
                consent_recorded_at=datetime.now(UTC),
            )
            db.add(pref)
            await db.flush()
        return pref

    @staticmethod
    async def update_customer_preferences(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        customer_id: UUID,
        data: CustomerCommunicationPreferenceUpdateRequest,
        client_ip: str | None = None,
    ) -> CustomerCommunicationPreference:
        pref = await NotificationService.get_or_create_customer_preferences(
            db, tenant_id=tenant_id, customer_id=customer_id
        )

        changes: dict[str, Any] = {}
        if data.email_opt_in is not None:
            pref.email_opt_in = data.email_opt_in
            changes["email_opt_in"] = data.email_opt_in
        if data.sms_opt_in is not None:
            pref.sms_opt_in = data.sms_opt_in
            changes["sms_opt_in"] = data.sms_opt_in
        if data.whatsapp_opt_in is not None:
            pref.whatsapp_opt_in = data.whatsapp_opt_in
            changes["whatsapp_opt_in"] = data.whatsapp_opt_in
        if data.preferred_channel is not None:
            pref.preferred_channel = data.preferred_channel
            changes["preferred_channel"] = data.preferred_channel

        pref.consent_recorded_at = datetime.now(UTC)
        pref.consent_ip_address = client_ip

        await NotificationService.log_audit_event(
            db,
            tenant_id=tenant_id,
            event_type="PREFERENCE_UPDATED",
            payload={"customer_id": str(customer_id), "changes": changes},
            actor_id=customer_id,
        )

        await db.commit()
        await db.refresh(pref)
        return pref

    @staticmethod
    async def resolve_template(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        code: str,
        channel: str,
        language: str = "en",
    ) -> tuple[str | None, str, int]:
        """
        Resolves notification template:
        1. Merchant override (tenant_id == tenant_id)
        2. Platform default (tenant_id IS NULL)
        3. Built-in system default templates
        Returns (subject_template, body_template, version)
        """
        # 1. Merchant specific
        stmt_merchant = (
            select(NotificationTemplate)
            .where(
                NotificationTemplate.tenant_id == tenant_id,
                NotificationTemplate.code == code,
                NotificationTemplate.channel == channel,
                NotificationTemplate.language == language,
                NotificationTemplate.is_active.is_(True),
            )
            .order_by(NotificationTemplate.version.desc())
        )
        t_m = (await db.execute(stmt_merchant)).scalars().first()
        if t_m:
            return (t_m.subject_template, t_m.body_template, t_m.version)

        # 2. Platform default
        stmt_platform = (
            select(NotificationTemplate)
            .where(
                NotificationTemplate.tenant_id.is_(None),
                NotificationTemplate.code == code,
                NotificationTemplate.channel == channel,
                NotificationTemplate.language == language,
                NotificationTemplate.is_active.is_(True),
            )
            .order_by(NotificationTemplate.version.desc())
        )
        t_p = (await db.execute(stmt_platform)).scalars().first()
        if t_p:
            return (t_p.subject_template, t_p.body_template, t_p.version)

        # 3. Codebase system defaults
        default_entry = DEFAULT_TEMPLATES.get(code, {}).get(channel)
        if default_entry:
            return (default_entry.get("subject"), default_entry["body"], 1)

        fallback_body = f"Notification for {code.replace('_', ' ').title()}."
        return (None, fallback_body, 1)

    @staticmethod
    async def dispatch_single_message(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        recipient: str,
        channel: str,
        template_code: str,
        context: dict[str, Any],
        outbox_id: UUID | None = None,
        idempotency_key: str | None = None,
        provider_name: str | None = None,
    ) -> NotificationMessage:
        """
        Renders template, persists NotificationMessage, dispatches via provider,
        and manages retries / dead-letter queues.
        """
        # 1. Idempotency Check
        if idempotency_key:
            stmt_idemp = select(NotificationMessage).where(
                NotificationMessage.tenant_id == tenant_id,
                NotificationMessage.idempotency_key == idempotency_key,
            )
            existing = (await db.execute(stmt_idemp)).scalar_one_or_none()
            if existing:
                return existing

        # 2. Resolve and Render Template
        subject_tmpl, body_tmpl, tmpl_ver = await NotificationService.resolve_template(
            db, tenant_id=tenant_id, code=template_code, channel=channel
        )

        rendered_subject = render_template_string(subject_tmpl, context) if subject_tmpl else None
        rendered_body = render_template_string(body_tmpl, context)

        settings = get_settings()
        provider = NotificationProviderFactory.get_provider(provider_name)

        # 3. Create message record in database
        message = NotificationMessage(
            tenant_id=tenant_id,
            outbox_id=outbox_id,
            recipient=recipient,
            channel=channel,
            template_code=template_code,
            template_version=tmpl_ver,
            subject=rendered_subject,
            body=rendered_body,
            status="processing",
            provider=provider.provider_name,
            idempotency_key=idempotency_key,
            retry_count=0,
            max_retries=settings.notification_max_retries,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db.add(message)
        await db.flush()

        # 4. Dispatch via Provider
        send_result = None
        if channel == NotificationChannel.SMS:
            send_result = await provider.send_sms(
                tenant_id=tenant_id,
                recipient_phone=recipient,
                message=rendered_body,
                metadata=context,
            )
        elif channel == NotificationChannel.WHATSAPP:
            send_result = await provider.send_whatsapp(
                tenant_id=tenant_id,
                recipient_phone=recipient,
                template_name=template_code,
                parameters={k: str(v) for k, v in context.items()},
                fallback_text=rendered_body,
                metadata=context,
            )
        elif channel == NotificationChannel.EMAIL:
            send_result = await provider.send_email(
                tenant_id=tenant_id,
                recipient_email=recipient,
                subject=rendered_subject or "Bagodi Notification",
                body_html=rendered_body,
                metadata=context,
            )

        # 5. Handle Outcome & Exponential Backoff
        if send_result and send_result.success:
            message.status = "sent"
            message.provider_message_id = send_result.provider_message_id
            await NotificationService.log_audit_event(
                db,
                tenant_id=tenant_id,
                message_id=message.id,
                event_type="SENT",
                payload={"channel": channel, "provider_message_id": send_result.provider_message_id},
            )
        else:
            err_code = send_result.error_code if send_result else "UNKNOWN_ERROR"
            err_msg = send_result.error_message if send_result else "Provider dispatch failed"
            message.retry_count = 1
            message.error_code = err_code
            message.error_message = err_msg

            if message.retry_count >= message.max_retries:
                message.status = "dead_letter"
                event_type = "DEAD_LETTER"
            else:
                message.status = "failed"
                event_type = "FAILED"
                backoff_delay = settings.notification_base_retry_delay_seconds * (2 ** message.retry_count)
                message.next_retry_at = datetime.now(UTC) + timedelta(seconds=backoff_delay)

            await NotificationService.log_audit_event(
                db,
                tenant_id=tenant_id,
                message_id=message.id,
                event_type=event_type,
                payload={"error_code": err_code, "error_message": err_msg},
            )

        await db.commit()
        await db.refresh(message)
        return message

    @staticmethod
    async def process_outbox_batch(
        db: AsyncSession,
        *,
        batch_size: int = 50,
    ) -> OutboxProcessResponse:
        """
        Polls and processes pending outbox events.
        Resolves customer communication preferences, determines channels,
        and generates individual notification messages.
        """
        now = datetime.now(UTC)
        stmt = (
            select(NotificationOutbox)
            .where(
                (NotificationOutbox.status == "pending")
                | (
                    (NotificationOutbox.status == "failed")
                    & (NotificationOutbox.next_retry_at <= now)
                    & (NotificationOutbox.retry_count < NotificationOutbox.max_retries)
                )
            )
            .order_by(NotificationOutbox.created_at.asc())
            .limit(batch_size)
        )
        outbox_items = (await db.execute(stmt)).scalars().all()

        processed_count = 0
        dispatched_count = 0
        failed_count = 0
        dead_letter_count = 0

        for item in outbox_items:
            payload = item.payload or {}
            phone = payload.get("customer_phone")
            email = payload.get("customer_email")
            raw_cust_id = payload.get("customer_id")
            customer_id = UUID(raw_cust_id) if raw_cust_id else None

            # Resolve preferences if customer ID exists
            pref = None
            if customer_id:
                pref = await NotificationService.get_or_create_customer_preferences(
                    db, tenant_id=item.tenant_id, customer_id=customer_id
                )

            # Determine Target Channels
            target_channels: list[tuple[str, str]] = []  # (channel, recipient)

            # Mobile channel determination (WhatsApp or SMS)
            if phone:
                if pref:
                    if pref.preferred_channel == "whatsapp" and pref.whatsapp_opt_in:
                        target_channels.append(("whatsapp", phone))
                    elif pref.sms_opt_in:
                        target_channels.append(("sms", phone))
                    elif pref.whatsapp_opt_in:
                        target_channels.append(("whatsapp", phone))
                else:
                    # Default: WhatsApp preferred, fallback SMS
                    target_channels.append(("whatsapp", phone))

            # Email channel determination
            if email and (not pref or pref.email_opt_in):
                target_channels.append(("email", email))

            # Dispatch across resolved channels
            event_success = True
            template_code = item.event_type.replace(".", "_")

            for channel, recipient in target_channels:
                idemp_key = f"{item.id}-{channel}"
                msg = await NotificationService.dispatch_single_message(
                    db,
                    tenant_id=item.tenant_id,
                    recipient=recipient,
                    channel=channel,
                    template_code=template_code,
                    context=payload,
                    outbox_id=item.id,
                    idempotency_key=idemp_key,
                )
                if msg.status in ("sent", "delivered"):
                    dispatched_count += 1
                elif msg.status == "dead_letter":
                    dead_letter_count += 1
                    event_success = False
                else:
                    failed_count += 1
                    event_success = False

            # Update Outbox status
            if event_success:
                item.status = "processed"
                item.processed_at = datetime.now(UTC)
                processed_count += 1
            else:
                item.retry_count += 1
                settings = get_settings()
                if item.retry_count >= item.max_retries:
                    item.status = "failed"
                    item.error_message = "All dispatch channels failed after maximum retries"
                else:
                    backoff = settings.notification_base_retry_delay_seconds * (2 ** item.retry_count)
                    item.next_retry_at = datetime.now(UTC) + timedelta(seconds=backoff)

            await db.commit()

        return OutboxProcessResponse(
            processed_count=processed_count,
            dispatched_messages_count=dispatched_count,
            failed_count=failed_count,
            dead_letter_count=dead_letter_count,
        )

    @staticmethod
    async def handle_delivery_report(
        db: AsyncSession,
        *,
        provider_name: str,
        raw_body: bytes,
        headers: dict[str, str],
    ) -> dict[str, Any]:
        """
        Processes inbound delivery receipt (DLR) webhook callbacks from telecom/email carriers.
        Updates message status to 'delivered' or 'failed'.
        """
        provider = NotificationProviderFactory.get_provider(provider_name)
        dlr = await provider.parse_delivery_report(raw_body=raw_body, headers=headers)

        if not dlr.is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_DLR_SIGNATURE", "message": dlr.error_message or "Webhook signature failed"},
            )

        stmt = select(NotificationMessage).where(
            NotificationMessage.provider_message_id == dlr.provider_message_id
        )
        message = (await db.execute(stmt)).scalar_one_or_none()
        if not message:
            return {"status": "unmapped_message", "provider_message_id": dlr.provider_message_id}

        if message.status != "delivered":
            if dlr.status in ("delivered", "success"):
                message.status = "delivered"
                message.delivery_timestamp = dlr.timestamp
                event_type = "DELIVERED"
            else:
                message.status = "failed"
                message.error_code = dlr.error_code
                message.error_message = dlr.error_message
                event_type = "FAILED"

            await NotificationService.log_audit_event(
                db,
                tenant_id=message.tenant_id,
                message_id=message.id,
                event_type=event_type,
                payload={"dlr_status": dlr.status, "provider_message_id": dlr.provider_message_id},
            )
            await db.commit()

        return {"status": "acknowledged", "provider_message_id": dlr.provider_message_id}

    @staticmethod
    async def retry_notification_message(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        message_id: UUID,
        actor_id: UUID | None = None,
    ) -> NotificationMessage:
        stmt = select(NotificationMessage).where(
            NotificationMessage.id == message_id,
            NotificationMessage.tenant_id == tenant_id,
        )
        msg = (await db.execute(stmt)).scalar_one_or_none()
        if not msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "MESSAGE_NOT_FOUND", "message": "Notification message not found."},
            )

        if msg.status not in ("failed", "dead_letter"):
            return msg

        provider = NotificationProviderFactory.get_provider(msg.provider)
        context = {"retry_by": str(actor_id)}

        send_result = None
        if msg.channel == NotificationChannel.SMS:
            send_result = await provider.send_sms(
                tenant_id=tenant_id,
                recipient_phone=msg.recipient,
                message=msg.body,
                metadata=context,
            )
        elif msg.channel == NotificationChannel.WHATSAPP:
            send_result = await provider.send_whatsapp(
                tenant_id=tenant_id,
                recipient_phone=msg.recipient,
                template_name=msg.template_code,
                parameters={},
                fallback_text=msg.body,
                metadata=context,
            )
        elif msg.channel == NotificationChannel.EMAIL:
            send_result = await provider.send_email(
                tenant_id=tenant_id,
                recipient_email=msg.recipient,
                subject=msg.subject or "Bagodi Notification",
                body_html=msg.body,
                metadata=context,
            )

        if send_result and send_result.success:
            msg.status = "sent"
            msg.provider_message_id = send_result.provider_message_id
            msg.error_code = None
            msg.error_message = None
            await NotificationService.log_audit_event(
                db,
                tenant_id=tenant_id,
                message_id=msg.id,
                event_type="SENT",
                payload={"manual_retry": True, "provider_message_id": send_result.provider_message_id},
                actor_id=actor_id,
            )
        else:
            msg.error_code = send_result.error_code if send_result else "RETRY_FAILED"
            msg.error_message = send_result.error_message if send_result else "Manual retry failed"

        await db.commit()
        await db.refresh(msg)
        return msg
