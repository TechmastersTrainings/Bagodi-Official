from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import SecurityPrincipal, get_security_principal, require_permission
from app.core.tenant import TenantContext, get_current_tenant
from app.db.session import get_db
from app.modules.inventory.schemas import (
    CustomerReturnCreate,
    InventoryLedgerResponse,
    PurchaseOrderCreate,
    PurchaseOrderResponse,
    StockAdjustmentCreate,
    StockBalanceResponse,
    StockDispatchCreate,
    StockReceiptCreate,
    StockReceiptResponse,
    StockReservationCreate,
    StockReservationRelease,
    StoreTransferCreate,
    StoreTransferReceive,
    StoreTransferResponse,
    SupplierCreate,
    SupplierResponse,
    SupplierUpdate,
)
from app.modules.inventory.services import (
    InventoryService,
    PurchaseOrderService,
    StoreTransferService,
    SupplierService,
)

router = APIRouter(prefix="/merchant/inventory", tags=["Merchant Inventory Engine"])


# --- Stock Balances ---
@router.get(
    "/balances",
    response_model=list[StockBalanceResponse],
    summary="Query real-time stock balances across stores and variants",
    dependencies=[Depends(require_permission("inventory.balances.read"))],
)
async def list_stock_balances(
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
    store_id: Annotated[
        UUID | None, Query(description="Filter by physical or virtual store")
    ] = None,
    variant_id: Annotated[
        UUID | None, Query(description="Filter by specific product variant")
    ] = None,
    low_stock_only: Annotated[
        bool, Query(description="Filter items at or below reorder threshold")
    ] = False,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return await InventoryService.list_balances(
        db,
        tenant_id=tenant.tenant_id,
        store_id=store_id,
        variant_id=variant_id,
        low_stock_only=low_stock_only,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/balances/{store_id}/{variant_id}",
    response_model=StockBalanceResponse,
    summary="Get exact real-time balance for a specific store and variant",
    dependencies=[Depends(require_permission("inventory.balances.read"))],
)
async def get_stock_balance(
    store_id: UUID,
    variant_id: UUID,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await InventoryService.get_balance(
        db, tenant_id=tenant.tenant_id, store_id=store_id, variant_id=variant_id
    )


# --- Immutable Audit Ledger ---
@router.get(
    "/ledger",
    response_model=list[InventoryLedgerResponse],
    summary="Query audit-grade immutable double-entry stock ledger history",
    dependencies=[Depends(require_permission("inventory.ledger.read"))],
)
async def list_inventory_ledger(
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
    store_id: Annotated[UUID | None, Query(description="Filter by store")] = None,
    variant_id: Annotated[UUID | None, Query(description="Filter by variant")] = None,
    movement_type: Annotated[
        str | None, Query(description="Filter by ledger movement type")
    ] = None,
    reference_id: Annotated[
        str | None, Query(description="Filter by order/PO/transfer reference ID")
    ] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return await InventoryService.list_ledger(
        db,
        tenant_id=tenant.tenant_id,
        store_id=store_id,
        variant_id=variant_id,
        movement_type=movement_type,
        reference_id=reference_id,
        skip=skip,
        limit=limit,
    )


# --- Core Stock Movements ---
@router.post(
    "/reservations",
    response_model=InventoryLedgerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Reserve stock for customer order or cart hold",
    dependencies=[Depends(require_permission("inventory.reserve"))],
)
async def reserve_stock(
    data: StockReservationCreate,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    entry, _ = await InventoryService.reserve_stock(
        db, tenant_id=tenant.tenant_id, data=data, user_id=principal.user_id
    )
    return entry


@router.post(
    "/reservations/release",
    response_model=InventoryLedgerResponse,
    status_code=status.HTTP_200_OK,
    summary="Release previously reserved stock back to available pool",
    dependencies=[Depends(require_permission("inventory.reserve"))],
)
async def release_reservation(
    data: StockReservationRelease,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    entry, _ = await InventoryService.release_reservation(
        db, tenant_id=tenant.tenant_id, data=data, user_id=principal.user_id
    )
    return entry


@router.post(
    "/dispatch",
    response_model=InventoryLedgerResponse,
    status_code=status.HTTP_200_OK,
    summary="Commit physical dispatch and fulfillment of reserved stock",
    dependencies=[Depends(require_permission("inventory.dispatch"))],
)
async def dispatch_stock(
    data: StockDispatchCreate,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    entry, _ = await InventoryService.dispatch_stock(
        db, tenant_id=tenant.tenant_id, data=data, user_id=principal.user_id
    )
    return entry


@router.post(
    "/returns",
    response_model=InventoryLedgerResponse,
    status_code=status.HTTP_200_OK,
    summary="Process customer return accepted back into store inventory",
    dependencies=[Depends(require_permission("inventory.adjust"))],
)
async def return_customer_stock(
    data: CustomerReturnCreate,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    entry, _ = await InventoryService.return_customer_stock(
        db, tenant_id=tenant.tenant_id, data=data, user_id=principal.user_id
    )
    return entry


@router.post(
    "/adjustments",
    response_model=InventoryLedgerResponse,
    status_code=status.HTTP_200_OK,
    summary="Record manual stock adjustment (damage, loss, cycle count reconciliation)",
    dependencies=[Depends(require_permission("inventory.adjust"))],
)
async def adjust_stock(
    data: StockAdjustmentCreate,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    entry, _ = await InventoryService.adjust_stock(
        db, tenant_id=tenant.tenant_id, data=data, user_id=principal.user_id
    )
    return entry


# --- Suppliers ---
@router.post(
    "/suppliers",
    response_model=SupplierResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a procurement supplier",
    dependencies=[Depends(require_permission("inventory.suppliers.create"))],
)
async def create_supplier(
    data: SupplierCreate,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await SupplierService.create_supplier(db, tenant.tenant_id, data)


@router.get(
    "/suppliers",
    response_model=list[SupplierResponse],
    summary="List procurement suppliers",
    dependencies=[Depends(require_permission("inventory.suppliers.read"))],
)
async def list_suppliers(
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
    active_only: Annotated[bool, Query()] = False,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return await SupplierService.list_suppliers(db, tenant.tenant_id, active_only, skip, limit)


@router.get(
    "/suppliers/{supplier_id}",
    response_model=SupplierResponse,
    summary="Get supplier details",
    dependencies=[Depends(require_permission("inventory.suppliers.read"))],
)
async def get_supplier(
    supplier_id: UUID,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await SupplierService.get_supplier(db, tenant.tenant_id, supplier_id)


@router.patch(
    "/suppliers/{supplier_id}",
    response_model=SupplierResponse,
    summary="Update supplier contact details or status",
    dependencies=[Depends(require_permission("inventory.suppliers.update"))],
)
async def update_supplier(
    supplier_id: UUID,
    data: SupplierUpdate,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await SupplierService.update_supplier(db, tenant.tenant_id, supplier_id, data)


# --- Purchase Orders & Stock Receipts ---
@router.post(
    "/purchase-orders",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a purchase order for procurement (does NOT alter stock)",
    dependencies=[Depends(require_permission("inventory.po.create"))],
)
async def create_purchase_order(
    data: PurchaseOrderCreate,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await PurchaseOrderService.create_purchase_order(
        db, tenant.tenant_id, data, principal.user_id
    )


@router.get(
    "/purchase-orders",
    response_model=list[PurchaseOrderResponse],
    summary="List purchase orders",
    dependencies=[Depends(require_permission("inventory.po.read"))],
)
async def list_purchase_orders(
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
    store_id: Annotated[UUID | None, Query()] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return await PurchaseOrderService.list_purchase_orders(
        db, tenant.tenant_id, store_id, status_filter, skip, limit
    )


@router.get(
    "/purchase-orders/{po_id}",
    response_model=PurchaseOrderResponse,
    summary="Get purchase order details and line items",
    dependencies=[Depends(require_permission("inventory.po.read"))],
)
async def get_purchase_order(
    po_id: UUID,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await PurchaseOrderService.get_purchase_order(db, tenant.tenant_id, po_id)


@router.post(
    "/receipts",
    response_model=StockReceiptResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Accept inward stock receipt (atomically posts PURCHASE_RECEIPT ledger records)",
    dependencies=[Depends(require_permission("inventory.receipt.create"))],
)
async def receive_goods(
    data: StockReceiptCreate,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await PurchaseOrderService.receive_goods(db, tenant.tenant_id, data, principal.user_id)


# --- Store Transfers ---
@router.post(
    "/transfers",
    response_model=StoreTransferResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate and dispatch stock transfer between stores (places stock in-transit)",
    dependencies=[Depends(require_permission("inventory.transfers.create"))],
)
async def create_transfer(
    data: StoreTransferCreate,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await StoreTransferService.create_and_dispatch_transfer(
        db, tenant.tenant_id, data, principal.user_id
    )


@router.get(
    "/transfers",
    response_model=list[StoreTransferResponse],
    summary="List store transfers",
    dependencies=[Depends(require_permission("inventory.transfers.read"))],
)
async def list_transfers(
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
    store_id: Annotated[
        UUID | None, Query(description="Filter by source or destination store")
    ] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return await StoreTransferService.list_transfers(
        db, tenant.tenant_id, store_id, status_filter, skip, limit
    )


@router.get(
    "/transfers/{transfer_id}",
    response_model=StoreTransferResponse,
    summary="Get store transfer details",
    dependencies=[Depends(require_permission("inventory.transfers.read"))],
)
async def get_transfer(
    transfer_id: UUID,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await StoreTransferService.get_transfer(db, tenant.tenant_id, transfer_id)


@router.post(
    "/transfers/{transfer_id}/receive",
    response_model=StoreTransferResponse,
    status_code=status.HTTP_200_OK,
    summary="Receive inbound store transfer at destination store (relieves in-transit, adds to on-hand)",
    dependencies=[Depends(require_permission("inventory.transfers.receive"))],
)
async def receive_transfer(
    transfer_id: UUID,
    data: StoreTransferReceive,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await StoreTransferService.receive_transfer(
        db, tenant.tenant_id, transfer_id, data, principal.user_id
    )
