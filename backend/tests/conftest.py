import uuid
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.config import get_settings
from app.core.tokens import create_access_token
from app.db.session import engine
from app.main import app
from app.modules.identity.otp_provider import InMemoryTestOTPProvider

settings = get_settings()
settings.otp_provider = "in_memory"


@pytest_asyncio.fixture(autouse=True)
async def cleanup_db_after_each_test():
    InMemoryTestOTPProvider.clear()
    yield
    # Clean up test transactions to keep the database completely clean and free of leftover test data
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE notification_audit_logs, customer_communication_preferences, "
                "notification_messages, notification_templates, notification_outbox, "
                "payment_audit_logs, processed_webhook_events, cod_settlements, refunds, "
                "pricing_audit_logs, coupon_redemptions, coupons, promotions, "
                "payment_transactions, order_status_history, order_items, orders, "
                "cart_items, carts, "
                "store_transfer_items, store_transfers, stock_receipt_items, "
                "stock_receipts, purchase_order_items, purchase_orders, suppliers, "
                "inventory_ledger, stock_balances, "
                "product_images, product_variants, products, brands, categories, "
                "user_sessions, otp_requests, stores, role_permissions, "
                "user_roles, roles, tenants, users, permissions CASCADE;"
            )
        )
    await engine.dispose()
    InMemoryTestOTPProvider.clear()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mint_jwt_token():
    def _mint(
        user_id: UUID | None = None,
        is_platform_user: bool = False,
        tenant_id: UUID | None = None,
        roles: list[str] | None = None,
        permissions: list[str] | None = None,
        session_id: UUID | None = None,
    ) -> str:
        uid = user_id or uuid.uuid4()
        sid = session_id or uuid.uuid4()
        token, _ = create_access_token(
            user_id=uid,
            is_platform_user=is_platform_user,
            tenant_id=tenant_id,
            session_id=sid,
            roles=roles or [],
            permissions=permissions or [],
        )
        return token

    return _mint
