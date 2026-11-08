from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.modules.catalog.models import ProductVariant
from app.modules.orders.models import Cart, CartItem
from app.modules.orders.router_cart import resolve_cart_context
from app.modules.orders.schemas import CartResponse
from app.modules.orders.services import CartService
from app.modules.pricing.schemas import (
    CartCouponApplyRequest,
    PriceQuoteResponse,
)
from app.modules.pricing.services import PricingService

router = APIRouter(tags=["Customer Pricing & Coupons"])


@router.get(
    "/pricing/quote",
    response_model=PriceQuoteResponse,
    summary="Get authoritative price quote and discount breakdown for current cart",
)
async def get_cart_price_quote(
    context: Annotated[tuple[UUID, UUID, UUID | None, str | None], Depends(resolve_cart_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
    coupon_code: Annotated[str | None, Query(description="Optional coupon code to preview")] = None,
):
    tenant_id, _, customer_id, session_id = context
    cart = await CartService.get_or_create_cart(
        db, tenant_id=tenant_id, customer_id=customer_id, session_id=session_id
    )
    if not cart.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "EMPTY_CART", "message": "Cannot calculate pricing on an empty cart."},
        )

    return await PricingService.calculate_cart_pricing(
        db,
        tenant_id=tenant_id,
        cart=cart,
        coupon_code=coupon_code,
        customer_id=customer_id,
    )


@router.post(
    "/cart/coupon",
    response_model=CartResponse,
    summary="Apply coupon code to active shopping cart",
)
async def apply_coupon_to_cart(
    data: CartCouponApplyRequest,
    context: Annotated[tuple[UUID, UUID, UUID | None, str | None], Depends(resolve_cart_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    tenant_id, store_id, customer_id, session_id = context
    cart = await CartService.get_or_create_cart(
        db, tenant_id=tenant_id, customer_id=customer_id, session_id=session_id
    )
    if not cart.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "EMPTY_CART",
                "message": "Add items to your cart before applying a coupon.",
            },
        )

    # Validate coupon eligibility against current cart
    quote = await PricingService.calculate_cart_pricing(
        db,
        tenant_id=tenant_id,
        cart=cart,
        coupon_code=data.code,
        customer_id=customer_id,
    )

    if not quote.discount_breakdown.coupon_applied:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "COUPON_NOT_APPLICABLE",
                "message": "Coupon code could not be applied to cart.",
            },
        )

    cart.coupon_code = data.code
    await db.commit()

    # Re-fetch cart with eager loads
    refreshed_cart = (
        await db.execute(
            select(Cart)
            .where(Cart.id == cart.id)
            .options(
                selectinload(Cart.items)
                .selectinload(CartItem.variant)
                .selectinload(ProductVariant.product)
            )
            .execution_options(populate_existing=True)
        )
    ).scalar_one()

    return await CartService.build_cart_response(db, tenant_id, refreshed_cart, store_id)


@router.delete(
    "/cart/coupon",
    response_model=CartResponse,
    summary="Remove coupon code from active shopping cart",
)
async def remove_coupon_from_cart(
    context: Annotated[tuple[UUID, UUID, UUID | None, str | None], Depends(resolve_cart_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    tenant_id, store_id, customer_id, session_id = context
    cart = await CartService.get_or_create_cart(
        db, tenant_id=tenant_id, customer_id=customer_id, session_id=session_id
    )
    cart.coupon_code = None
    await db.commit()

    refreshed_cart = (
        await db.execute(
            select(Cart)
            .where(Cart.id == cart.id)
            .options(
                selectinload(Cart.items)
                .selectinload(CartItem.variant)
                .selectinload(ProductVariant.product)
            )
            .execution_options(populate_existing=True)
        )
    ).scalar_one()

    return await CartService.build_cart_response(db, tenant_id, refreshed_cart, store_id)
