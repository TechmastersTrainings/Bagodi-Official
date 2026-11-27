from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import SecurityPrincipal, get_security_principal
from app.db.session import get_db
from app.modules.catalog.models import Product
from app.modules.catalog.services import ProductService
from app.modules.orders.models import WishlistItem
from app.modules.platform.models import Tenant

router = APIRouter(prefix="/wishlist", tags=["Customer Wishlist"])


async def _resolve_wishlist_tenant(
    db: AsyncSession,
    principal: SecurityPrincipal,
    x_tenant_id: UUID | None,
    tenant_id: UUID | None,
) -> UUID:
    resolved = principal.tenant_id or x_tenant_id or tenant_id
    if resolved:
        tenant = (
            await db.execute(select(Tenant).where(Tenant.id == resolved, Tenant.status == "active"))
        ).scalar_one_or_none()
        if tenant:
            return tenant.id
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "TENANT_INACTIVE", "message": "Merchant is unavailable or suspended."},
        )
    anchor = (
        await db.execute(select(Tenant).where(Tenant.status == "active").order_by(Tenant.created_at.asc()))
    ).scalars().first()
    if not anchor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "TENANT_NOT_FOUND", "message": "No active merchant found."},
        )
    return anchor.id


def _serialize_wishlist_item(item: WishlistItem) -> dict:
    product = item.product
    variants = list(product.variants or []) if product else []
    images = sorted(product.images or [], key=lambda img: img.sort_order) if product else []
    first_var = variants[0] if variants else None
    total_stock = sum(max(0, int(getattr(v, "available_stock", 0) or 0)) for v in variants)
    selling_price = float(first_var.base_price) if first_var else 0.0
    mrp = float(first_var.mrp) if first_var and first_var.mrp else selling_price
    return {
        "id": str(item.id),
        "productId": str(item.product_id),
        "product_id": str(item.product_id),
        "name": product.name if product else "",
        "slug": product.slug if product else "",
        "imageUrl": images[0].url if images else None,
        "basePrice": selling_price,
        "mrp": mrp,
        "inStock": total_stock > 0 or bool(variants),
        "categoryName": product.category.name if (product and product.category) else None,
        "variants": [
            {
                "id": str(v.id),
                "size": v.size,
                "sellingPrice": float(v.base_price),
                "availableStock": int(getattr(v, "available_stock", 0) or 0),
            }
            for v in variants
        ],
        "createdAt": item.created_at.isoformat() if item.created_at else None,
    }


@router.get("", summary="List customer wishlist products")
async def list_wishlist_items(
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_tenant_id: Annotated[UUID | None, Header(alias="X-Tenant-ID")] = None,
    tenant_id: Annotated[UUID | None, Query()] = None,
) -> list[dict]:
    if not principal.user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    target_tenant_id = await _resolve_wishlist_tenant(db, principal, x_tenant_id, tenant_id)
    stmt = (
        select(WishlistItem)
        .where(
            WishlistItem.tenant_id == target_tenant_id,
            WishlistItem.customer_id == principal.user_id,
        )
        .options(
            selectinload(WishlistItem.product).selectinload(Product.variants),
            selectinload(WishlistItem.product).selectinload(Product.images),
            selectinload(WishlistItem.product).selectinload(Product.category),
        )
        .order_by(WishlistItem.created_at.desc())
    )
    items = list((await db.execute(stmt)).scalars().all())
    products = [i.product for i in items if i.product is not None]
    if products:
        await ProductService._attach_stock_balances(db, products)
    return [_serialize_wishlist_item(i) for i in items if i.product is not None]


@router.post("/items/{product_id}", status_code=status.HTTP_201_CREATED, summary="Save product to wishlist")
async def add_wishlist_item(
    product_id: UUID,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_tenant_id: Annotated[UUID | None, Header(alias="X-Tenant-ID")] = None,
    tenant_id: Annotated[UUID | None, Query()] = None,
) -> dict:
    if not principal.user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    target_tenant_id = await _resolve_wishlist_tenant(db, principal, x_tenant_id, tenant_id)

    product = (
        await db.execute(
            select(Product).where(Product.id == product_id, Product.tenant_id == target_tenant_id)
        )
    ).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")

    existing = (
        await db.execute(
            select(WishlistItem).where(
                WishlistItem.tenant_id == target_tenant_id,
                WishlistItem.customer_id == principal.user_id,
                WishlistItem.product_id == product_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        return {"status": "saved", "productId": str(product_id), "id": str(existing.id)}

    entry = WishlistItem(
        tenant_id=target_tenant_id,
        customer_id=principal.user_id,
        product_id=product_id,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return {"status": "saved", "productId": str(product_id), "id": str(entry.id)}


@router.delete("/items/{product_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove product from wishlist")
async def remove_wishlist_item(
    product_id: UUID,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_tenant_id: Annotated[UUID | None, Header(alias="X-Tenant-ID")] = None,
    tenant_id: Annotated[UUID | None, Query()] = None,
) -> None:
    if not principal.user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    target_tenant_id = await _resolve_wishlist_tenant(db, principal, x_tenant_id, tenant_id)
    await db.execute(
        delete(WishlistItem).where(
            WishlistItem.tenant_id == target_tenant_id,
            WishlistItem.customer_id == principal.user_id,
            WishlistItem.product_id == product_id,
        )
    )
    await db.commit()
