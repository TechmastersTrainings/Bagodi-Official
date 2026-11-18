from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import SecurityPrincipal, get_optional_security_principal
from app.db.session import get_db
from app.modules.catalog.models import Brand, Category, Product, ProductImage, ProductVariant
from app.modules.catalog.schemas import (
    BrandResponse,
    CategoryResponse,
    ProductCreate,
    ProductDetailResponse,
    ProductImageCreate,
    ProductUpdate,
    ProductVariantCreate,
    ProductVariantResponse,
)
from app.modules.catalog.services import BrandService, CategoryService, ProductService
from app.modules.platform.models import Tenant

router = APIRouter(prefix="/catalog", tags=["Customer Catalogue"])
storefront_router = APIRouter(tags=["Storefront Public"])


@router.get(
    "/categories",
    response_model=list[CategoryResponse],
    summary="List active categories for customer browsing",
)
@storefront_router.get(
    "/categories",
    response_model=list[CategoryResponse],
    summary="List active categories for customer storefront",
)
async def list_public_categories(
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: Annotated[UUID | None, Query(description="Optional merchant filter")] = None,
):
    return await CategoryService.list_categories(db, tenant_id=tenant_id, active_only=True)


@router.get(
    "/brands",
    response_model=list[BrandResponse],
    summary="List active brands for customer browsing",
)
@storefront_router.get(
    "/brands",
    response_model=list[BrandResponse],
    summary="List active brands for customer storefront",
)
async def list_public_brands(
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: Annotated[UUID | None, Query(description="Optional merchant filter")] = None,
):
    return await BrandService.list_brands(db, tenant_id=tenant_id, active_only=True)


@router.get(
    "/products",
    response_model=list[ProductDetailResponse],
    summary="Browse and search live published products",
)
@storefront_router.get(
    "/products",
    response_model=list[ProductDetailResponse],
    summary="Browse and search live published storefront products",
)
async def list_public_products(
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: Annotated[
        UUID | None, Query(description="Filter products by merchant organization")
    ] = None,
    category: Annotated[str | None, Query(description="Filter by category slug or ID")] = None,
    category_id: Annotated[str | None, Query(description="Filter by category ID")] = None,
    categoryId: Annotated[str | None, Query(description="Filter by category ID (frontend alias)")] = None,
    brand: Annotated[str | None, Query(description="Filter by brand slug or ID")] = None,
    brand_id: Annotated[str | None, Query(description="Filter by brand ID")] = None,
    brandId: Annotated[str | None, Query(description="Filter by brand ID (frontend alias)")] = None,
    search: Annotated[str | None, Query(description="Search products by title or keyword")] = None,
    page: Annotated[int | None, Query(ge=1, description="1-based page number")] = None,
    pageSize: Annotated[int | None, Query(ge=1, le=100, description="Items per page")] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    sortBy: Annotated[str | None, Query(description="Sorting option")] = None,
    sizes: Annotated[str | None, Query(description="Size filters")] = None,
    minPrice: Annotated[float | None, Query(description="Minimum price")] = None,
    maxPrice: Annotated[float | None, Query(description="Maximum price")] = None,
    inStockOnly: Annotated[bool | None, Query(description="Only in stock items")] = None,
):
    # Resolve category filter (support UUID or slug e.g. 'sarees', 'mens-wear')
    resolved_category_id: UUID | None = None
    raw_cat = category or category_id or categoryId
    if raw_cat and raw_cat.strip() and raw_cat.strip().upper() != "ALL":
        try:
            resolved_category_id = UUID(raw_cat.strip())
        except (ValueError, TypeError):
            cat_stmt = select(Category).where(Category.slug == raw_cat.strip().lower())
            found_cat = (await db.execute(cat_stmt)).scalar_one_or_none()
            if found_cat:
                resolved_category_id = found_cat.id

    # Resolve brand filter (support UUID or slug e.g. 'raymond', 'bagodi-atelier')
    resolved_brand_id: UUID | None = None
    raw_brand = brand or brand_id or brandId
    if raw_brand and raw_brand.strip() and raw_brand.strip().upper() != "ALL":
        try:
            resolved_brand_id = UUID(raw_brand.strip())
        except (ValueError, TypeError):
            brand_stmt = select(Brand).where(Brand.slug == raw_brand.strip().lower())
            found_brand = (await db.execute(brand_stmt)).scalar_one_or_none()
            if found_brand:
                resolved_brand_id = found_brand.id

    # Calculate effective pagination
    effective_limit = pageSize or limit
    effective_skip = skip
    if page and page > 1 and skip == 0:
        effective_skip = (page - 1) * effective_limit

    return await ProductService.list_public_products(
        db,
        tenant_id=tenant_id,
        category_id=resolved_category_id,
        brand_id=resolved_brand_id,
        search=search,
        skip=effective_skip,
        limit=effective_limit,
    )


@router.get(
    "/products/{slug}",
    response_model=ProductDetailResponse,
    summary="Get live published product details by slug",
)
@storefront_router.get(
    "/products/{slug}",
    response_model=ProductDetailResponse,
    summary="Get live published storefront product details by slug or ID",
)
async def get_public_product(
    slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    tenant_id: Annotated[UUID | None, Query(description="Optional merchant context")] = None,
):
    return await ProductService.get_public_product_by_slug(db, slug=slug, tenant_id=tenant_id)


