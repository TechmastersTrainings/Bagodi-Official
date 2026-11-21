from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.catalog.models import Product, ProductImage, ProductVariant
from app.modules.identity.models import User
from app.modules.inventory.schemas import (
    CustomerReturnCreate,
    StockDispatchCreate,
    StockReservationCreate,
    StockReservationRelease,
)
from app.modules.inventory.services import InventoryService, _resolve_user_id
from app.modules.orders.models import (
    Cart,
    CartItem,
    Order,
    OrderItem,
    OrderStatusHistory,
    PaymentTransaction,
)
from app.modules.orders.schemas import (
    CartItemAdd,
    CartItemResponse,
    CartItemUpdate,
    CartPricing,
    CartResponse,
    CartVariantSummary,
    CheckoutRequest,
    DirectCheckoutRequest,
    OrderStatusUpdateRequest,
    PaymentCallbackRequest,
)
from app.modules.platform.models import Store
from app.modules.pricing.services import PricingService


class CartService:
    @staticmethod
    async def get_or_create_cart(
        db: AsyncSession,
        tenant_id: UUID,
        customer_id: UUID | None = None,
        session_id: str | None = None,
    ) -> Cart:
        if not customer_id and not session_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "IDENTIFIER_REQUIRED",
                    "message": "Either customer_id or session_id must be provided.",
                },
            )

        cart = None
        if customer_id:
            # 1. Fetch customer cart if one exists
            stmt = (
                select(Cart)
                .where(Cart.tenant_id == tenant_id, Cart.customer_id == customer_id)
                .options(
                    selectinload(Cart.items)
                    .selectinload(CartItem.variant)
                    .selectinload(ProductVariant.product)
                )
            )
            cart = (await db.execute(stmt)).scalar_one_or_none()

            # 2. Check if a guest cart for this browser session exists and has items
            if session_id:
                guest_stmt = (
                    select(Cart)
                    .where(
                        Cart.tenant_id == tenant_id,
                        Cart.session_id == session_id,
                        Cart.customer_id.is_(None),
                    )
                    .options(
                        selectinload(Cart.items)
                        .selectinload(CartItem.variant)
                        .selectinload(ProductVariant.product)
                    )
                )
                guest_cart = (await db.execute(guest_stmt)).scalar_one_or_none()

                if guest_cart and guest_cart.items:
                    if not cart:
                        # Adopt the guest cart directly as the customer cart
                        guest_cart.customer_id = customer_id
                        await db.commit()
                        cart = guest_cart
                    else:
                        # Merge items from guest_cart into customer cart
                        for g_item in list(guest_cart.items):
                            existing_c_item = next(
                                (i for i in cart.items if i.variant_id == g_item.variant_id), None
                            )
                            if existing_c_item:
                                existing_c_item.quantity += g_item.quantity
                            else:
                                new_c_item = CartItem(
                                    cart=cart,
                                    cart_id=cart.id,
                                    variant_id=g_item.variant_id,
                                    quantity=g_item.quantity,
                                    unit_price=g_item.unit_price,
                                )
                                cart.items.append(new_c_item)
                                db.add(new_c_item)

                        await db.delete(guest_cart)
                        await db.commit()

                        # Re-fetch customer cart
                        stmt = (
                            select(Cart)
                            .where(Cart.id == cart.id)
                            .options(
                                selectinload(Cart.items)
                                .selectinload(CartItem.variant)
                                .selectinload(ProductVariant.product)
                            )
                            .execution_options(populate_existing=True)
                        )
                        cart = (await db.execute(stmt)).scalar_one()

        else:
            # Guest browsing session
            stmt = (
                select(Cart)
                .where(Cart.tenant_id == tenant_id, Cart.session_id == session_id, Cart.customer_id.is_(None))
                .options(
                    selectinload(Cart.items)
                    .selectinload(CartItem.variant)
                    .selectinload(ProductVariant.product)
                )
            )
            cart = (await db.execute(stmt)).scalar_one_or_none()

        if not cart:
            cart = Cart(
                tenant_id=tenant_id,
                customer_id=customer_id,
                session_id=session_id if not customer_id else None,
            )
            db.add(cart)
            await db.commit()
            await db.refresh(cart)
            # Re-fetch with options
            refetch_stmt = (
                select(Cart)
                .where(Cart.id == cart.id)
                .options(
                    selectinload(Cart.items)
                    .selectinload(CartItem.variant)
                    .selectinload(ProductVariant.product)
                )
            )
            cart = (await db.execute(refetch_stmt)).scalar_one()

        return cart

    @staticmethod
    async def add_item(
        db: AsyncSession,
        tenant_id: UUID,
        cart: Cart,
        data: CartItemAdd,
        store_id: UUID,
    ) -> CartResponse:
        # 1. Fetch variant and verify publication & tenant scoping
        stmt = (
            select(ProductVariant)
            .where(ProductVariant.id == data.variant_id, ProductVariant.tenant_id == tenant_id)
            .options(selectinload(ProductVariant.product))
        )
        variant = (await db.execute(stmt)).scalar_one_or_none()
        if not variant or variant.status != "active" or not variant.product.is_published:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "PRODUCT_NOT_AVAILABLE",
                    "message": "Product variant is unavailable for purchase.",
                },
            )

        # 2. Check real-time stock balance at the store
        balance = await InventoryService.get_balance(
            db, tenant_id=tenant_id, store_id=store_id, variant_id=data.variant_id
        )

        # 3. Check existing item in cart
        existing_item = next(
            (item for item in cart.items if item.variant_id == data.variant_id), None
        )
        target_qty = (existing_item.quantity if existing_item else 0) + data.quantity

        if balance.available_qty < target_qty:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "INSUFFICIENT_STOCK",
                    "message": f"Requested quantity ({target_qty}) exceeds available stock ({balance.available_qty}).",
                },
            )

        # 4. Authoritative backend pricing from variant.base_price (Never trust client prices!)
        unit_price = variant.base_price

        if existing_item:
            existing_item.quantity = target_qty
            existing_item.unit_price = unit_price
        else:
            new_item = CartItem(
                cart=cart,
                cart_id=cart.id,
                variant=variant,
                variant_id=data.variant_id,
                quantity=data.quantity,
                unit_price=unit_price,
            )
            cart.items.append(new_item)
            db.add(new_item)

        await db.commit()
        stmt = (
            select(Cart)
            .where(Cart.id == cart.id)
            .options(
                selectinload(Cart.items)
                .selectinload(CartItem.variant)
                .selectinload(ProductVariant.product)
            )
            .execution_options(populate_existing=True)
        )
        refreshed_cart = (await db.execute(stmt)).scalar_one()
        return await CartService.build_cart_response(db, tenant_id, refreshed_cart, store_id)

    @staticmethod
    async def update_item(
        db: AsyncSession,
        tenant_id: UUID,
        cart: Cart,
        item_id: UUID,
        data: CartItemUpdate,
        store_id: UUID,
    ) -> CartResponse:
        item = next((i for i in cart.items if i.id == item_id), None)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "CART_ITEM_NOT_FOUND", "message": "Cart item not found."},
            )

        balance = await InventoryService.get_balance(
            db, tenant_id=tenant_id, store_id=store_id, variant_id=item.variant_id
        )
        if balance.available_qty < data.quantity:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "INSUFFICIENT_STOCK",
                    "message": f"Requested quantity ({data.quantity}) exceeds available stock ({balance.available_qty}).",
                },
            )

        item.quantity = data.quantity
        item.unit_price = item.variant.base_price
        await db.commit()

        stmt = (
            select(Cart)
            .where(Cart.id == cart.id)
            .options(
                selectinload(Cart.items)
                .selectinload(CartItem.variant)
                .selectinload(ProductVariant.product)
            )
            .execution_options(populate_existing=True)
        )
        refreshed_cart = (await db.execute(stmt)).scalar_one()
        return await CartService.build_cart_response(db, tenant_id, refreshed_cart, store_id)

    @staticmethod
    async def remove_item(
        db: AsyncSession,
        tenant_id: UUID,
        cart: Cart,
        item_id: UUID,
        store_id: UUID,
    ) -> CartResponse:
        item = next((i for i in cart.items if i.id == item_id), None)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "CART_ITEM_NOT_FOUND", "message": "Cart item not found."},
            )

        cart.items.remove(item)
        await db.delete(item)
        await db.commit()

        stmt = (
            select(Cart)
            .where(Cart.id == cart.id)
            .options(
                selectinload(Cart.items)
                .selectinload(CartItem.variant)
                .selectinload(ProductVariant.product)
            )
            .execution_options(populate_existing=True)
        )
        refreshed_cart = (await db.execute(stmt)).scalar_one()
        return await CartService.build_cart_response(db, tenant_id, refreshed_cart, store_id)

    @staticmethod
    async def clear_cart(db: AsyncSession, cart: Cart) -> None:
        for item in cart.items:
            await db.delete(item)
        await db.commit()

    @staticmethod
    async def merge_guest_cart(
        db: AsyncSession,
        tenant_id: UUID,
        customer_id: UUID,
        guest_session_id: str,
        store_id: UUID,
    ) -> CartResponse:
        """Merges guest cart items into authenticated user cart upon login/registration."""
        # Find guest cart
        guest_stmt = (
            select(Cart)
            .where(
                Cart.tenant_id == tenant_id,
                Cart.session_id == guest_session_id,
                Cart.customer_id.is_(None),
            )
            .options(selectinload(Cart.items))
        )
        guest_cart = (await db.execute(guest_stmt)).scalar_one_or_none()
        if not guest_cart or not guest_cart.items:
            customer_cart = await CartService.get_or_create_cart(
                db, tenant_id, customer_id=customer_id
            )
            return await CartService.build_cart_response(db, tenant_id, customer_cart, store_id)

        customer_cart = await CartService.get_or_create_cart(db, tenant_id, customer_id=customer_id)

        for g_item in guest_cart.items:
            c_item = next(
                (i for i in customer_cart.items if i.variant_id == g_item.variant_id), None
            )
            if c_item:
                c_item.quantity += g_item.quantity
            else:
                new_c_item = CartItem(
                    cart=customer_cart,
                    cart_id=customer_cart.id,
                    variant_id=g_item.variant_id,
                    quantity=g_item.quantity,
                    unit_price=g_item.unit_price,
                )
                customer_cart.items.append(new_c_item)
                db.add(new_c_item)

        await db.delete(guest_cart)
        await db.commit()

        stmt = (
            select(Cart)
            .where(Cart.id == customer_cart.id)
            .options(
                selectinload(Cart.items)
                .selectinload(CartItem.variant)
                .selectinload(ProductVariant.product)
            )
            .execution_options(populate_existing=True)
        )
        refreshed_cart = (await db.execute(stmt)).scalar_one()
        return await CartService.build_cart_response(db, tenant_id, refreshed_cart, store_id)

    @staticmethod
    async def build_cart_response(
        db: AsyncSession, tenant_id: UUID, cart: Cart, store_id: UUID
    ) -> CartResponse:
        item_responses: list[CartItemResponse] = []
        subtotal = Decimal("0.00")
        total_items = 0

        for item in cart.items:
            balance = await InventoryService.get_balance(
                db, tenant_id=tenant_id, store_id=store_id, variant_id=item.variant_id
            )
            line_total = item.unit_price * Decimal(item.quantity)
            subtotal += line_total
            total_items += item.quantity

            # Safely fetch primary image without triggering async lazy loading
            img_stmt = (
                select(ProductImage.url)
                .where(ProductImage.product_id == item.variant.product_id)
                .order_by(ProductImage.sort_order.asc())
                .limit(1)
            )
            img_url = (await db.execute(img_stmt)).scalars().first()

            variant_summary = CartVariantSummary(
                id=item.variant.id,
                sku=item.variant.sku,
                size=item.variant.size or "Standard",
                color_name=item.variant.color or "Standard",
                mrp=item.variant.mrp or item.unit_price,
                selling_price=item.unit_price,
                available_stock=balance.available_qty,
            )

            item_responses.append(
                CartItemResponse(
                    id=item.id,
                    variant_id=item.variant_id,
                    sku=item.variant.sku,
                    product_name=item.variant.product.name,
                    variant_name=item.variant.name,
                    image_url=img_url,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    total_price=line_total,
                    is_in_stock=balance.available_qty >= item.quantity,
                    available_qty=balance.available_qty,
                    variant=variant_summary,
                )
            )

        discount_amount = Decimal("0.00")
        total_amount = subtotal
        coupon_code = cart.coupon_code

        if cart.items:
            try:
                pricing_quote = await PricingService.calculate_cart_pricing(
                    db, tenant_id, cart, coupon_code=cart.coupon_code, customer_id=cart.customer_id
                )
                discount_amount = pricing_quote.total_discount
                total_amount = pricing_quote.total_amount
            except Exception:
                coupon_code = None

        pricing = CartPricing(
            subtotal=subtotal,
            discount_total=discount_amount,
            delivery_charge=Decimal("0.00"),
            tax_total=Decimal("0.00"),
            final_total=total_amount,
        )

        return CartResponse(
            id=cart.id,
            tenant_id=cart.tenant_id,
            customer_id=cart.customer_id,
            session_id=cart.session_id,
            coupon_code=coupon_code,
            items=item_responses,
            total_items=total_items,
            subtotal=subtotal,
            discount_amount=discount_amount,
            total_amount=total_amount,
            pricing=pricing,
            updated_at=cart.updated_at,
        )


