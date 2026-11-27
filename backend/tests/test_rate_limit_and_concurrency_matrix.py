import asyncio
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.passwords import hash_password
from app.db.session import engine
from app.modules.catalog.models import Brand, Category, Product, ProductVariant
from app.modules.identity.models import User
from app.modules.inventory.models import StockBalance
from app.modules.inventory.services import InventoryService
from app.modules.platform.models import Store, Tenant


@pytest.mark.asyncio
async def test_rate_limit_middleware_blocks_burst_auth_traffic(client: AsyncClient):
    headers = {
        "X-Enforce-RateLimit": "true",
        "X-Forwarded-For": f"203.0.113.{int(uuid4().int % 200) + 10}",
    }
    for idx in range(30):
        resp = await client.post(
            "/api/v1/auth/otp/send",
            json={"phoneOrEmail": f"987654{idx:04d}", "channel": "SMS"},
            headers=headers,
        )
        assert resp.status_code != 429, f"Unexpected 429 at request {idx + 1}"
        assert resp.headers.get("X-RateLimit-Limit") == "30"
        assert resp.headers.get("X-RateLimit-Remaining") == str(29 - idx)

    blocked = await client.post(
        "/api/v1/auth/otp/send",
        json={"phoneOrEmail": "9876549999", "channel": "SMS"},
        headers=headers,
    )
    assert blocked.status_code == 429
    assert blocked.headers.get("Retry-After") == "60"
    assert blocked.headers.get("X-RateLimit-Remaining") == "0"
    assert blocked.json()["code"] == "RATE_LIMIT_EXCEEDED"