# --- Public & Merchant Direct Product Management ---
@storefront_router.post(
    "/products",
    response_model=ProductDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an apparel product",
)
async def create_product_direct(
    data: ProductCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[SecurityPrincipal | None, Depends(get_optional_security_principal)] = None,
):
    # Resolve merchant tenant
    tenant_id: UUID | None = None
    if principal and principal.tenant_id:
        tenant_id = principal.tenant_id
    else:
        stmt = select(Tenant).order_by(Tenant.created_at.asc())
        active_tenant = (await db.execute(stmt)).scalars().first()
        if active_tenant:
            tenant_id = active_tenant.id
        else:
            new_tenant = Tenant(
                name="Bagodi Flagship Store",
                slug="bagodi-flagship",
                legal_name="Bagodi Retail Private Limited",
                status="active",
                contact_email="manager@bagodi.in",
                contact_phone="+919888877777",
            )
            db.add(new_tenant)
            await db.flush()
            tenant_id = new_tenant.id

    # Automatically activate and publish product created from web portals
    if data.status == "draft":
        data.status = "active"
    data.is_published = True

    # If no variants supplied, construct default variant from base_price or fallback
    if not data.variants:
        price = Decimal(str(data.base_price)) if data.base_price is not None else Decimal("1999.00")
        data.variants.append(
            ProductVariantCreate(
                name=f"{data.name} - Standard",
                size="FREE",
                color="Standard",
                mrp=price,
                base_price=price,
                initial_stock=10,
                status="active",
            )
        )

    product = await ProductService.create_product(db, tenant_id, data)
    return product


@storefront_router.put(
    "/products/{product_id}",
    response_model=ProductDetailResponse,
    summary="Update an apparel product",
)
@storefront_router.patch(
    "/products/{product_id}",
    response_model=ProductDetailResponse,
    summary="Patch an apparel product",
)
async def update_product_direct(
    product_id: UUID,
    data: ProductUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    stmt = (
        select(Product)
        .where(Product.id == product_id)
        .options(
            selectinload(Product.variants),
            selectinload(Product.images),
            selectinload(Product.category),
            selectinload(Product.brand),
        )
    )
    product = (await db.execute(stmt)).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    if data.name is not None:
        product.name = data.name
    if data.description is not None:
        product.description = data.description
    if data.category_id is not None:
        product.category_id = data.category_id
    if data.brand_id is not None:
        product.brand_id = data.brand_id
    if data.status is not None:
        product.status = data.status
    if data.is_published is not None:
        product.is_published = data.is_published

    if data.base_price is not None and product.variants:
        for v in product.variants:
            v.base_price = Decimal(str(data.base_price))
            if v.mrp and v.mrp < v.base_price:
                v.mrp = v.base_price

    if data.images is not None:
        for img in list(product.images):
            await db.delete(img)
        for img_data in data.images:
            new_img = ProductImage(
                tenant_id=product.tenant_id,
                product_id=product.id,
                url=img_data.url,
                alt_text=img_data.alt_text,
                sort_order=img_data.sort_order,
                is_primary=img_data.is_primary,
            )
            db.add(new_img)

    await db.commit()
    await db.refresh(product)
    await ProductService._attach_stock_balances(db, [product])
    return product


@storefront_router.delete(
    "/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archive or delete an apparel product",
)
async def delete_product_direct(
    product_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    stmt = select(Product).where(Product.id == product_id)
    product = (await db.execute(stmt)).scalar_one_or_none()
    if product:
        product.status = "archived"
        product.is_published = False
        await db.commit()


@storefront_router.post(
    "/variants",
    response_model=ProductVariantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a product variant",
)
async def create_variant_direct(
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[SecurityPrincipal | None, Depends(get_optional_security_principal)] = None,
):
    raw_prod_id = data.get("productId") or data.get("product_id")
    if not raw_prod_id:
        raise HTTPException(status_code=400, detail="productId is required")
    product_uuid = UUID(str(raw_prod_id))

    stmt = select(Product).where(Product.id == product_uuid)
    product = (await db.execute(stmt)).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    mrp_val = Decimal(str(data.get("mrp") or data.get("sellingPrice") or 1999))
    selling_price_val = Decimal(str(data.get("sellingPrice") or mrp_val))

    variant_create = ProductVariantCreate(
        sku=data.get("sku"),
        barcode=data.get("barcode"),
        name=data.get("name") or f"{data.get('size', 'Standard')} - {data.get('colorName', 'Standard')}",
        size=data.get("size"),
        color=data.get("colorName") or data.get("color"),
        mrp=mrp_val,
        base_price=selling_price_val,
        initial_stock=int(data.get("initialStock", 0)),
        status="active",
    )
    return await ProductService.add_variant(db, product.tenant_id, product.id, variant_create)


@storefront_router.delete(
    "/variants/{variant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a product variant",
)
async def delete_variant_direct(
    variant_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    stmt = select(ProductVariant).where(ProductVariant.id == variant_id)
    variant = (await db.execute(stmt)).scalar_one_or_none()
    if variant:
        await db.delete(variant)
        await db.commit()
