from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    SecurityPrincipal,
    get_optional_security_principal,
)
from app.db.session import get_db
from app.modules.orders.schemas import (
    CartItemAdd,
    CartItemUpdate,
    CartMergeRequest,
    CartResponse,
)
from app.modules.orders.services import CartService
from app.modules.platform.models import Store, Tenant

router = APIRouter(prefix="/cart", tags=["Customer Shopping Cart"])


async def resolve_cart_context(
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[SecurityPrincipal | None, Depends(get_optional_security_principal)],
    tenant_id: Annotated[UUID | None, Query(description="Merchant organization ID")] = None,
    x_session_id: Annotated[str | None, Header(alias="X-Session-ID")] = None,
    store_id: Annotated[UUID | None, Query(description="Fulfilling store location")] = None,
) -> tuple[UUID, UUID, UUID | None, str | None]:
    """Resolves merchant tenant, fulfilling store, and customer/guest identity."""
    resolved_tenant_id = (principal.tenant_id if principal else None) or tenant_id
    if not resolved_tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "TENANT_REQUIRED",
                "message": "Merchant context (tenant_id) is required.",
            },
        )

    # Validate tenant is active
    tenant = (
        await db.execute(
            select(Tenant).where(Tenant.id == resolved_tenant_id, Tenant.status == "active")
        )
    ).scalar_one_or_none()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "TENANT_NOT_FOUND",
                "message": "Merchant organization not found or inactive.",
            },
        )

    # Resolve fulfilling store
    resolved_store_id = store_id
    if not resolved_store_id:
        store = (
            (
                await db.execute(
                    select(Store)
                    .where(Store.tenant_id == resolved_tenant_id, Store.status == "active")
                    .order_by(Store.code.asc())
                )
            )
            .scalars()
            .first()
        )
        if not store:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "STORE_NOT_FOUND",
                    "message": "No active store found for merchant.",
                },
            )
        resolved_store_id = store.id

    customer_id = (
        (principal.user_id if not principal.is_platform_user else None) if principal else None
    )
    if not customer_id and not x_session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "IDENTIFIER_REQUIRED",
                "message": "Either customer authentication or X-Session-ID header is required.",
            },
        )
    return resolved_tenant_id, resolved_store_id, customer_id, x_session_id


@router.get(
    "",
    response_model=CartResponse,
    summary="Get current shopping cart with real-time stock balances",
)
async def get_cart(
    context: Annotated[tuple[UUID, UUID, UUID | None, str | None], Depends(resolve_cart_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    tenant_id, store_id, customer_id, session_id = context
    cart = await CartService.get_or_create_cart(
        db, tenant_id=tenant_id, customer_id=customer_id, session_id=session_id
    )
    return await CartService.build_cart_response(
        db, tenant_id=tenant_id, cart=cart, store_id=store_id
    )


@router.post(
    "/items",
    response_model=CartResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an item to the shopping cart",
)
async def add_item_to_cart(
    data: CartItemAdd,
    context: Annotated[tuple[UUID, UUID, UUID | None, str | None], Depends(resolve_cart_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    tenant_id, store_id, customer_id, session_id = context
    cart = await CartService.get_or_create_cart(
        db, tenant_id=tenant_id, customer_id=customer_id, session_id=session_id
    )
    return await CartService.add_item(
        db, tenant_id=tenant_id, cart=cart, data=data, store_id=store_id
    )


@router.patch(
    "/items/{item_id}",
    response_model=CartResponse,
    summary="Update item quantity in shopping cart",
)
async def update_cart_item(
    item_id: UUID,
    data: CartItemUpdate,
    context: Annotated[tuple[UUID, UUID, UUID | None, str | None], Depends(resolve_cart_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    tenant_id, store_id, customer_id, session_id = context
    cart = await CartService.get_or_create_cart(
        db, tenant_id=tenant_id, customer_id=customer_id, session_id=session_id
    )
    return await CartService.update_item(
        db, tenant_id=tenant_id, cart=cart, item_id=item_id, data=data, store_id=store_id
    )


@router.delete(
    "/items/{item_id}",
    response_model=CartResponse,
    summary="Remove an item from shopping cart",
)
async def remove_cart_item(
    item_id: UUID,
    context: Annotated[tuple[UUID, UUID, UUID | None, str | None], Depends(resolve_cart_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    tenant_id, store_id, customer_id, session_id = context
    cart = await CartService.get_or_create_cart(
        db, tenant_id=tenant_id, customer_id=customer_id, session_id=session_id
    )
    return await CartService.remove_item(
        db, tenant_id=tenant_id, cart=cart, item_id=item_id, store_id=store_id
    )


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Clear all items from shopping cart",
)
async def clear_cart(
    context: Annotated[tuple[UUID, UUID, UUID | None, str | None], Depends(resolve_cart_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    tenant_id, _, customer_id, session_id = context
    cart = await CartService.get_or_create_cart(
        db, tenant_id=tenant_id, customer_id=customer_id, session_id=session_id
    )
    await CartService.clear_cart(db, cart)


@router.post(
    "/merge",
    response_model=CartResponse,
    summary="Merge guest session cart into authenticated customer cart",
)
async def merge_cart(
    data: CartMergeRequest,
    context: Annotated[tuple[UUID, UUID, UUID | None, str | None], Depends(resolve_cart_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    tenant_id, store_id, customer_id, _ = context
    if not customer_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "AUTHENTICATION_REQUIRED",
                "message": "Customer login is required to merge carts.",
            },
        )
    return await CartService.merge_guest_cart(
        db,
        tenant_id=tenant_id,
        customer_id=customer_id,
        guest_session_id=data.session_id,
        store_id=store_id,
    )