@pytest.mark.asyncio
async def test_flash_sale_burst_prevents_oversell_and_restores_on_cancel(
    client: AsyncClient,
    mint_jwt_token,
):
    total_units = 2
    concurrent_buyers = 10

    async with AsyncSession(engine) as db:
        tenant = Tenant(
            name="Flash Sale Couturier",
            slug=f"flash-{uuid4().hex[:6]}",
            legal_name="Flash Retail Pvt Ltd",
            status="active",
            contact_email="flash@bagodi.in",
            contact_phone="+919800033333",
        )
        db.add(tenant)
        await db.flush()

        store = Store(
            tenant_id=tenant.id,
            name="Flagship Bidar",
            code=f"STR-{uuid4().hex[:4]}",
            status="active",
        )
        db.add(store)

        cat = Category(tenant_id=tenant.id, name="Blazers", slug=f"blazers-{uuid4().hex[:4]}")
        brand = Brand(tenant_id=tenant.id, name="Raymond", slug=f"ray-{uuid4().hex[:4]}")
        db.add_all([cat, brand])
        await db.flush()

        product = Product(
            tenant_id=tenant.id,
            category_id=cat.id,
            brand_id=brand.id,
            name="Limited Bandhgala",
            slug=f"limited-bandhgala-{uuid4().hex[:6]}",
            status="active",
            is_published=True,
        )
        db.add(product)
        await db.flush()

        variant = ProductVariant(
            tenant_id=tenant.id,
            product_id=product.id,
            sku=f"SKU-F-{uuid4().hex[:6]}",
            name="Royal Navy M",
            size="M",
            color="Navy",
            mrp=Decimal("5999.00"),
            base_price=Decimal("4480.00"),
            status="active",
        )
        db.add(variant)
        await db.flush()

        users: list[User] = []
        for idx in range(concurrent_buyers):
            u = User(
                phone_e164=f"+91981110{idx:04d}",
                email=f"flash_buyer_{idx}_{uuid4().hex[:4]}@bagodi.in",
                display_name=f"Flash Buyer {idx}",
                password_hash=hash_password("Pass12345!"),
                status="active",
                is_platform_user=False,
            )
            db.add(u)
            users.append(u)
        await db.flush()

        tenant_id, store_id, variant_id = tenant.id, store.id, variant.id
        user_ids = [u.id for u in users]

        await InventoryService.post_movement(
            db,
            tenant_id=tenant_id,
            store_id=store_id,
            variant_id=variant_id,
            movement_type="RECEIPT",
            from_account="SUPPLIER",
            to_account="ON_HAND",
            quantity=total_units,
            on_hand_delta=total_units,
            user_id=user_ids[0],
        )

    buyer_headers: list[dict[str, str]] = []
    for uid in user_ids:
        tok = mint_jwt_token(
            user_id=uid,
            tenant_id=tenant_id,
            roles=["customer"],
            permissions=["customer.*"],
        )
        hdrs = {"Authorization": f"Bearer {tok}"}
        buyer_headers.append(hdrs)
        add_res = await client.post(
            f"/api/v1/cart/items?store_id={store_id}",
            json={"variant_id": str(variant_id), "quantity": 1},
            headers=hdrs,
        )
        assert add_res.status_code == 201

    async def attempt_checkout(idx: int):
        return await client.post(
            "/api/v1/orders/checkout",
            json={
                "store_id": str(store_id),
                "payment_method": "cod",
                "shipping_address": {
                    "full_name": f"Flash Buyer {idx}",
                    "phone": f"+91981110{idx:04d}",
                    "address_line1": "Fort Road",
                    "city": "Bidar",
                    "state": "Karnataka",
                    "postal_code": "585401",
                },
                "customer_name": f"Flash Buyer {idx}",
                "customer_phone": f"+91981110{idx:04d}",
            },
            headers=buyer_headers[idx],
        )

    responses = await asyncio.gather(*(attempt_checkout(i) for i in range(concurrent_buyers)))
    succeeded = [r for r in responses if r.status_code == 201]
    rejected = [r for r in responses if r.status_code != 201]

    assert len(succeeded) == total_units
    assert len(rejected) == concurrent_buyers - total_units
    assert all(r.status_code == 409 for r in rejected)

    async with AsyncSession(engine) as db:
        bal = (
            await db.execute(
                select(StockBalance).where(
                    StockBalance.store_id == store_id,
                    StockBalance.variant_id == variant_id,
                )
            )
        ).scalar_one()
        assert bal.on_hand_qty == total_units
        assert bal.reserved_qty == total_units
        assert bal.available_qty == 0

    first_order = succeeded[0].json()
    first_hdrs = buyer_headers[int(first_order["customer_name"].split()[-1])]
    cancel_res = await client.post(
        f"/api/v1/orders/{first_order['order_number']}/cancel",
        json={"reason": "Customer cancelled after flash checkout"},
        headers=first_hdrs,
    )
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "CANCELLED"

    async with AsyncSession(engine) as db:
        bal = (
            await db.execute(
                select(StockBalance).where(
                    StockBalance.store_id == store_id,
                    StockBalance.variant_id == variant_id,
                )
            )
        ).scalar_one()
        assert bal.reserved_qty == 1
        assert bal.available_qty == 1


def test_production_config_failsafe_blocks_insecure_defaults():
    insecure = Settings(
        app_env="production",
        allow_mock_providers_in_production=False,
        jwt_secret_key="short-dev-key",
        payment_gateway_provider="mock",
    )
    with pytest.raises(ValueError):
        insecure.validate_production_configuration()

    valid = Settings(
        app_env="production",
        debug=False,
        allow_mock_providers_in_production=False,
        jwt_secret_key="0123456789abcdef0123456789abcdef_live_signing_key",
        payment_gateway_provider="razorpay",
        payment_mock_secret="prod_webhook_live_signing_key_9988",
        payment_webhook_secret="prod_webhook_live_signing_key_9988",
        razorpay_key_id="rzp_live_123456",
        razorpay_key_secret="rzp_live_secret_123456",
        otp_provider="twilio",
        twilio_account_sid="AC_live_123456",
        twilio_auth_token="live_auth_token_123456",
        twilio_from_phone="+919972000805",
        courier_provider="shiprocket",
        shiprocket_email="ops@bagodi.in",
        shiprocket_password="strong-courier-password",
        notification_default_provider="twilio",
        notification_sms_provider="twilio",
        notification_whatsapp_provider="twilio",
        notification_webhook_secret="prod_notif_secret_live_key_1234",
    )
    valid.validate_production_configuration()
