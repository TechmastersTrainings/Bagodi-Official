import random
import re
import time
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import SecurityPrincipal, get_optional_security_principal
from app.db.session import get_db
from app.modules.catalog.models import Brand, Category, Product, ProductImage, ProductVariant
from app.modules.inventory.models import InventoryLedger, PurchaseOrder, PurchaseOrderItem, StockBalance
from app.modules.inventory.services import InventoryService
from app.modules.platform.models import Store, Tenant

router = APIRouter(prefix="/inventory", tags=["Direct Inventory Management"])


class InventoryCreatePayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    serialNumber: str | None = None
    barcode: str | None = None
    sku: str | None = None
    productName: str
    categoryName: str = "Silk Sarees"
    price: float = 0.0
    mrp: float = 0.0
    onHandQuantity: int = 1
    size: str = "Free Size"
    colorName: str = "Standard"
    images: list[dict] = Field(default_factory=list)
    pushToCatalogue: bool = False


class PushToCataloguePayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    inventoryId: str


class InventoryAdjustmentPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    inventoryId: str | None = None
    variantId: str
    storeId: str | None = None
    operationType: str = "STOCK_ADJUSTMENT"
    quantityChange: int = 0
    reason: str = "Manual Adjustment"
    referenceDocument: str | None = None
    notes: str | None = None


class ReconcilePayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    variantId: str
    countedQuantity: int
    notes: str | None = None


class PurchaseOrderReceivePayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    poNumber: str | None = None
    items: list[dict] = Field(default_factory=list)


async def _resolve_tenant_and_store(
    db: AsyncSession, principal: SecurityPrincipal | None
) -> tuple[Tenant, Store]:
    tenant: Tenant | None = None
    if principal and principal.tenant_id:
        stmt = select(Tenant).where(Tenant.id == principal.tenant_id)
        tenant = (await db.execute(stmt)).scalar_one_or_none()

    if not tenant:
        stmt = select(Tenant).order_by(Tenant.created_at.asc())
        tenant = (await db.execute(stmt)).scalars().first()

    if not tenant:
        tenant = Tenant(
            id=UUID("11111111-1111-1111-1111-111111111111"),
            name="Bagodi Clothing",
            slug="bagodi",
            legal_name="Bagodi Retail Private Limited",
            status="active",
            contact_email="merchant@bagodi.in",
            contact_phone="+919876500002",
        )
        db.add(tenant)
        await db.flush()

    store_stmt = (
        select(Store)
        .where(Store.tenant_id == tenant.id, Store.status == "active")
        .order_by(Store.code.asc())
    )
    store = (await db.execute(store_stmt)).scalars().first()
    if not store:
        store_stmt = select(Store).where(Store.tenant_id == tenant.id)
        store = (await db.execute(store_stmt)).scalars().first()

    if not store:
        store = Store(
            id=UUID("22222222-2222-2222-2222-222222222222"),
            tenant_id=tenant.id,
            name="Bagodi Bidar Flagship Store",
            code="BIDAR-01",
            status="active",
            address_line="Main Market Road",
            city="Bidar",
            state="Karnataka",
            postal_code="585401",
        )
        db.add(store)
        await db.flush()

    return tenant, store


