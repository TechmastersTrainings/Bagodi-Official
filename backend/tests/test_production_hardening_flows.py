from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.passwords import hash_password
from app.db.session import engine
from app.modules.catalog.models import Brand, Category, Product, ProductVariant
from app.modules.delivery.providers.shiprocket_provider import ShiprocketCourierProvider
from app.modules.identity.models import Role, User, UserRole
from app.modules.inventory.services import InventoryService
from app.modules.platform.models import Store, Tenant


@pytest.mark.asyncio
async def test_wishlist_persistence_and_gst_order_breakdown(client: AsyncClient, mint_jwt_token):
    from sqlalchemy.ext.asyncio import AsyncSession

    async with AsyncSession(engine) as db:
        tenant = Tenant(
            name="Wishlist Store",
            slug=f"wish-{uuid4().hex[:6]}",
            legal_name="Wishlist Retail Pvt Ltd",
            status="active",
            contact_email="wish@bagodi.in",
            contact_phone="+919800011111",
        )
        db.add(tenant)
        await db.flush()

        store = Store(
            tenant_id=tenant.id,
            name="Flagship",
            code="STR-W1",
            status="active",
        )
        db.add(store)

        user = User(
            phone_e164="+919800022222",
            email="wishcust@bagodi.in",
            display_name="Wish Customer",
            password_hash=hash_password("Pass12345!"),
            status="active",
            is_platform_user=False,
        )
        db.add(user)

        cat = Category(tenant_id=tenant.id, name="Silk Sarees", slug=f"sarees-{uuid4().hex[:4]}")
        brand = Brand(tenant_id=tenant.id, name="Bagodi Silk", slug=f"brand-{uuid4().hex[:4]}")
        db.add_all([cat, brand])
        await db.flush()

        product = Product(
            tenant_id=tenant.id,
            category_id=cat.id,
            brand_id=brand.id,
            name="Kanjeevaram Zari Saree",
            slug=f"kanjeevaram-{uuid4().hex[:6]}",
            status="active",
            is_published=True,
        )
        db.add(product)
        await db.flush()

        variant = ProductVariant(
            tenant_id=tenant.id,
            product_id=product.id,
            sku=f"SKU-W-{uuid4().hex[:6]}",
            name="Standard Red",
            size="FREE",
            color="Crimson",
            mrp=Decimal("2499.00"),
            base_price=Decimal("2240.00"),
            status="active",
        )
        db.add(variant)
        await db.flush()

        tenant_id, user_id, product_id, variant_id, store_id = (
            tenant.id,
            user.id,
            product.id,
            variant.id,
            store.id,
        )

        await InventoryService.post_movement(
            db,
            tenant_id=tenant_id,
            store_id=store_id,
            variant_id=variant_id,
            movement_type="RECEIPT",
            from_account="SUPPLIER",
            to_account="ON_HAND",
            quantity=3,
            on_hand_delta=3,
            user_id=user_id,
        )

    tok = mint_jwt_token(user_id=user_id, tenant_id=tenant_id, roles=["customer"], permissions=["customer.*"])
    headers = {"Authorization": f"Bearer {tok}"}

    # 1. Save product to persistent DB wishlist
    add_res = await client.post(f"/api/v1/wishlist/items/{product_id}", headers=headers)
    assert add_res.status_code == 201

    # Duplicate save is idempotent
    dup_res = await client.post(f"/api/v1/wishlist/items/{product_id}", headers=headers)
    assert dup_res.status_code == 201

    list_res = await client.get("/api/v1/wishlist", headers=headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1
    assert list_res.json()[0]["productId"] == str(product_id)

    # 2. Remove from wishlist
    del_res = await client.delete(f"/api/v1/wishlist/items/{product_id}", headers=headers)
    assert del_res.status_code == 204
    assert (await client.get("/api/v1/wishlist", headers=headers)).json() == []

    # 3. Checkout & verify Indian GST inclusive breakdown on OrderResponse
    await client.post(
        f"/api/v1/cart/items?store_id={store_id}",
        json={"variant_id": str(variant_id), "quantity": 1},
        headers=headers,
    )
    chk = await client.post(
        "/api/v1/orders/checkout",
        json={
            "store_id": str(store_id),
            "payment_method": "cod",
            "shipping_address": {
                "full_name": "Wish Customer",
                "phone": "+919800022222",
                "address_line1": "Bidar Fort Rd",
                "city": "Bidar",
                "state": "Karnataka",
                "postal_code": "585401",
            },
            "customer_name": "Wish Customer",
            "customer_phone": "+919800022222",
        },
        headers=headers,
    )
    assert chk.status_code == 201
    order_json = chk.json()
    assert order_json["total_amount"] == "2240.00"
    assert order_json["taxAmount"] == 240.0
    assert order_json["cgstAmount"] == 120.0
    assert order_json["sgstAmount"] == 120.0
    assert order_json["taxableAmount"] == 2000.0


def test_shiprocket_rejects_unsigned_webhooks():
    provider = ShiprocketCourierProvider(
        email="sandbox@bagodi.internal",
        password="pass",
        api_key="sr_whsec_test_secret_key",
        is_sandbox=True,
    )
    assert provider.verify_webhook_signature(b'{"awb":"SR123"}', {}) is False
    assert provider.verify_webhook_signature(b'{"awb":"SR123"}', {"X-Api-Key": "sr_whsec_test_secret_key"}) is True
