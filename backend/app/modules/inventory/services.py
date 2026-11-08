from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.catalog.models import ProductVariant
from app.modules.identity.models import User
from app.modules.inventory.models import (
    InventoryLedger,
    PurchaseOrder,
    PurchaseOrderItem,
    StockBalance,
    StockReceipt,
    StockReceiptItem,
    StoreTransfer,
    StoreTransferItem,
    Supplier,
)
from app.modules.inventory.schemas import (
    CustomerReturnCreate,
    PurchaseOrderCreate,
    StockAdjustmentCreate,
    StockDispatchCreate,
    StockReceiptCreate,
    StockReservationCreate,
    StockReservationRelease,
    StoreTransferCreate,
    StoreTransferReceive,
    SupplierCreate,
    SupplierUpdate,
)
from app.modules.platform.models import Store


async def _resolve_user_id(db: AsyncSession, user_id: UUID | None) -> UUID | None:
    if not user_id:
        return None
    exists = (await db.execute(select(User.id).where(User.id == user_id))).scalar_one_or_none()
    return user_id if exists else None


class InventoryService:
    @staticmethod
    async def get_or_create_balance_for_update(
        db: AsyncSession,
        tenant_id: UUID,
        store_id: UUID,
        variant_id: UUID,
    ) -> StockBalance:
        """Lock and return the stock balance row for (tenant_id, store_id, variant_id).

        Uses SELECT ... FOR UPDATE to serialize concurrent balance mutations.
        """
        stmt = (
            select(StockBalance)
            .where(
                StockBalance.tenant_id == tenant_id,
                StockBalance.store_id == store_id,
                StockBalance.variant_id == variant_id,
            )
            .with_for_update()
        )
        balance = (await db.execute(stmt)).scalar_one_or_none()
        if balance:
            return balance

        # Validate store belongs to tenant
        store_stmt = select(Store).where(Store.id == store_id, Store.tenant_id == tenant_id)
        store = (await db.execute(store_stmt)).scalar_one_or_none()
        if not store:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "STORE_NOT_FOUND",
                    "message": f"Store '{store_id}' not found for merchant.",
                },
            )

        # Validate variant belongs to tenant
        var_stmt = select(ProductVariant).where(
            ProductVariant.id == variant_id, ProductVariant.tenant_id == tenant_id
        )
        variant = (await db.execute(var_stmt)).scalar_one_or_none()
        if not variant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "VARIANT_NOT_FOUND",
                    "message": f"Variant '{variant_id}' not found for merchant.",
                },
            )

        # Create row
        balance = StockBalance(
            tenant_id=tenant_id,
            store_id=store_id,
            variant_id=variant_id,
            on_hand_qty=0,
            reserved_qty=0,
            available_qty=0,
            in_transit_qty=0,
            reorder_threshold=5,
            low_stock_alert=True,
        )
        db.add(balance)
        await db.flush()

        # Re-select with for update
        return (await db.execute(stmt)).scalar_one()

    @staticmethod
    async def post_movement(
        db: AsyncSession,
        tenant_id: UUID,
        store_id: UUID,
        variant_id: UUID,
        movement_type: str,
        from_account: str,
        to_account: str,
        quantity: int,
        on_hand_delta: int = 0,
        reserved_delta: int = 0,
        in_transit_delta: int = 0,
        reference_type: str | None = None,
        reference_id: str | None = None,
        notes: str | None = None,
        idempotency_key: str | None = None,
        user_id: UUID | None = None,
    ) -> tuple[InventoryLedger, StockBalance]:
        """Core transactional engine for posting immutable double-entry ledger transactions

        and updating materialized stock balances under row locks with idempotency protection.
        """
        if quantity <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "INVALID_QUANTITY",
                    "message": "Movement quantity must be greater than zero.",
                },
            )

        # Idempotency guard: if key provided and already processed, return existing record
        if idempotency_key:
            existing_stmt = select(InventoryLedger).where(
                InventoryLedger.tenant_id == tenant_id,
                InventoryLedger.idempotency_key == idempotency_key,
            )
            existing_entry = (await db.execute(existing_stmt)).scalar_one_or_none()
            if existing_entry:
                balance_stmt = select(StockBalance).where(
                    StockBalance.tenant_id == tenant_id,
                    StockBalance.store_id == store_id,
                    StockBalance.variant_id == variant_id,
                )
                existing_balance = (await db.execute(balance_stmt)).scalar_one_or_none()
                return existing_entry, existing_balance

        # Acquire pessimistic row-level lock
        balance = await InventoryService.get_or_create_balance_for_update(
            db, tenant_id=tenant_id, store_id=store_id, variant_id=variant_id
        )

        new_on_hand = balance.on_hand_qty + on_hand_delta
        new_reserved = balance.reserved_qty + reserved_delta
        new_in_transit = balance.in_transit_qty + in_transit_delta
        new_available = new_on_hand - new_reserved

        # Enforce strict stock balance invariants
        if new_on_hand < 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "INSUFFICIENT_STOCK",
                    "message": f"Requested operation would result in negative on-hand inventory ({new_on_hand}).",
                },
            )
        if new_reserved < 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "INVALID_RESERVATION",
                    "message": f"Operation would result in negative reserved inventory ({new_reserved}).",
                },
            )
        if new_available < 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "INSUFFICIENT_AVAILABLE_STOCK",
                    "message": f"Requested quantity ({quantity}) exceeds available inventory ({balance.available_qty}).",
                },
            )
        if new_in_transit < 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "INVALID_IN_TRANSIT",
                    "message": f"Operation would result in negative in-transit inventory ({new_in_transit}).",
                },
            )
        if new_reserved > new_on_hand:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "RESERVED_EXCEEDS_ON_HAND",
                    "message": "Reserved quantity cannot exceed physical on-hand inventory.",
                },
            )

        # Update materialized balance snapshot
        balance.on_hand_qty = new_on_hand
        balance.reserved_qty = new_reserved
        balance.available_qty = new_available
        balance.in_transit_qty = new_in_transit
        balance.low_stock_alert = new_available <= balance.reorder_threshold

        # Post immutable ledger record
        valid_user_id = await _resolve_user_id(db, user_id)
        entry = InventoryLedger(
            tenant_id=tenant_id,
            store_id=store_id,
            variant_id=variant_id,
            movement_type=movement_type,
            from_account=from_account,
            to_account=to_account,
            quantity=quantity,
            on_hand_delta=on_hand_delta,
            reserved_delta=reserved_delta,
            in_transit_delta=in_transit_delta,
            balance_after_on_hand=new_on_hand,
            balance_after_reserved=new_reserved,
            balance_after_available=new_available,
            idempotency_key=idempotency_key,
            reference_type=reference_type,
            reference_id=reference_id,
            notes=notes,
            created_by_user_id=valid_user_id,
        )
        db.add(entry)
        await db.flush()
        await db.commit()
        await db.refresh(balance)
        await db.refresh(entry)
        return entry, balance

    # --- High-Level Movement Workflows ---

    @staticmethod
    async def reserve_stock(
        db: AsyncSession, tenant_id: UUID, data: StockReservationCreate, user_id: UUID | None
    ) -> tuple[InventoryLedger, StockBalance]:
        return await InventoryService.post_movement(
            db=db,
            tenant_id=tenant_id,
            store_id=data.store_id,
            variant_id=data.variant_id,
            movement_type="SALES_RESERVATION",
            from_account="STORE_ON_HAND",
            to_account="STORE_RESERVED",
            quantity=data.quantity,
            on_hand_delta=0,
            reserved_delta=data.quantity,
            in_transit_delta=0,
            reference_type="ORDER_RESERVATION",
            reference_id=data.reference_id,
            notes=data.notes,
            idempotency_key=data.idempotency_key,
            user_id=user_id,
        )

    @staticmethod
    async def release_reservation(
        db: AsyncSession, tenant_id: UUID, data: StockReservationRelease, user_id: UUID | None
    ) -> tuple[InventoryLedger, StockBalance]:
        return await InventoryService.post_movement(
            db=db,
            tenant_id=tenant_id,
            store_id=data.store_id,
            variant_id=data.variant_id,
            movement_type="SALES_RELEASE",
            from_account="STORE_RESERVED",
            to_account="STORE_ON_HAND",
            quantity=data.quantity,
            on_hand_delta=0,
            reserved_delta=-data.quantity,
            in_transit_delta=0,
            reference_type="ORDER_RELEASE",
            reference_id=data.reference_id,
            notes=data.notes,
            idempotency_key=data.idempotency_key,
            user_id=user_id,
        )

    @staticmethod
    async def dispatch_stock(
        db: AsyncSession, tenant_id: UUID, data: StockDispatchCreate, user_id: UUID | None
    ) -> tuple[InventoryLedger, StockBalance]:
        return await InventoryService.post_movement(
            db=db,
            tenant_id=tenant_id,
            store_id=data.store_id,
            variant_id=data.variant_id,
            movement_type="SALES_DISPATCH",
            from_account="STORE_RESERVED",
            to_account="SALES_CUSTOMER",
            quantity=data.quantity,
            on_hand_delta=-data.quantity,
            reserved_delta=-data.quantity,
            in_transit_delta=0,
            reference_type="SALES_ORDER",
            reference_id=data.reference_id,
            notes=data.notes,
            idempotency_key=data.idempotency_key,
            user_id=user_id,
        )

    @staticmethod
    async def return_customer_stock(
        db: AsyncSession, tenant_id: UUID, data: CustomerReturnCreate, user_id: UUID | None
    ) -> tuple[InventoryLedger, StockBalance]:
        return await InventoryService.post_movement(
            db=db,
            tenant_id=tenant_id,
            store_id=data.store_id,
            variant_id=data.variant_id,
            movement_type="CUSTOMER_RETURN",
            from_account="SALES_CUSTOMER",
            to_account="STORE_ON_HAND",
            quantity=data.quantity,
            on_hand_delta=data.quantity,
            reserved_delta=0,
            in_transit_delta=0,
            reference_type="RETURN_ORDER",
            reference_id=data.reference_id,
            notes=data.notes,
            idempotency_key=data.idempotency_key,
            user_id=user_id,
        )

    @staticmethod
    async def adjust_stock(
        db: AsyncSession, tenant_id: UUID, data: StockAdjustmentCreate, user_id: UUID | None
    ) -> tuple[InventoryLedger, StockBalance]:
        if data.reason == "damage":
            movement_type = "ADJUSTMENT_DAMAGE"
            from_account = "STORE_ON_HAND"
            to_account = "INVENTORY_SHRINKAGE_DAMAGE"
            on_hand_delta = -data.quantity
            reserved_delta = 0
        elif data.reason == "loss":
            movement_type = "ADJUSTMENT_LOSS"
            from_account = "STORE_ON_HAND"
            to_account = "INVENTORY_SHRINKAGE_LOSS"
            on_hand_delta = -data.quantity
            reserved_delta = 0
        elif data.reason == "reconciliation_gain":
            movement_type = "RECONCILIATION_GAIN"
            from_account = "INVENTORY_RECONCILIATION"
            to_account = "STORE_ON_HAND"
            on_hand_delta = data.quantity
            reserved_delta = 0
        elif data.reason == "reconciliation_loss":
            movement_type = "RECONCILIATION_LOSS"
            from_account = "STORE_ON_HAND"
            to_account = "INVENTORY_RECONCILIATION"
            on_hand_delta = -data.quantity
            reserved_delta = 0
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "INVALID_ADJUSTMENT_REASON",
                    "message": f"Unsupported reason '{data.reason}'.",
                },
            )

        return await InventoryService.post_movement(
            db=db,
            tenant_id=tenant_id,
            store_id=data.store_id,
            variant_id=data.variant_id,
            movement_type=movement_type,
            from_account=from_account,
            to_account=to_account,
            quantity=data.quantity,
            on_hand_delta=on_hand_delta,
            reserved_delta=reserved_delta,
            in_transit_delta=0,
            reference_type="MANUAL_ADJUSTMENT",
            reference_id=data.reason,
            notes=data.notes,
            idempotency_key=data.idempotency_key,
            user_id=user_id,
        )

    # --- Query Methods ---

    @staticmethod
    async def get_balance(
        db: AsyncSession, tenant_id: UUID, store_id: UUID, variant_id: UUID
    ) -> StockBalance:
        stmt = select(StockBalance).where(
            StockBalance.tenant_id == tenant_id,
            StockBalance.store_id == store_id,
            StockBalance.variant_id == variant_id,
        )
        balance = (await db.execute(stmt)).scalar_one_or_none()
        if not balance:
            balance = await InventoryService.get_or_create_balance_for_update(
                db, tenant_id=tenant_id, store_id=store_id, variant_id=variant_id
            )
            await db.commit()
            await db.refresh(balance)
        return balance

    @staticmethod
    async def list_balances(
        db: AsyncSession,
        tenant_id: UUID,
        store_id: UUID | None = None,
        variant_id: UUID | None = None,
        low_stock_only: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> list[StockBalance]:
        stmt = select(StockBalance).where(StockBalance.tenant_id == tenant_id)
        if store_id:
            stmt = stmt.where(StockBalance.store_id == store_id)
        if variant_id:
            stmt = stmt.where(StockBalance.variant_id == variant_id)
        if low_stock_only:
            stmt = stmt.where(StockBalance.low_stock_alert.is_(True))

        stmt = stmt.order_by(StockBalance.updated_at.desc()).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def list_ledger(
        db: AsyncSession,
        tenant_id: UUID,
        store_id: UUID | None = None,
        variant_id: UUID | None = None,
        movement_type: str | None = None,
        reference_id: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[InventoryLedger]:
        stmt = select(InventoryLedger).where(InventoryLedger.tenant_id == tenant_id)
        if store_id:
            stmt = stmt.where(InventoryLedger.store_id == store_id)
        if variant_id:
            stmt = stmt.where(InventoryLedger.variant_id == variant_id)
        if movement_type:
            stmt = stmt.where(InventoryLedger.movement_type == movement_type)
        if reference_id:
            stmt = stmt.where(InventoryLedger.reference_id == reference_id)

        stmt = stmt.order_by(InventoryLedger.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())


class SupplierService:
    @staticmethod
    async def create_supplier(db: AsyncSession, tenant_id: UUID, data: SupplierCreate) -> Supplier:
        existing = (
            await db.execute(
                select(Supplier).where(Supplier.tenant_id == tenant_id, Supplier.code == data.code)
            )
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "SUPPLIER_CODE_EXISTS",
                    "message": f"Supplier code '{data.code}' already exists.",
                },
            )

        supplier = Supplier(
            tenant_id=tenant_id,
            name=data.name,
            code=data.code,
            contact_person=data.contact_person,
            email=data.email,
            phone=data.phone,
            address=data.address,
            gstin=data.gstin,
            is_active=data.is_active,
        )
        db.add(supplier)
        await db.commit()
        await db.refresh(supplier)
        return supplier

    @staticmethod
    async def update_supplier(
        db: AsyncSession, tenant_id: UUID, supplier_id: UUID, data: SupplierUpdate
    ) -> Supplier:
        supplier = (
            await db.execute(
                select(Supplier).where(Supplier.id == supplier_id, Supplier.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if not supplier:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "SUPPLIER_NOT_FOUND", "message": "Supplier not found."},
            )

        if data.name is not None:
            supplier.name = data.name
        if data.contact_person is not None:
            supplier.contact_person = data.contact_person
        if data.email is not None:
            supplier.email = data.email
        if data.phone is not None:
            supplier.phone = data.phone
        if data.address is not None:
            supplier.address = data.address
        if data.gstin is not None:
            supplier.gstin = data.gstin
        if data.is_active is not None:
            supplier.is_active = data.is_active

        await db.commit()
        await db.refresh(supplier)
        return supplier

    @staticmethod
    async def list_suppliers(
        db: AsyncSession, tenant_id: UUID, active_only: bool = False, skip: int = 0, limit: int = 50
    ) -> list[Supplier]:
        stmt = select(Supplier).where(Supplier.tenant_id == tenant_id)
        if active_only:
            stmt = stmt.where(Supplier.is_active.is_(True))
        stmt = stmt.order_by(Supplier.name.asc()).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_supplier(db: AsyncSession, tenant_id: UUID, supplier_id: UUID) -> Supplier:
        supplier = (
            await db.execute(
                select(Supplier).where(Supplier.id == supplier_id, Supplier.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if not supplier:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "SUPPLIER_NOT_FOUND", "message": "Supplier not found."},
            )
        return supplier


class PurchaseOrderService:
    @staticmethod
    async def create_purchase_order(
        db: AsyncSession, tenant_id: UUID, data: PurchaseOrderCreate, user_id: UUID | None
    ) -> PurchaseOrder:
        # Check store
        store = (
            await db.execute(
                select(Store).where(Store.id == data.store_id, Store.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if not store:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "STORE_NOT_FOUND", "message": "Destination store not found."},
            )

        # Check PO number uniqueness
        existing_po = (
            await db.execute(
                select(PurchaseOrder).where(
                    PurchaseOrder.tenant_id == tenant_id, PurchaseOrder.po_number == data.po_number
                )
            )
        ).scalar_one_or_none()
        if existing_po:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "PO_NUMBER_EXISTS",
                    "message": f"PO number '{data.po_number}' already exists.",
                },
            )

        if data.supplier_id:
            supplier = (
                await db.execute(
                    select(Supplier).where(
                        Supplier.id == data.supplier_id, Supplier.tenant_id == tenant_id
                    )
                )
            ).scalar_one_or_none()
            if not supplier:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"code": "SUPPLIER_NOT_FOUND", "message": "Supplier not found."},
                )

        # Validate variant ownership and calculate total
        total_amount = Decimal("0.00")
        po_items: list[PurchaseOrderItem] = []
        for line in data.items:
            variant = (
                await db.execute(
                    select(ProductVariant).where(
                        ProductVariant.id == line.variant_id, ProductVariant.tenant_id == tenant_id
                    )
                )
            ).scalar_one_or_none()
            if not variant:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "code": "VARIANT_NOT_FOUND",
                        "message": f"Variant '{line.variant_id}' not found.",
                    },
                )
            line_total = line.unit_cost * Decimal(line.quantity_ordered)
            total_amount += line_total
            po_items.append(
                PurchaseOrderItem(
                    tenant_id=tenant_id,
                    variant_id=line.variant_id,
                    quantity_ordered=line.quantity_ordered,
                    quantity_received=0,
                    unit_cost=line.unit_cost,
                    total_cost=line_total,
                )
            )

        valid_user_id = await _resolve_user_id(db, user_id)
        po = PurchaseOrder(
            tenant_id=tenant_id,
            store_id=data.store_id,
            supplier_id=data.supplier_id,
            po_number=data.po_number,
            status="ordered",
            total_amount=total_amount,
            notes=data.notes,
            created_by_user_id=valid_user_id,
            items=po_items,
        )
        db.add(po)
        await db.commit()
        return await PurchaseOrderService.get_purchase_order(db, tenant_id, po.id)

    @staticmethod
    async def get_purchase_order(db: AsyncSession, tenant_id: UUID, po_id: UUID) -> PurchaseOrder:
        stmt = (
            select(PurchaseOrder)
            .where(PurchaseOrder.id == po_id, PurchaseOrder.tenant_id == tenant_id)
            .options(selectinload(PurchaseOrder.items))
        )
        po = (await db.execute(stmt)).scalar_one_or_none()
        if not po:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "PURCHASE_ORDER_NOT_FOUND", "message": "Purchase order not found."},
            )
        return po

    @staticmethod
    async def list_purchase_orders(
        db: AsyncSession,
        tenant_id: UUID,
        store_id: UUID | None = None,
        status_filter: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[PurchaseOrder]:
        stmt = (
            select(PurchaseOrder)
            .where(PurchaseOrder.tenant_id == tenant_id)
            .options(selectinload(PurchaseOrder.items))
        )
        if store_id:
            stmt = stmt.where(PurchaseOrder.store_id == store_id)
        if status_filter:
            stmt = stmt.where(PurchaseOrder.status == status_filter)
        stmt = stmt.order_by(PurchaseOrder.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def receive_goods(
        db: AsyncSession, tenant_id: UUID, data: StockReceiptCreate, user_id: UUID | None
    ) -> StockReceipt:
        # Check store
        store = (
            await db.execute(
                select(Store).where(Store.id == data.store_id, Store.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if not store:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "STORE_NOT_FOUND", "message": "Store not found."},
            )

        # Check receipt number unique
        existing_rcp = (
            await db.execute(
                select(StockReceipt).where(
                    StockReceipt.tenant_id == tenant_id,
                    StockReceipt.receipt_number == data.receipt_number,
                )
            )
        ).scalar_one_or_none()
        if existing_rcp:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "RECEIPT_NUMBER_EXISTS",
                    "message": f"Receipt '{data.receipt_number}' already exists.",
                },
            )

        # Check PO if provided
        po: PurchaseOrder | None = None
        if data.purchase_order_id:
            po = (
                await db.execute(
                    select(PurchaseOrder)
                    .where(
                        PurchaseOrder.id == data.purchase_order_id,
                        PurchaseOrder.tenant_id == tenant_id,
                    )
                    .options(selectinload(PurchaseOrder.items))
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if not po:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "code": "PURCHASE_ORDER_NOT_FOUND",
                        "message": "Purchase order not found.",
                    },
                )

        receipt_items: list[StockReceiptItem] = []
        for line in data.items:
            # Post ledger movement for inward receipt
            item_idempotency = (
                f"{data.idempotency_key}:{line.variant_id}" if data.idempotency_key else None
            )
            await InventoryService.post_movement(
                db=db,
                tenant_id=tenant_id,
                store_id=data.store_id,
                variant_id=line.variant_id,
                movement_type="PURCHASE_RECEIPT",
                from_account="SUPPLIER_INWARD",
                to_account="STORE_ON_HAND",
                quantity=line.quantity_received,
                on_hand_delta=line.quantity_received,
                reserved_delta=0,
                in_transit_delta=0,
                reference_type="PURCHASE_ORDER" if po else "DIRECT_RECEIPT",
                reference_id=po.po_number if po else data.receipt_number,
                notes=f"Inward receipt {data.receipt_number}",
                idempotency_key=item_idempotency,
                user_id=user_id,
            )

            receipt_items.append(
                StockReceiptItem(
                    variant_id=line.variant_id,
                    quantity_received=line.quantity_received,
                    unit_cost=line.unit_cost,
                )
            )

            # Update PO line item received quantities
            if po:
                for po_item in po.items:
                    if po_item.variant_id == line.variant_id:
                        po_item.quantity_received += line.quantity_received

        # Update PO status
        if po:
            all_received = all(item.quantity_received >= item.quantity_ordered for item in po.items)
            po.status = "received" if all_received else "partially_received"

        valid_user_id = await _resolve_user_id(db, user_id)
        receipt = StockReceipt(
            tenant_id=tenant_id,
            store_id=data.store_id,
            purchase_order_id=data.purchase_order_id,
            receipt_number=data.receipt_number,
            invoice_number=data.invoice_number,
            notes=data.notes,
            received_by_user_id=valid_user_id,
            items=receipt_items,
        )
        db.add(receipt)
        await db.commit()
        stmt = (
            select(StockReceipt)
            .where(StockReceipt.id == receipt.id)
            .options(selectinload(StockReceipt.items))
        )
        return (await db.execute(stmt)).scalar_one()


class StoreTransferService:
    @staticmethod
    async def create_and_dispatch_transfer(
        db: AsyncSession, tenant_id: UUID, data: StoreTransferCreate, user_id: UUID | None
    ) -> StoreTransfer:
        if data.source_store_id == data.destination_store_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "SAME_STORE_TRANSFER",
                    "message": "Source and destination store must be distinct.",
                },
            )

        # Validate source store
        src = (
            await db.execute(
                select(Store).where(Store.id == data.source_store_id, Store.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if not src:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "SOURCE_STORE_NOT_FOUND", "message": "Source store not found."},
            )

        # Validate destination store
        dest = (
            await db.execute(
                select(Store).where(
                    Store.id == data.destination_store_id, Store.tenant_id == tenant_id
                )
            )
        ).scalar_one_or_none()
        if not dest:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "DESTINATION_STORE_NOT_FOUND",
                    "message": "Destination store not found.",
                },
            )

        # Check unique transfer number
        existing_trf = (
            await db.execute(
                select(StoreTransfer).where(
                    StoreTransfer.tenant_id == tenant_id,
                    StoreTransfer.transfer_number == data.transfer_number,
                )
            )
        ).scalar_one_or_none()
        if existing_trf:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "TRANSFER_NUMBER_EXISTS",
                    "message": f"Transfer '{data.transfer_number}' already exists.",
                },
            )

        transfer_items: list[StoreTransferItem] = []
        for line in data.items:
            # Post dispatch movement from source store on-hand into goods-in-transit
            line_idempotency = (
                f"{data.idempotency_key}:dispatch:{line.variant_id}"
                if data.idempotency_key
                else None
            )
            await InventoryService.post_movement(
                db=db,
                tenant_id=tenant_id,
                store_id=data.source_store_id,
                variant_id=line.variant_id,
                movement_type="TRANSFER_DISPATCH",
                from_account="STORE_ON_HAND",
                to_account="GOODS_IN_TRANSIT",
                quantity=line.quantity_shipped,
                on_hand_delta=-line.quantity_shipped,
                reserved_delta=0,
                in_transit_delta=line.quantity_shipped,
                reference_type="STORE_TRANSFER",
                reference_id=data.transfer_number,
                notes=f"Dispatched to store {dest.name}",
                idempotency_key=line_idempotency,
                user_id=user_id,
            )
            transfer_items.append(
                StoreTransferItem(
                    variant_id=line.variant_id,
                    quantity_shipped=line.quantity_shipped,
                    quantity_received=0,
                )
            )

        valid_user_id = await _resolve_user_id(db, user_id)
        transfer = StoreTransfer(
            tenant_id=tenant_id,
            source_store_id=data.source_store_id,
            destination_store_id=data.destination_store_id,
            transfer_number=data.transfer_number,
            status="in_transit",
            notes=data.notes,
            dispatched_by_user_id=valid_user_id,
            items=transfer_items,
        )
        db.add(transfer)
        await db.commit()
        return await StoreTransferService.get_transfer(db, tenant_id, transfer.id)

    @staticmethod
    async def receive_transfer(
        db: AsyncSession,
        tenant_id: UUID,
        transfer_id: UUID,
        data: StoreTransferReceive,
        user_id: UUID | None,
    ) -> StoreTransfer:
        stmt = (
            select(StoreTransfer)
            .where(StoreTransfer.id == transfer_id, StoreTransfer.tenant_id == tenant_id)
            .options(selectinload(StoreTransfer.items))
            .with_for_update()
        )
        transfer = (await db.execute(stmt)).scalar_one_or_none()
        if not transfer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "TRANSFER_NOT_FOUND", "message": "Store transfer not found."},
            )

        if transfer.status != "in_transit":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "INVALID_TRANSFER_STATUS",
                    "message": f"Transfer is in '{transfer.status}' status and cannot be received.",
                },
            )

        for line in transfer.items:
            # 1. Relieve in_transit on source store
            src_balance = await InventoryService.get_or_create_balance_for_update(
                db,
                tenant_id=tenant_id,
                store_id=transfer.source_store_id,
                variant_id=line.variant_id,
            )
            src_balance.in_transit_qty = max(0, src_balance.in_transit_qty - line.quantity_shipped)

            # 2. Add stock to destination store on-hand
            dest_idempotency = (
                f"{data.idempotency_key}:receipt:{line.variant_id}"
                if data.idempotency_key
                else None
            )
            await InventoryService.post_movement(
                db=db,
                tenant_id=tenant_id,
                store_id=transfer.destination_store_id,
                variant_id=line.variant_id,
                movement_type="TRANSFER_RECEIPT",
                from_account="GOODS_IN_TRANSIT",
                to_account="STORE_ON_HAND",
                quantity=line.quantity_shipped,
                on_hand_delta=line.quantity_shipped,
                reserved_delta=0,
                in_transit_delta=0,
                reference_type="STORE_TRANSFER",
                reference_id=transfer.transfer_number,
                notes=f"Received transfer {transfer.transfer_number}",
                idempotency_key=dest_idempotency,
                user_id=user_id,
            )
            line.quantity_received = line.quantity_shipped

        transfer.status = "completed"
        transfer.received_by_user_id = await _resolve_user_id(db, user_id)
        if data.notes:
            transfer.notes = f"{transfer.notes or ''}\nReceipt Note: {data.notes}".strip()

        await db.commit()
        return await StoreTransferService.get_transfer(db, tenant_id, transfer.id)

    @staticmethod
    async def get_transfer(db: AsyncSession, tenant_id: UUID, transfer_id: UUID) -> StoreTransfer:
        stmt = (
            select(StoreTransfer)
            .where(StoreTransfer.id == transfer_id, StoreTransfer.tenant_id == tenant_id)
            .options(selectinload(StoreTransfer.items))
        )
        transfer = (await db.execute(stmt)).scalar_one_or_none()
        if not transfer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "TRANSFER_NOT_FOUND", "message": "Store transfer not found."},
            )
        return transfer

    @staticmethod
    async def list_transfers(
        db: AsyncSession,
        tenant_id: UUID,
        store_id: UUID | None = None,
        status_filter: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[StoreTransfer]:
        stmt = (
            select(StoreTransfer)
            .where(StoreTransfer.tenant_id == tenant_id)
            .options(selectinload(StoreTransfer.items))
        )
        if store_id:
            stmt = stmt.where(
                or_(
                    StoreTransfer.source_store_id == store_id,
                    StoreTransfer.destination_store_id == store_id,
                )
            )
        if status_filter:
            stmt = stmt.where(StoreTransfer.status == status_filter)
        stmt = stmt.order_by(StoreTransfer.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())