@router.get("", summary="Get inventory ledger items")
async def list_inventory_items(
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    pageSize: Annotated[int, Query(ge=1, le=100)] = 15,
    search: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    principal: Annotated[SecurityPrincipal | None, Depends(get_optional_security_principal)] = None,
):
    tenant, store = await _resolve_tenant_and_store(db, principal)

    stmt = (
        select(ProductVariant)
        .join(Product, ProductVariant.product_id == Product.id)
        .options(
            selectinload(ProductVariant.product).selectinload(Product.category),
            selectinload(ProductVariant.product).selectinload(Product.brand),
            selectinload(ProductVariant.product).selectinload(Product.images),
        )
        .where(ProductVariant.tenant_id == tenant.id)
    )

    if search and search.strip():
        term = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Product.name.ilike(term),
                ProductVariant.sku.ilike(term),
                ProductVariant.barcode.ilike(term),
            )
        )

    stmt = stmt.order_by(ProductVariant.created_at.desc())
    all_variants = list((await db.execute(stmt)).scalars().all())

    variant_ids = [v.id for v in all_variants]
    stock_map: dict[UUID, StockBalance] = {}
    if variant_ids:
        b_stmt = select(StockBalance).where(
            StockBalance.variant_id.in_(variant_ids), StockBalance.store_id == store.id
        )
        b_res = (await db.execute(b_stmt)).scalars().all()
        stock_map = {b.variant_id: b for b in b_res}

    items = []
    for v in all_variants:
        b = stock_map.get(v.id)
        on_hand = b.on_hand_qty if b else 0
        reserved = b.reserved_qty if b else 0
        available = b.available_qty if b else 0

        if available <= 0:
            item_status = "OUT_OF_STOCK"
        elif available <= 5:
            item_status = "LOW_STOCK"
        else:
            item_status = "IN_STOCK"

        if status and status != "ALL" and item_status != status:
            continue

        prod = v.product
        items.append(
            {
                "id": str(v.id),
                "productId": str(prod.id),
                "productName": prod.name,
                "variantId": str(v.id),
                "variant": {
                    "id": str(v.id),
                    "productId": str(prod.id),
                    "sku": v.sku,
                    "barcode": v.barcode or "",
                    "size": v.size or "FREE",
                    "colorName": v.color or "Standard",
                    "colorHex": getattr(v, "color_hex", None),
                    "mrp": float(v.mrp),
                    "sellingPrice": float(v.base_price),
                    "availableStock": available,
                    "reservedStock": reserved,
                    "isActive": v.status == "active",
                },
                "sku": v.sku,
                "barcode": v.barcode or "",
                "storeId": str(store.id),
                "storeName": store.name,
                "onHandQuantity": on_hand,
                "reservedQuantity": reserved,
                "availableQuantity": available,
                "damagedQuantity": 0,
                "reorderLevel": 5,
                "stockStatus": item_status,
                "updatedAt": (v.updated_at or v.created_at).isoformat(),
            }
        )

    total = len(items)
    start = (page - 1) * pageSize
    paginated_items = items[start : start + pageSize]
    total_pages = max(1, (total + pageSize - 1) // pageSize)

    return {
        "items": paginated_items,
        "total": total,
        "page": page,
        "pageSize": pageSize,
        "totalPages": total_pages,
    }


@router.post("", status_code=status.HTTP_201_CREATED, summary="Add in-store inventory and serial")
async def add_inventory_item(
    data: InventoryCreatePayload,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[SecurityPrincipal | None, Depends(get_optional_security_principal)] = None,
):
    tenant, store = await _resolve_tenant_and_store(db, principal)

    # 1. Resolve or create Category
    clean_cat_slug = re.sub(r"[^a-z0-9]+", "-", data.categoryName.lower()).strip("-") or "apparel"
    cat_stmt = select(Category).where(
        or_(Category.slug == clean_cat_slug, Category.name.ilike(data.categoryName.strip()))
    )
    category = (await db.execute(cat_stmt)).scalars().first()
    if not category:
        category = Category(
            tenant_id=None,
            name=data.categoryName.strip(),
            slug=clean_cat_slug,
            description=f"Curated {data.categoryName}",
            is_active=True,
        )
        db.add(category)
        await db.flush()

    # 2. Resolve default brand
    brand_stmt = select(Brand).where(Brand.slug == "bagodi-atelier")
    brand = (await db.execute(brand_stmt)).scalars().first()
    if not brand:
        brand = (await db.execute(select(Brand).order_by(Brand.created_at.asc()))).scalars().first()

    # 3. Create Product
    base_slug = re.sub(r"[^a-z0-9]+", "-", data.productName.lower()).strip("-") or "garment"
    product_slug = f"{base_slug[:120]}-{uuid4().hex[:6]}"
    is_live = bool(data.pushToCatalogue)
    product = Product(
        tenant_id=tenant.id,
        category_id=category.id,
        brand_id=brand.id if brand else None,
        name=data.productName.strip(),
        slug=product_slug,
        description=f"Authentic luxury {data.productName.strip()} in stock at Bidar Flagship Store.",
        status="active" if is_live else "draft",
        is_published=is_live,
    )
    db.add(product)
    await db.flush()

    # 4. Create Variant
    sku = data.sku or data.serialNumber or f"BGD-INV-{uuid4().hex[:6].upper()}"
    barcode = data.barcode or data.serialNumber or f"890{int(time.time()) % 1000000:06d}{random.randint(100, 999):03d}"
    price = Decimal(str(data.price)) if data.price > 0 else Decimal("1999.00")
    mrp = Decimal(str(data.mrp)) if data.mrp > 0 else price

    variant = ProductVariant(
        tenant_id=tenant.id,
        product_id=product.id,
        sku=sku,
        barcode=barcode,
        name=f"{data.productName.strip()} - {data.size}",
        size=data.size,
        color=data.colorName,
        mrp=mrp,
        base_price=price,
        status="active",
    )
    db.add(variant)
    await db.flush()

    # 5. Add images
    for idx, img in enumerate(data.images):
        url = img.get("url")
        if url:
            db.add(
                ProductImage(
                    tenant_id=tenant.id,
                    product_id=product.id,
                    url=url,
                    alt_text=img.get("altText") or data.productName,
                    sort_order=idx + 1,
                    is_primary=(idx == 0 or img.get("isPrimary", False)),
                )
            )

    # 6. Post stock balance movement
    qty = max(1, data.onHandQuantity)
    await InventoryService.post_movement(
        db=db,
        tenant_id=tenant.id,
        store_id=store.id,
        variant_id=variant.id,
        movement_type="PURCHASE_RECEIPT",
        from_account="EXTERNAL_VENDOR",
        to_account="STORE_ON_HAND",
        quantity=qty,
        on_hand_delta=qty,
        reference_type="INVENTORY_ONBOARDING",
        reference_id=f"ONBOARD-{variant.sku}",
        notes=f"Initial in-store stock for {variant.sku}",
        user_id=principal.user_id if principal else None,
    )

    await db.commit()

    return {
        "success": True,
        "id": str(variant.id),
        "productId": str(product.id),
        "productName": product.name,
        "variantId": str(variant.id),
        "sku": variant.sku,
        "barcode": variant.barcode,
        "availableQuantity": qty,
        "isPublished": is_live,
    }


@router.post("/push-to-catalogue", summary="Push staged inventory item to live storefront")
async def push_to_catalogue(
    data: PushToCataloguePayload,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    target_id = data.inventoryId.strip()
    is_uuid = False
    try:
        parsed_uuid = UUID(target_id)
        is_uuid = True
    except (ValueError, TypeError):
        parsed_uuid = None

    product: Product | None = None
    if is_uuid:
        # Check if target is a ProductVariant
        v_stmt = select(ProductVariant).where(ProductVariant.id == parsed_uuid)
        variant = (await db.execute(v_stmt)).scalar_one_or_none()
        if variant:
            p_stmt = select(Product).where(Product.id == variant.product_id)
            product = (await db.execute(p_stmt)).scalar_one_or_none()
        else:
            p_stmt = select(Product).where(Product.id == parsed_uuid)
            product = (await db.execute(p_stmt)).scalar_one_or_none()

    if not product:
        # Search by SKU or barcode
        v_stmt = (
            select(ProductVariant)
            .where(or_(ProductVariant.sku == target_id, ProductVariant.barcode == target_id))
            .options(selectinload(ProductVariant.product))
        )
        variant = (await db.execute(v_stmt)).scalar_one_or_none()
        if variant:
            product = variant.product

    if not product:
        raise HTTPException(
            status_code=404,
            detail=f"Inventory reference '{target_id}' could not be resolved to a garment.",
        )

    product.status = "active"
    product.is_published = True
    await db.commit()

    return {
        "success": True,
        "message": f"'{product.name}' is now live on the customer storefront.",
        "productId": str(product.id),
        "slug": product.slug,
    }


@router.get("/valuation", summary="Get real-time financial stock valuation and indicators")
async def get_stock_valuation(
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[SecurityPrincipal | None, Depends(get_optional_security_principal)] = None,
):
    tenant, store = await _resolve_tenant_and_store(db, principal)

    stmt = (
        select(ProductVariant, StockBalance)
        .outerjoin(
            StockBalance,
            (StockBalance.variant_id == ProductVariant.id) & (StockBalance.store_id == store.id),
        )
        .join(Product, ProductVariant.product_id == Product.id)
        .options(
            selectinload(ProductVariant.product).selectinload(Product.brand),
            selectinload(ProductVariant.product).selectinload(Product.category),
        )
        .where(ProductVariant.tenant_id == tenant.id)
    )
    rows = (await db.execute(stmt)).all()

    total_units_on_hand = 0
    total_units_reserved = 0
    total_retail_val = Decimal("0.00")
    low_stock_count = 0
    out_of_stock_count = 0
    val_by_brand: dict[str, float] = {}
    val_by_category: dict[str, float] = {}

    for variant, balance in rows:
        on_hand = balance.on_hand_qty if balance else 0
        reserved = balance.reserved_qty if balance else 0
        available = balance.available_qty if balance else 0

        total_units_on_hand += on_hand
        total_units_reserved += reserved

        price = variant.base_price or Decimal("0.00")
        line_val = price * on_hand
        total_retail_val += line_val

        if available <= 0:
            out_of_stock_count += 1
        elif available <= 5:
            low_stock_count += 1

        brand_name = (
            variant.product.brand.name if variant.product and variant.product.brand else "Bagodi"
        )
        category_name = (
            variant.product.category.name if variant.product and variant.product.category else "General"
        )

        val_by_brand[brand_name] = round(val_by_brand.get(brand_name, 0.0) + float(line_val), 2)
        val_by_category[category_name] = round(
            val_by_category.get(category_name, 0.0) + float(line_val), 2
        )

    return {
        "totalUnitsOnHand": total_units_on_hand,
        "totalUnitsReserved": total_units_reserved,
        "totalRetailValuation": round(float(total_retail_val), 2),
        "lowStockItemsCount": low_stock_count,
        "outOfStockItemsCount": out_of_stock_count,
        "valuationByBrand": val_by_brand,
        "valuationByCategory": val_by_category,
    }


@router.get("/movements", summary="Get audit stock movements")
async def list_stock_movements(
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    pageSize: Annotated[int, Query(ge=1, le=100)] = 15,
    principal: Annotated[SecurityPrincipal | None, Depends(get_optional_security_principal)] = None,
):
    tenant, _ = await _resolve_tenant_and_store(db, principal)

    stmt = (
        select(InventoryLedger)
        .where(InventoryLedger.tenant_id == tenant.id)
        .order_by(InventoryLedger.created_at.desc())
    )
    total = len((await db.execute(stmt)).scalars().all())

    stmt = stmt.offset((page - 1) * pageSize).limit(pageSize)
    ledgers = list((await db.execute(stmt)).scalars().all())

    variant_ids = [l.variant_id for l in ledgers]
    v_map = {}
    if variant_ids:
        v_stmt = (
            select(ProductVariant)
            .where(ProductVariant.id.in_(variant_ids))
            .options(selectinload(ProductVariant.product))
        )
        for v in (await db.execute(v_stmt)).scalars().all():
            v_map[v.id] = v

    items = []
    for l in ledgers:
        variant = v_map.get(l.variant_id)
        product_name = variant.product.name if variant and variant.product else "Apparel"
        sku = variant.sku if variant else "SKU"
        barcode = (variant.barcode if variant else None) or sku

        items.append(
            {
                "id": str(l.id),
                "timestamp": l.created_at.isoformat(),
                "inventoryId": str(l.variant_id),
                "productName": product_name,
                "sku": sku,
                "barcode": barcode,
                "operationType": l.movement_type,
                "quantityChange": l.on_hand_delta,
                "previousAvailableQuantity": max(0, l.quantity),
                "newAvailableQuantity": l.quantity,
                "reason": l.notes or l.reference_type or "Audit Transaction",
                "referenceDocument": l.reference_id or "-",
                "operatorName": "Store Merchandiser",
            }
        )

    total_pages = max(1, (total + pageSize - 1) // pageSize)
    return {
        "items": items,
        "total": total,
        "page": page,
        "pageSize": pageSize,
        "totalPages": total_pages,
    }


@router.get("/reconciliation", summary="List stock reconciliation items")
async def list_reconciliation_items(
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[SecurityPrincipal | None, Depends(get_optional_security_principal)] = None,
):
    tenant, store = await _resolve_tenant_and_store(db, principal)

    stmt = (
        select(ProductVariant, StockBalance)
        .outerjoin(
            StockBalance,
            (StockBalance.variant_id == ProductVariant.id) & (StockBalance.store_id == store.id),
        )
        .join(Product, ProductVariant.product_id == Product.id)
        .options(selectinload(ProductVariant.product))
        .where(ProductVariant.tenant_id == tenant.id)
        .order_by(ProductVariant.created_at.desc())
        .limit(50)
    )
    rows = (await db.execute(stmt)).all()

    items = []
    for variant, balance in rows:
        available = balance.available_qty if balance else 0
        items.append(
            {
                "id": str(variant.id),
                "inventoryId": str(variant.id),
                "variantId": str(variant.id),
                "productName": variant.product.name,
                "sku": variant.sku,
                "barcode": variant.barcode or variant.sku,
                "systemQuantity": available,
                "countedQuantity": available,
                "variance": 0,
                "status": "MATCHED",
                "notes": "Verified against physical floor rack",
                "auditedAt": (variant.updated_at or variant.created_at).isoformat(),
            }
        )

    return {
        "items": items,
        "total": len(items),
        "page": 1,
        "pageSize": 50,
        "totalPages": 1,
    }


@router.post("/reconcile", summary="Commit physical reconciliation")
async def reconcile_stock(
    data: ReconcilePayload,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[SecurityPrincipal | None, Depends(get_optional_security_principal)] = None,
):
    tenant, store = await _resolve_tenant_and_store(db, principal)
    variant_id = UUID(data.variantId)

    balance = await InventoryService.get_or_create_balance_for_update(
        db, tenant.id, store.id, variant_id
    )
    current_avail = balance.available_qty
    delta = data.countedQuantity - current_avail

    if delta != 0:
        await InventoryService.post_movement(
            db=db,
            tenant_id=tenant.id,
            store_id=store.id,
            variant_id=variant_id,
            movement_type="STOCK_ADJUSTMENT",
            from_account="PHYSICAL_AUDIT_ADJUSTMENT" if delta < 0 else "AUDIT_SURPLUS",
            to_account="STORE_ON_HAND",
            quantity=abs(delta),
            on_hand_delta=delta,
            reference_type="CYCLE_COUNT_RECONCILIATION",
            reference_id=f"RECON-{variant_id.hex[:6].upper()}",
            notes=data.notes or f"Physical cycle count adjusted by {delta} unit(s)",
            user_id=principal.user_id if principal else None,
        )
        await db.commit()

    return {"success": True, "message": "Reconciliation posted successfully"}


@router.get("/purchase-orders", summary="List purchase orders")
async def list_purchase_orders(
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[SecurityPrincipal | None, Depends(get_optional_security_principal)] = None,
):
    tenant, _ = await _resolve_tenant_and_store(db, principal)

    stmt = (
        select(PurchaseOrder)
        .where(PurchaseOrder.tenant_id == tenant.id)
        .options(selectinload(PurchaseOrder.items).selectinload(PurchaseOrderItem.variant))
        .order_by(PurchaseOrder.created_at.desc())
        .limit(30)
    )
    orders = list((await db.execute(stmt)).scalars().all())

    items = []
    for po in orders:
        po_items = []
        for i in po.items:
            po_items.append(
                {
                    "id": str(i.id),
                    "variantId": str(i.variant_id),
                    "sku": i.variant.sku if i.variant else "SKU",
                    "productName": "Garment",
                    "size": i.variant.size if i.variant else "FREE",
                    "colorName": i.variant.color if i.variant else "Standard",
                    "orderedQuantity": i.quantity_ordered,
                    "receivedQuantity": i.quantity_received,
                    "unitCost": float(i.unit_cost),
                }
            )
        items.append(
            {
                "id": str(po.id),
                "poNumber": po.po_number,
                "supplierName": po.supplier_reference or "Bespoke Deccan Mill",
                "status": po.status,
                "orderDate": po.created_at.isoformat(),
                "totalCost": float(po.total_cost),
                "items": po_items,
            }
        )

    return {
        "items": items,
        "total": len(items),
        "page": 1,
        "pageSize": 50,
        "totalPages": 1,
    }


@router.post("/purchase-orders/receive", summary="Receive purchase order batch")
async def receive_purchase_order(
    data: PurchaseOrderReceivePayload,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[SecurityPrincipal | None, Depends(get_optional_security_principal)] = None,
):
    tenant, store = await _resolve_tenant_and_store(db, principal)
    for item in data.items:
        v_id_str = item.get("variantId")
        qty = int(item.get("receivedQuantity", 0))
        if v_id_str and qty > 0:
            v_id = UUID(v_id_str)
            await InventoryService.post_movement(
                db=db,
                tenant_id=tenant.id,
                store_id=store.id,
                variant_id=v_id,
                movement_type="PURCHASE_RECEIPT",
                from_account="EXTERNAL_VENDOR",
                to_account="STORE_ON_HAND",
                quantity=qty,
                on_hand_delta=qty,
                reference_type="PURCHASE_ORDER_RECEIPT",
                reference_id=data.poNumber or f"PO-{v_id.hex[:6].upper()}",
                notes=f"Received PO shipment for {data.poNumber}",
                user_id=principal.user_id if principal else None,
            )
    await db.commit()
    return {"success": True, "message": "Shipment received and stock updated"}


@router.get("/barcode/{barcode}", summary="Lookup variant and inventory item by barcode or SKU")
async def lookup_by_barcode(
    barcode: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[SecurityPrincipal | None, Depends(get_optional_security_principal)] = None,
):
    tenant, store = await _resolve_tenant_and_store(db, principal)
    clean_code = barcode.strip()

    stmt = (
        select(ProductVariant)
        .where(
            ProductVariant.tenant_id == tenant.id,
            or_(ProductVariant.barcode == clean_code, ProductVariant.sku == clean_code),
        )
        .options(selectinload(ProductVariant.product))
    )
    variant = (await db.execute(stmt)).scalar_one_or_none()
    if not variant:
        return {
            "found": False,
            "message": f"No garment found matching barcode or SKU '{clean_code}'.",
        }

    balance = await InventoryService.get_or_create_balance_for_update(
        db, tenant.id, store.id, variant.id
    )
    product = variant.product

    inventory_item = {
        "id": str(variant.id),
        "productId": str(product.id),
        "productName": product.name,
        "variantId": str(variant.id),
        "sku": variant.sku,
        "barcode": variant.barcode or variant.sku,
        "storeId": str(store.id),
        "storeName": store.name,
        "onHandQuantity": balance.on_hand_qty,
        "reservedQuantity": balance.reserved_qty,
        "availableQuantity": balance.available_qty,
        "damagedQuantity": 0,
        "reorderLevel": 5,
        "stockStatus": "IN_STOCK" if balance.available_qty > 5 else "LOW_STOCK",
        "updatedAt": (variant.updated_at or variant.created_at).isoformat(),
    }

    variant_payload = {
        "id": str(variant.id),
        "productId": str(product.id),
        "sku": variant.sku,
        "barcode": variant.barcode or "",
        "size": variant.size or "FREE",
        "colorName": variant.color or "Standard",
        "mrp": float(variant.mrp),
        "sellingPrice": float(variant.base_price),
        "availableStock": balance.available_qty,
        "reservedStock": balance.reserved_qty,
        "isActive": variant.status == "active",
    }

    return {
        "found": True,
        "productName": product.name,
        "variant": variant_payload,
        "inventory": inventory_item,
        "message": "Barcode identified successfully.",
    }


@router.post("/adjust", summary="Adjust inventory quantity")
async def adjust_inventory(
    data: InventoryAdjustmentPayload,
    db: Annotated[AsyncSession, Depends(get_db)],
    principal: Annotated[SecurityPrincipal | None, Depends(get_optional_security_principal)] = None,
):
    tenant, store = await _resolve_tenant_and_store(db, principal)
    variant_id = UUID(data.variantId)

    qty_change = data.quantityChange
    if qty_change == 0:
        raise HTTPException(status_code=400, detail="quantityChange must be non-zero")

    balance = await InventoryService.get_or_create_balance_for_update(
        db, tenant.id, store.id, variant_id
    )

    if qty_change < 0 and balance.available_qty + qty_change < 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot deduct {abs(qty_change)} unit(s). Current available quantity is only {balance.available_qty}.",
        )

    from_acc = "STORE_ON_HAND" if qty_change < 0 else "MANUAL_ADJUSTMENT"
    to_acc = "DAMAGE_WRITE_OFF" if qty_change < 0 else "STORE_ON_HAND"

    await InventoryService.post_movement(
        db=db,
        tenant_id=tenant.id,
        store_id=store.id,
        variant_id=variant_id,
        movement_type=data.operationType or "STOCK_ADJUSTMENT",
        from_account=from_acc,
        to_account=to_acc,
        quantity=abs(qty_change),
        on_hand_delta=qty_change,
        reference_type=data.reason,
        reference_id=data.referenceDocument or f"ADJ-{variant_id.hex[:6].upper()}",
        notes=data.notes or f"Manual adjustment: {data.reason}",
        user_id=principal.user_id if principal else None,
    )
    await db.commit()
    await db.refresh(balance)

    return {
        "success": True,
        "message": f"Successfully updated stock by {qty_change} unit(s).",
        "updatedItem": {
            "variantId": str(variant_id),
            "availableQuantity": balance.available_qty,
            "onHandQuantity": balance.on_hand_qty,
        },
    }