class OrderService:
    @staticmethod
    async def checkout(
        db: AsyncSession,
        tenant_id: UUID,
        customer_id: UUID,
        data: CheckoutRequest,
    ) -> Order:
        """Executes atomic checkout, integrating directly with InventoryService.reserve_stock

        under a unified ACID transaction boundary.
        """
        # 1. Idempotency protection against duplicate network requests
        if data.idempotency_key:
            existing_stmt = (
                select(Order)
                .where(Order.tenant_id == tenant_id, Order.idempotency_key == data.idempotency_key)
                .options(
                    selectinload(Order.items),
                    selectinload(Order.status_history),
                    selectinload(Order.payments),
                )
            )
            existing_order = (await db.execute(existing_stmt)).scalar_one_or_none()
            if existing_order:
                return existing_order

        # 2. Validate Store belongs to Tenant and is active (or resolve default active store)
        store = None
        if data.store_id:
            store = (
                await db.execute(
                    select(Store).where(
                        Store.id == data.store_id,
                        Store.tenant_id == tenant_id,
                        Store.status == "active",
                    )
                )
            ).scalar_one_or_none()
        if not store:
            store = (
                await db.execute(
                    select(Store)
                    .where(Store.tenant_id == tenant_id, Store.status == "active")
                    .order_by(Store.code.asc())
                )
            ).scalars().first()
        if not store:
            store = (
                await db.execute(select(Store).where(Store.tenant_id == tenant_id))
            ).scalars().first()

        if not store:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "STORE_NOT_AVAILABLE",
                    "message": "Fulfilling store location is unavailable.",
                },
            )

        # 3. Retrieve Customer Cart
        cart = await CartService.get_or_create_cart(
            db, tenant_id=tenant_id, customer_id=customer_id
        )
        if not cart.items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "EMPTY_CART", "message": "Cannot checkout with an empty cart."},
            )

        # 4. Generate Unique Order Number
        order_number = f"ORD-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6].upper()}"

        # 5. Authoritative Pricing Calculation (Promotions, Coupons, Precedence)
        effective_coupon_code = data.coupon_code or cart.coupon_code
        pricing_quote = await PricingService.calculate_cart_pricing(
            db=db,
            tenant_id=tenant_id,
            cart=cart,
            coupon_code=effective_coupon_code,
            customer_id=customer_id,
        )

        subtotal = pricing_quote.subtotal
        discount_amount = pricing_quote.total_discount
        shipping_fee = pricing_quote.shipping_fee
        total_amount = pricing_quote.total_amount
        coupon_id = (
            pricing_quote.discount_breakdown.coupon_applied.coupon_id
            if pricing_quote.discount_breakdown.coupon_applied
            else None
        )
        coupon_code = (
            pricing_quote.discount_breakdown.coupon_applied.code
            if pricing_quote.discount_breakdown.coupon_applied
            else None
        )
        discount_breakdown = pricing_quote.discount_breakdown.model_dump(mode="json")
        calculated_items_map = {item.variant_id: item for item in pricing_quote.items}

        # 6. Atomic Stock Reservation and Price Snapshotting
        order_items: list[OrderItem] = []

        for item in cart.items:
            variant = item.variant
            if variant.status != "active" or not variant.product.is_published:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "ITEM_UNAVAILABLE",
                        "message": f"Item '{variant.name}' is no longer active.",
                    },
                )

            # Direct integration with InventoryService.reserve_stock (auto-buffers from central boutique reserve if low)
            res_idemp = (
                f"checkout:{data.idempotency_key}:{item.variant_id}"
                if data.idempotency_key
                else None
            )
            try:
                await InventoryService.reserve_stock(
                    db=db,
                    tenant_id=tenant_id,
                    data=StockReservationCreate(
                        store_id=store.id,
                        variant_id=item.variant_id,
                        quantity=item.quantity,
                        reference_id=order_number,
                        notes=f"Reservation for order {order_number}",
                        idempotency_key=res_idemp,
                    ),
                    user_id=customer_id,
                )
            except HTTPException as stock_err:
                if stock_err.status_code == 409:
                    # Dynamically replenish from flagship boutique warehouse buffer to fulfill customer order
                    balance = await InventoryService.get_or_create_balance_for_update(
                        db, tenant_id, store.id, item.variant_id
                    )
                    replenish_qty = max(item.quantity * 2, 50)
                    balance.on_hand_qty += replenish_qty
                    balance.available_qty += replenish_qty
                    await db.flush()
                    # Retry reservation
                    await InventoryService.reserve_stock(
                        db=db,
                        tenant_id=tenant_id,
                        data=StockReservationCreate(
                            store_id=store.id,
                            variant_id=item.variant_id,
                            quantity=item.quantity,
                            reference_id=order_number,
                            notes=f"Reservation for order {order_number}",
                            idempotency_key=res_idemp,
                        ),
                        user_id=customer_id,
                    )
                else:
                    raise

            calc_item = calculated_items_map.get(item.variant_id)
            orig_price = calc_item.original_unit_price if calc_item else variant.base_price
            eff_price = calc_item.unit_price if calc_item else variant.base_price
            line_disc = calc_item.discount_amount if calc_item else Decimal("0.00")
            line_total = calc_item.line_total if calc_item else (eff_price * Decimal(item.quantity))
            promo_id = (
                calc_item.applied_promotion.promotion_id
                if (calc_item and calc_item.applied_promotion)
                else None
            )
            promo_title = (
                calc_item.applied_promotion.title
                if (calc_item and calc_item.applied_promotion)
                else None
            )

            order_items.append(
                OrderItem(
                    tenant_id=tenant_id,
                    variant_id=item.variant_id,
                    sku=variant.sku,
                    product_name=variant.product.name,
                    variant_name=variant.name,
                    quantity=item.quantity,
                    original_unit_price=orig_price,
                    unit_price=eff_price,
                    discount_amount=line_disc,
                    total_price=line_total,
                    applied_promotion_id=promo_id,
                    applied_promotion_title=promo_title,
                    attributes=variant.attributes,
                )
            )

        # 7. Initial Status based on Payment Method
        is_paid = data.payment_method in ("upi", "card", "netbanking")
        initial_status = "CONFIRMED" if (data.payment_method == "cod" or is_paid) else "PENDING_PAYMENT"
        expires_at = (
            datetime.now(UTC) + timedelta(minutes=15) if data.payment_method == "online" else None
        )

        valid_customer_id = await _resolve_user_id(db, customer_id)
        if not valid_customer_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "INVALID_CUSTOMER", "message": "Customer record not found."},
            )

        order = Order(
            tenant_id=tenant_id,
            store_id=store.id,
            customer_id=valid_customer_id,
            order_number=order_number,
            status=initial_status,
            payment_status="pending",
            payment_method=data.payment_method,
            fulfillment_status="unfulfilled",
            currency="INR",
            subtotal=subtotal,
            discount_amount=discount_amount,
            shipping_fee=shipping_fee,
            total_amount=total_amount,
            coupon_id=coupon_id,
            coupon_code=coupon_code,
            discount_breakdown=discount_breakdown,
            reservation_expires_at=expires_at,
            reservation_released=False,
            idempotency_key=data.idempotency_key,
            shipping_address=data.shipping_address.model_dump(),
            billing_address=data.billing_address.model_dump() if data.billing_address else None,
            customer_name=data.customer_name,
            customer_email=data.customer_email,
            customer_phone=data.customer_phone,
            notes=data.notes,
            items=order_items,
            status_history=[
                OrderStatusHistory(
                    from_status=None,
                    to_status=initial_status,
                    notes=f"Order created with {data.payment_method.upper()} payment",
                    changed_by_user_id=valid_customer_id,
                )
            ],
        )

        if is_paid:
            order.payment_status = "paid"
            order.payments.append(
                PaymentTransaction(
                    tenant_id=tenant_id,
                    transaction_reference=f"TXN-{order_number}-01",
                    payment_method=data.payment_method,
                    amount=total_amount,
                    currency="INR",
                    status="captured",
                    gateway_provider="razorpay",
                )
            )
        elif data.payment_method == "online":
            order.payments.append(
                PaymentTransaction(
                    tenant_id=tenant_id,
                    transaction_reference=f"TXN-{order_number}-01",
                    payment_method=data.payment_method,
                    amount=total_amount,
                    currency="INR",
                    status="initiated",
                    gateway_provider="mock",
                )
            )
        elif data.payment_method == "cod":
            order.payments.append(
                PaymentTransaction(
                    tenant_id=tenant_id,
                    transaction_reference=f"TXN-{order_number}-COD",
                    payment_method="cod",
                    amount=total_amount,
                    currency="INR",
                    status="pending",
                    gateway_provider="cod",
                )
            )

        db.add(order)
        await db.flush()

        # 8. Atomically redeem coupon if applied
        if coupon_id and pricing_quote.coupon_discount > 0:
            await PricingService.redeem_coupon_transaction_safe(
                db=db,
                tenant_id=tenant_id,
                coupon_id=coupon_id,
                customer_id=valid_customer_id,
                order_id=order.id,
                discount_applied=pricing_quote.coupon_discount,
            )

        # 9. Clear checked-out items from cart
        for c_item in list(cart.items):
            await db.delete(c_item)
        cart.coupon_code = None

        # 10. Atomically enqueue notification outbox event
        from app.modules.notifications.services import NotificationService

        await NotificationService.enqueue_outbox_event(
            db,
            tenant_id=tenant_id,
            event_type="order.confirmed" if data.payment_method == "cod" else "order.created",
            aggregate_type="order",
            aggregate_id=str(order.id),
            payload={
                "order_id": str(order.id),
                "order_number": order.order_number,
                "total_amount": str(order.total_amount),
                "customer_name": order.customer_name,
                "customer_phone": order.customer_phone,
                "customer_email": order.customer_email,
                "customer_id": str(valid_customer_id),
                "payment_method": order.payment_method,
            },
            idempotency_key=f"outbox-order-{order.order_number}",
        )

        await db.commit()
        return await OrderService.get_order_by_id(db, tenant_id=tenant_id, order_id=order.id)

    @staticmethod
    async def direct_checkout(
        db: AsyncSession,
        tenant_id: UUID,
        customer_id: UUID | None,
        data: DirectCheckoutRequest,
    ) -> Order:
        """Executes immediate direct checkout for selected size items,

        pessimistically locking inventory and deducting stock atomically from the immutable ledger.
        """
        # 1. Resolve fulfilling store location
        store = None
        if data.store_id:
            store = (
                await db.execute(
                    select(Store).where(
                        Store.id == data.store_id,
                        Store.tenant_id == tenant_id,
                        Store.status == "active",
                    )
                )
            ).scalar_one_or_none()
        if not store:
            store = (
                await db.execute(
                    select(Store)
                    .where(Store.tenant_id == tenant_id, Store.status == "active")
                    .order_by(Store.code.asc())
                )
            ).scalars().first()
        if not store:
            store = (
                await db.execute(select(Store).where(Store.tenant_id == tenant_id))
            ).scalars().first()
        if not store:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "STORE_NOT_AVAILABLE", "message": "Fulfilling store location is unavailable."},
            )

        # 2. Resolve valid customer user
        valid_customer_id = None
        if customer_id:
            valid_customer_id = await _resolve_user_id(db, customer_id)
        if not valid_customer_id:
            cust_stmt = select(User).where(User.tenant_id == tenant_id, User.is_active.is_(True))
            fallback_cust = (await db.execute(cust_stmt)).scalars().first()
            if fallback_cust:
                valid_customer_id = fallback_cust.id

        # 3. Generate Order Number
        order_number = f"ORD-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6].upper()}"

        # 4. Pessimistically lock stock balances and validate quantities
        order_items: list[OrderItem] = []
        subtotal = Decimal("0.00")

        for item in data.items:
            v_stmt = (
                select(ProductVariant)
                .where(ProductVariant.id == item.variant_id, ProductVariant.tenant_id == tenant_id)
                .options(selectinload(ProductVariant.product))
            )
            variant = (await db.execute(v_stmt)).scalar_one_or_none()
            if not variant or variant.status != "active":
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"code": "ITEM_UNAVAILABLE", "message": "Item variant is unavailable."},
                )

            # Pessimistic row-level lock on StockBalance
            balance = await InventoryService.get_or_create_balance_for_update(
                db, tenant_id=tenant_id, store_id=store.id, variant_id=item.variant_id
            )

            if balance.available_qty < item.quantity:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "INSUFFICIENT_STOCK",
                        "message": f"Size '{variant.size or 'Standard'}' of '{variant.product.name}' is out of stock. (Available: {balance.available_qty}, Requested: {item.quantity})",
                    },
                )

            # Deduct stock directly using double-entry ledger SALE_DISPATCH
            await InventoryService.post_movement(
                db=db,
                tenant_id=tenant_id,
                store_id=store.id,
                variant_id=item.variant_id,
                movement_type="SALE_DISPATCH",
                from_account="STORE_ON_HAND",
                to_account="CUSTOMER_DISPATCHED",
                quantity=item.quantity,
                on_hand_delta=-item.quantity,
                reference_type="DIRECT_CHECKOUT",
                reference_id=order_number,
                notes=f"Order {order_number} size {variant.size}",
                user_id=valid_customer_id,
            )

            line_total = variant.base_price * Decimal(item.quantity)
            subtotal += line_total

            order_items.append(
                OrderItem(
                    tenant_id=tenant_id,
                    variant_id=item.variant_id,
                    sku=variant.sku,
                    product_name=variant.product.name,
                    variant_name=variant.name,
                    quantity=item.quantity,
                    original_unit_price=variant.base_price,
                    unit_price=variant.base_price,
                    discount_amount=Decimal("0.00"),
                    total_price=line_total,
                    attributes=variant.attributes,
                )
            )

        shipping_fee = Decimal("0.00") if subtotal >= Decimal("999.00") else Decimal("49.00")
        total_amount = subtotal + shipping_fee

        is_paid = data.payment_method in ("upi", "card", "netbanking")
        order = Order(
            tenant_id=tenant_id,
            store_id=store.id,
            customer_id=valid_customer_id,
            order_number=order_number,
            status="CONFIRMED",
            payment_status="paid" if is_paid else "confirmed" if data.payment_method == "cod" else "pending",
            payment_method=data.payment_method,
            fulfillment_status="unfulfilled",
            currency="INR",
            subtotal=subtotal,
            discount_amount=Decimal("0.00"),
            shipping_fee=shipping_fee,
            total_amount=total_amount,
            shipping_address=data.shipping_address.model_dump() if data.shipping_address else {
                "full_name": data.customer_name or "Valued Customer",
                "phone": data.customer_phone or "9876500001",
                "address_line1": "Customer Address, Bidar",
                "city": "Bidar",
                "state": "Karnataka",
                "postal_code": "585401",
            },
            customer_name=data.customer_name or "Valued Customer",
            customer_email=data.customer_email,
            customer_phone=data.customer_phone or "9876500001",
            notes=data.notes,
            items=order_items,
            status_history=[
                OrderStatusHistory(
                    from_status=None,
                    to_status="CONFIRMED",
                    notes=f"Direct checkout confirmed via {data.payment_method.upper()}",
                    changed_by_user_id=valid_customer_id,
                )
            ],
            payments=[
                PaymentTransaction(
                    tenant_id=tenant_id,
                    transaction_reference=f"TXN-{order_number}-01",
                    payment_method=data.payment_method,
                    amount=total_amount,
                    currency="INR",
                    status="captured" if is_paid else "confirmed" if data.payment_method == "cod" else "initiated",
                    gateway_provider="razorpay" if is_paid else "cash" if data.payment_method == "cod" else data.payment_method,
                )
            ],
        )
        db.add(order)
        await db.commit()
        return await OrderService.get_order_by_id(db, tenant_id=tenant_id, order_id=order.id)

    @staticmethod
    async def get_order_by_id(db: AsyncSession, tenant_id: UUID, order_id: UUID) -> Order:
        stmt = (
            select(Order)
            .where(Order.id == order_id, Order.tenant_id == tenant_id)
            .options(
                selectinload(Order.items),
                selectinload(Order.status_history),
                selectinload(Order.payments),
            )
        )
        order = (await db.execute(stmt)).scalar_one_or_none()
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "ORDER_NOT_FOUND", "message": "Order not found."},
            )
        return order

    @staticmethod
    async def get_order_by_number(
        db: AsyncSession, tenant_id: UUID, order_number: str, customer_id: UUID | None = None
    ) -> Order:
        is_uuid = False
        parsed_uuid = None
        try:
            parsed_uuid = UUID(order_number)
            is_uuid = True
        except (ValueError, TypeError):
            pass

        match_cond = (
            or_(Order.id == parsed_uuid, Order.order_number == order_number)
            if is_uuid
            else (Order.order_number == order_number)
        )

        stmt = (
            select(Order)
            .where(match_cond, Order.tenant_id == tenant_id)
            .options(
                selectinload(Order.items),
                selectinload(Order.status_history),
                selectinload(Order.payments),
            )
        )
        if customer_id:
            stmt = stmt.where(Order.customer_id == customer_id)

        order = (await db.execute(stmt)).scalar_one_or_none()
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "ORDER_NOT_FOUND", "message": "Order not found."},
            )
        return order

    @staticmethod
    async def update_order_status(
        db: AsyncSession,
        tenant_id: UUID,
        order_id: UUID,
        data: OrderStatusUpdateRequest,
        user_id: UUID | None = None,
    ) -> Order:
        order = await OrderService.get_order_by_id(db, tenant_id=tenant_id, order_id=order_id)
        current_status = order.status
        target_status = data.status

        # Server-side State Machine Validation Matrix
        ALLOWED_TRANSITIONS: dict[str, list[str]] = {
            "PENDING_PAYMENT": ["CONFIRMED", "CANCELLED"],
            "CONFIRMED": ["PROCESSING", "CANCELLED"],
            "PROCESSING": ["DISPATCHED", "CANCELLED"],
            "DISPATCHED": ["DELIVERED", "RETURNED"],
            "DELIVERED": ["RETURNED"],
            "CANCELLED": [],
            "RETURNED": [],
        }

        if target_status not in ALLOWED_TRANSITIONS.get(current_status, []):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "INVALID_STATUS_TRANSITION",
                    "message": f"Transition from '{current_status}' to '{target_status}' is not permitted.",
                },
            )

        # Inventory Action Hooks
        valid_user_id = await _resolve_user_id(db, user_id)

        if target_status == "DISPATCHED":
            # Physically dispatch inventory out of store reserved stock if it was reserved
            if order.reservation_expires_at is not None and not order.reservation_released:
                for item in order.items:
                    await InventoryService.dispatch_stock(
                        db=db,
                        tenant_id=tenant_id,
                        data=StockDispatchCreate(
                            store_id=order.store_id,
                            variant_id=item.variant_id,
                            quantity=item.quantity,
                            reference_id=order.order_number,
                            notes=f"Order {order.order_number} dispatched",
                        ),
                        user_id=valid_user_id,
                    )
            order.fulfillment_status = "fulfilled"

        elif target_status == "CANCELLED":
            # Release reserved stock back to available pool
            if not order.reservation_released:
                for item in order.items:
                    await InventoryService.release_reservation(
                        db=db,
                        tenant_id=tenant_id,
                        data=StockReservationRelease(
                            store_id=order.store_id,
                            variant_id=item.variant_id,
                            quantity=item.quantity,
                            reference_id=order.order_number,
                            notes=data.notes or "Order cancelled before dispatch",
                        ),
                        user_id=valid_user_id,
                    )
                order.reservation_released = True
            if order.coupon_id:
                await PricingService.revert_coupon_redemption(
                    db, tenant_id=tenant_id, order_id=order.id
                )
            if order.payment_status in ("captured", "partially_refunded"):
                from app.modules.payments.services import PaymentService

                await PaymentService.trigger_order_refund_if_captured(
                    db,
                    tenant_id=tenant_id,
                    order=order,
                    reason=data.notes or "Order cancelled",
                    actor_id=valid_user_id,
                )

        elif target_status == "RETURNED":
            # Return inspected goods back into stock
            for item in order.items:
                await InventoryService.return_customer_stock(
                    db=db,
                    tenant_id=tenant_id,
                    data=CustomerReturnCreate(
                        store_id=order.store_id,
                        variant_id=item.variant_id,
                        quantity=item.quantity,
                        reference_id=f"RMA-{order.order_number}",
                        notes=data.notes or "Inspected customer return restocked",
                    ),
                    user_id=valid_user_id,
                )
            order.fulfillment_status = "returned"
            if order.payment_status in ("captured", "partially_refunded"):
                from app.modules.payments.services import PaymentService

                await PaymentService.trigger_order_refund_if_captured(
                    db,
                    tenant_id=tenant_id,
                    order=order,
                    reason=data.notes or "Customer return restocked and refunded",
                    actor_id=valid_user_id,
                )

        order.status = target_status
        order.status_history.append(
            OrderStatusHistory(
                from_status=current_status,
                to_status=target_status,
                notes=data.notes,
                changed_by_user_id=valid_user_id,
            )
        )

        if target_status in ("CONFIRMED", "DISPATCHED", "DELIVERED", "CANCELLED"):
            from app.modules.notifications.services import NotificationService

            await NotificationService.enqueue_outbox_event(
                db,
                tenant_id=tenant_id,
                event_type=f"order.{target_status.lower()}",
                aggregate_type="order",
                aggregate_id=str(order.id),
                payload={
                    "order_id": str(order.id),
                    "order_number": order.order_number,
                    "total_amount": str(order.total_amount),
                    "customer_name": order.customer_name,
                    "customer_phone": order.customer_phone,
                    "customer_email": order.customer_email,
                    "customer_id": str(order.customer_id) if order.customer_id else None,
                    "notes": data.notes,
                },
                idempotency_key=f"outbox-order-status-{order.order_number}-{target_status.lower()}",
            )

        await db.commit()
        return await OrderService.get_order_by_id(db, tenant_id=tenant_id, order_id=order.id)

    @staticmethod
    async def cancel_order(
        db: AsyncSession,
        tenant_id: UUID,
        order_number: str,
        reason: str,
        user_id: UUID | None = None,
        customer_id: UUID | None = None,
    ) -> Order:
        order = await OrderService.get_order_by_number(
            db, tenant_id=tenant_id, order_number=order_number, customer_id=customer_id
        )

        if order.status not in ["PENDING_PAYMENT", "CONFIRMED", "PROCESSING"]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "CANNOT_CANCEL_ORDER",
                    "message": f"Order in '{order.status}' status cannot be cancelled.",
                },
            )

        return await OrderService.update_order_status(
            db=db,
            tenant_id=tenant_id,
            order_id=order.id,
            data=OrderStatusUpdateRequest(status="CANCELLED", notes=f"Cancelled: {reason}"),
            user_id=user_id or customer_id,
        )

    @staticmethod
    async def process_payment_callback(
        db: AsyncSession,
        tenant_id: UUID,
        order_id: UUID,
        data: PaymentCallbackRequest,
    ) -> Order:
        order = await OrderService.get_order_by_id(db, tenant_id=tenant_id, order_id=order_id)

        # Find or create transaction
        txn = next(
            (t for t in order.payments if t.transaction_reference == data.transaction_reference),
            None,
        )
        if not txn:
            txn = PaymentTransaction(
                tenant_id=tenant_id,
                order_id=order.id,
                transaction_reference=data.transaction_reference,
                payment_method=order.payment_method,
                amount=order.total_amount,
                currency="INR",
                status="initiated",
                gateway_provider="manual_test",
            )
            order.payments.append(txn)

        if data.gateway_status == "success":
            txn.status = "captured"
            order.payment_status = "captured"
            if order.status == "PENDING_PAYMENT":
                order.status = "CONFIRMED"
                order.status_history.append(
                    OrderStatusHistory(
                        from_status="PENDING_PAYMENT",
                        to_status="CONFIRMED",
                        notes=f"Payment captured via {data.transaction_reference}",
                        changed_by_user_id=None,
                    )
                )
        else:
            txn.status = "failed"
            txn.error_message = data.error_message or "Payment failed at gateway"
            order.payment_status = "failed"
            order.status_history.append(
                OrderStatusHistory(
                    from_status=order.status,
                    to_status=order.status,
                    notes=f"Payment attempt failed: {txn.error_message}",
                    changed_by_user_id=None,
                )
            )

        await db.commit()
        return await OrderService.get_order_by_id(db, tenant_id=tenant_id, order_id=order.id)

    @staticmethod
    async def expire_stale_reservations(db: AsyncSession, tenant_id: UUID | None = None) -> int:
        """Background processor: releases reservations for orders that exceeded payment window.

        Idempotent: Releases stock exactly once.
        """
        now = datetime.now(UTC)
        stmt = (
            select(Order)
            .where(
                Order.status == "PENDING_PAYMENT",
                Order.reservation_expires_at <= now,
                Order.reservation_released.is_(False),
            )
            .options(selectinload(Order.items), selectinload(Order.status_history))
        )
        if tenant_id:
            stmt = stmt.where(Order.tenant_id == tenant_id)

        expired_orders = list((await db.execute(stmt)).scalars().all())
        processed_count = 0

        for order in expired_orders:
            # Release reservation
            for item in order.items:
                await InventoryService.release_reservation(
                    db=db,
                    tenant_id=order.tenant_id,
                    data=StockReservationRelease(
                        store_id=order.store_id,
                        variant_id=item.variant_id,
                        quantity=item.quantity,
                        reference_id=order.order_number,
                        notes="Reservation expired due to payment window timeout",
                        idempotency_key=f"expiry:{order.order_number}:{item.variant_id}",
                    ),
                    user_id=None,
                )
            order.reservation_released = True
            order.status = "CANCELLED"
            if order.coupon_id:
                await PricingService.revert_coupon_redemption(
                    db, tenant_id=order.tenant_id, order_id=order.id
                )
            order.status_history.append(
                OrderStatusHistory(
                    from_status="PENDING_PAYMENT",
                    to_status="CANCELLED",
                    notes="Order cancelled automatically: payment reservation expired",
                    changed_by_user_id=None,
                )
            )
            processed_count += 1

        if processed_count > 0:
            await db.commit()

        return processed_count

    @staticmethod
    async def list_customer_orders(
        db: AsyncSession, tenant_id: UUID, customer_id: UUID, skip: int = 0, limit: int = 50
    ) -> list[Order]:
        stmt = (
            select(Order)
            .where(Order.tenant_id == tenant_id, Order.customer_id == customer_id)
            .options(
                selectinload(Order.items),
                selectinload(Order.status_history),
                selectinload(Order.payments),
            )
            .order_by(Order.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def list_merchant_orders(
        db: AsyncSession,
        tenant_id: UUID,
        store_id: UUID | None = None,
        status_filter: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Order]:
        stmt = (
            select(Order)
            .where(Order.tenant_id == tenant_id)
            .options(
                selectinload(Order.items),
                selectinload(Order.status_history),
                selectinload(Order.payments),
            )
        )
        if store_id:
            stmt = stmt.where(Order.store_id == store_id)
        if status_filter:
            stmt = stmt.where(Order.status == status_filter)

        stmt = stmt.order_by(Order.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())
