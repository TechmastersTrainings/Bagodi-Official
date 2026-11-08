import csv
import io
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import (
    case,
    distinct,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.models import Category, Product, ProductVariant
from app.modules.delivery.models import DeliveryPersonnel, Shipment
from app.modules.identity.models import User
from app.modules.inventory.models import (
    InventoryLedger,
    StockBalance,
    StockReceiptItem,
)
from app.modules.orders.models import Order, OrderItem, PaymentTransaction
from app.modules.payments.models import CodSettlement, Refund
from app.modules.platform.models import Store, Tenant
from app.modules.reports.models import ReportExportLog
from app.modules.reports.schemas import (
    CategoryPerformanceRecord,
    CategoryPerformanceReportResponse,
    CodSettlementSummary,
    CourierPerformanceRecord,
    CustomerAnalyticsResponse,
    DamagedStockReportRecord,
    DeliveryAnalyticsResponse,
    InventoryLedgerMovementSummary,
    InventoryReportResponse,
    MerchantDashboardResponse,
    MultiStoreReportResponse,
    OrderAnalyticsResponse,
    OrderStatusBreakdown,
    PaymentMethodSummary,
    PaymentReportResponse,
    PlatformOverviewResponse,
    ProductPerformanceRecord,
    ProductPerformanceReportResponse,
    ReportDateRangeFilter,
    RiderPerformanceRecord,
    SalesIntervalRecord,
    SalesKpiCard,
    SalesReportResponse,
    StockBalanceReportRecord,
    StoreComparisonRecord,
    TenantComparisonRecord,
    TimeSeriesPoint,
    TopCustomerRecord,
)


class ReportingService:
    # -------------------------------------------------------------------------
    # Helper: Date Bound Resolution
    # -------------------------------------------------------------------------
    @staticmethod
    def resolve_date_bounds(
        filter_params: ReportDateRangeFilter,
    ) -> tuple[datetime, datetime]:
        now = datetime.now(UTC)

        if filter_params.start_date and filter_params.end_date:
            # Custom bounds provided
            s = filter_params.start_date
            e = filter_params.end_date

            if isinstance(s, date) and not isinstance(s, datetime):
                start_dt = datetime.combine(s, time.min, tzinfo=UTC)
            elif isinstance(s, datetime):
                start_dt = s if s.tzinfo else s.replace(tzinfo=UTC)
            else:
                start_dt = now - timedelta(days=30)

            if isinstance(e, date) and not isinstance(e, datetime):
                end_dt = datetime.combine(e, time.max, tzinfo=UTC)
            elif isinstance(e, datetime):
                end_dt = e if e.tzinfo else e.replace(tzinfo=UTC)
            else:
                end_dt = now

            if start_dt > end_dt:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "INVALID_DATE_RANGE",
                        "message": "start_date cannot be greater than end_date.",
                    },
                )
            return start_dt, end_dt

        # Preset time windows
        window = (filter_params.time_window or "last_30_days").lower()

        if window == "today":
            today_start = datetime.combine(now.date(), time.min, tzinfo=UTC)
            return today_start, now
        elif window == "yesterday":
            yest = now.date() - timedelta(days=1)
            return datetime.combine(yest, time.min, tzinfo=UTC), datetime.combine(
                yest, time.max, tzinfo=UTC
            )
        elif window == "last_7_days":
            return now - timedelta(days=7), now
        elif window == "this_month":
            month_start = datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=UTC)
            return month_start, now
        elif window == "last_month":
            first_this_month = datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=UTC)
            last_day_prev = first_this_month - timedelta(seconds=1)
            first_prev_month = datetime(
                last_day_prev.year, last_day_prev.month, 1, 0, 0, 0, tzinfo=UTC
            )
            return first_prev_month, last_day_prev
        else:
            # Default: last 30 days
            return now - timedelta(days=30), now

    # -------------------------------------------------------------------------
    # 1. Merchant Operations Dashboard
    # -------------------------------------------------------------------------
    @staticmethod
    async def get_merchant_dashboard(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        filter_params: ReportDateRangeFilter,
    ) -> MerchantDashboardResponse:
        start_dt, end_dt = ReportingService.resolve_date_bounds(filter_params)

        # Base order query filter
        order_filter = [
            Order.tenant_id == tenant_id,
            Order.created_at >= start_dt,
            Order.created_at <= end_dt,
        ]
        if filter_params.store_id:
            order_filter.append(Order.store_id == filter_params.store_id)

        # 1. Aggregate Sales KPIs
        kpi_stmt = select(
            func.coalesce(
                func.sum(
                    case((Order.status != "CANCELLED", Order.subtotal), else_=Decimal("0.00"))
                ),
                Decimal("0.00"),
            ).label("gross_sales"),
            func.coalesce(
                func.sum(
                    case(
                        (Order.status != "CANCELLED", Order.discount_amount),
                        else_=Decimal("0.00"),
                    )
                ),
                Decimal("0.00"),
            ).label("discount_total"),
            func.coalesce(
                func.sum(
                    case((Order.status != "CANCELLED", Order.shipping_fee), else_=Decimal("0.00"))
                ),
                Decimal("0.00"),
            ).label("shipping_fee_total"),
            func.coalesce(
                func.sum(
                    case((Order.status != "CANCELLED", Order.total_amount), else_=Decimal("0.00"))
                ),
                Decimal("0.00"),
            ).label("net_sales"),
            func.count(Order.id).label("total_orders"),
            func.count(case((Order.status == "DELIVERED", Order.id))).label("delivered_orders"),
            func.count(case((Order.status == "CANCELLED", Order.id))).label("cancelled_orders"),
            func.count(case((Order.status == "RETURNED", Order.id))).label("returned_orders"),
        ).where(*order_filter)

        kpi_res = (await db.execute(kpi_stmt)).one()
        total_orders = kpi_res.total_orders or 0
        delivered_orders = kpi_res.delivered_orders or 0
        cancelled_orders = kpi_res.cancelled_orders or 0
        returned_orders = kpi_res.returned_orders or 0
        net_sales = Decimal(str(kpi_res.net_sales or "0.00"))

        valid_orders = total_orders - cancelled_orders
        aov = (
            (net_sales / valid_orders).quantize(Decimal("0.01"))
            if valid_orders > 0
            else Decimal("0.00")
        )
        cancellation_rate = (
            (Decimal(cancelled_orders) / Decimal(total_orders) * Decimal("100.0")).quantize(
                Decimal("0.01")
            )
            if total_orders > 0
            else Decimal("0.00")
        )
        return_rate = (
            (Decimal(returned_orders) / Decimal(delivered_orders) * Decimal("100.0")).quantize(
                Decimal("0.01")
            )
            if delivered_orders > 0
            else Decimal("0.00")
        )

        # Pending fulfillment count
        stmt_pending = select(func.count(Order.id)).where(
            Order.tenant_id == tenant_id,
            Order.status.in_(["CONFIRMED", "PROCESSING"]),
        )
        if filter_params.store_id:
            stmt_pending = stmt_pending.where(Order.store_id == filter_params.store_id)
        pending_fulfillment_orders = (await db.execute(stmt_pending)).scalar() or 0

        # Out for delivery shipments
        stmt_ofd = select(func.count(Shipment.id)).where(
            Shipment.tenant_id == tenant_id,
            Shipment.status == "OUT_FOR_DELIVERY",
        )
        if filter_params.store_id:
            stmt_ofd = stmt_ofd.where(Shipment.store_id == filter_params.store_id)
        out_for_delivery_shipments = (await db.execute(stmt_ofd)).scalar() or 0

        kpis = SalesKpiCard(
            gross_sales=Decimal(str(kpi_res.gross_sales or "0.00")),
            discount_total=Decimal(str(kpi_res.discount_total or "0.00")),
            shipping_fee_total=Decimal(str(kpi_res.shipping_fee_total or "0.00")),
            net_sales=net_sales,
            total_orders=total_orders,
            delivered_orders=delivered_orders,
            cancelled_orders=cancelled_orders,
            returned_orders=returned_orders,
            aov=aov,
            cancellation_rate=cancellation_rate,
            return_rate=return_rate,
            pending_fulfillment_orders=pending_fulfillment_orders,
            out_for_delivery_shipments=out_for_delivery_shipments,
        )

        # 2. Time-Series (Daily)
        ts_stmt = (
            select(
                func.to_char(func.timezone("UTC", Order.created_at), "YYYY-MM-DD").label("d"),
                func.count(Order.id).label("cnt"),
                func.coalesce(
                    func.sum(
                        case((Order.status != "CANCELLED", Order.subtotal), else_=Decimal("0.00"))
                    ),
                    Decimal("0.00"),
                ).label("gross"),
                func.coalesce(
                    func.sum(
                        case(
                            (Order.status != "CANCELLED", Order.total_amount), else_=Decimal("0.00")
                        )
                    ),
                    Decimal("0.00"),
                ).label("net"),
            )
            .where(*order_filter)
            .group_by("d")
            .order_by("d")
        )
        ts_rows = (await db.execute(ts_stmt)).fetchall()
        time_series = [
            TimeSeriesPoint(
                date=row.d,
                orders_count=row.cnt,
                gross_sales=Decimal(str(row.gross)),
                net_sales=Decimal(str(row.net)),
            )
            for row in ts_rows
        ]

        # 3. Order Status Breakdown
        status_stmt = (
            select(Order.status, func.count(Order.id)).where(*order_filter).group_by(Order.status)
        )
        status_rows = (await db.execute(status_stmt)).fetchall()
        order_status_summary = {row[0]: row[1] for row in status_rows}

        # 4. Top Selling Products
        top_prods_resp = await ReportingService.get_product_performance(
            db, tenant_id=tenant_id, filter_params=filter_params, limit=5
        )

        return MerchantDashboardResponse(
            tenant_id=tenant_id,
            period=filter_params.time_window,
            start_date=start_dt,
            end_date=end_dt,
            store_id=filter_params.store_id,
            kpis=kpis,
            time_series=time_series,
            top_selling_products=top_prods_resp.records,
            order_status_summary=order_status_summary,
        )

    # -------------------------------------------------------------------------
    # 2. Sales & Revenue Reports
    # -------------------------------------------------------------------------
    @staticmethod
    async def get_sales_report(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        filter_params: ReportDateRangeFilter,
    ) -> SalesReportResponse:
        start_dt, end_dt = ReportingService.resolve_date_bounds(filter_params)
        granularity = (filter_params.granularity or "daily").lower()

        order_filter = [
            Order.tenant_id == tenant_id,
            Order.created_at >= start_dt,
            Order.created_at <= end_dt,
        ]
        if filter_params.store_id:
            order_filter.append(Order.store_id == filter_params.store_id)

        # Date format by granularity
        if granularity == "monthly":
            fmt = "YYYY-MM"
        elif granularity == "weekly":
            fmt = "IYYY-IW"
        else:
            fmt = "YYYY-MM-DD"

        # 1. Summary Card
        summary_res = await ReportingService.get_merchant_dashboard(
            db, tenant_id=tenant_id, filter_params=filter_params
        )

        # 2. Interval aggregation
        interval_stmt = (
            select(
                func.to_char(func.timezone("UTC", Order.created_at), fmt).label("interval_date"),
                func.count(Order.id).label("orders_count"),
                func.coalesce(
                    func.sum(
                        case((Order.status != "CANCELLED", Order.subtotal), else_=Decimal("0.00"))
                    ),
                    Decimal("0.00"),
                ).label("gross_sales"),
                func.coalesce(
                    func.sum(
                        case(
                            (Order.status != "CANCELLED", Order.discount_amount),
                            else_=Decimal("0.00"),
                        )
                    ),
                    Decimal("0.00"),
                ).label("discounts"),
                func.coalesce(
                    func.sum(
                        case(
                            (Order.status != "CANCELLED", Order.shipping_fee),
                            else_=Decimal("0.00"),
                        )
                    ),
                    Decimal("0.00"),
                ).label("shipping_fees"),
                func.coalesce(
                    func.sum(
                        case(
                            (Order.status != "CANCELLED", Order.total_amount), else_=Decimal("0.00")
                        )
                    ),
                    Decimal("0.00"),
                ).label("net_sales"),
            )
            .where(*order_filter)
            .group_by("interval_date")
            .order_by("interval_date")
        )
        rows = (await db.execute(interval_stmt)).fetchall()

        # Captured payments and refunds for each interval
        pay_stmt = (
            select(
                func.to_char(func.timezone("UTC", PaymentTransaction.created_at), fmt).label(
                    "interval_date"
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (PaymentTransaction.status == "captured", PaymentTransaction.amount),
                            else_=Decimal("0.00"),
                        )
                    ),
                    Decimal("0.00"),
                ).label("captured"),
            )
            .where(
                PaymentTransaction.tenant_id == tenant_id,
                PaymentTransaction.created_at >= start_dt,
                PaymentTransaction.created_at <= end_dt,
            )
            .group_by("interval_date")
        )
        pay_dict = {
            row.interval_date: Decimal(str(row.captured))
            for row in (await db.execute(pay_stmt)).fetchall()
        }

        refund_stmt = (
            select(
                func.to_char(func.timezone("UTC", Refund.created_at), fmt).label("interval_date"),
                func.coalesce(
                    func.sum(
                        case((Refund.status == "succeeded", Refund.amount), else_=Decimal("0.00"))
                    ),
                    Decimal("0.00"),
                ).label("refunded"),
            )
            .where(
                Refund.tenant_id == tenant_id,
                Refund.created_at >= start_dt,
                Refund.created_at <= end_dt,
            )
            .group_by("interval_date")
        )
        refund_dict = {
            row.interval_date: Decimal(str(row.refunded))
            for row in (await db.execute(refund_stmt)).fetchall()
        }

        records: list[SalesIntervalRecord] = []
        for r in rows:
            cnt = r.orders_count or 0
            net = Decimal(str(r.net_sales or "0.00"))
            aov = (net / cnt).quantize(Decimal("0.01")) if cnt > 0 else Decimal("0.00")
            records.append(
                SalesIntervalRecord(
                    interval_date=r.interval_date,
                    orders_count=cnt,
                    gross_sales=Decimal(str(r.gross_sales or "0.00")),
                    discounts=Decimal(str(r.discounts or "0.00")),
                    shipping_fees=Decimal(str(r.shipping_fees or "0.00")),
                    net_sales=net,
                    captured_revenue=pay_dict.get(r.interval_date, Decimal("0.00")),
                    refunded_amount=refund_dict.get(r.interval_date, Decimal("0.00")),
                    aov=aov,
                )
            )

        return SalesReportResponse(
            tenant_id=tenant_id,
            store_id=filter_params.store_id,
            start_date=start_dt,
            end_date=end_dt,
            granularity=granularity,
            summary=summary_res.kpis,
            records=records,
        )

    # -------------------------------------------------------------------------
    # 3. Product & Category Performance Analytics
    # -------------------------------------------------------------------------
    @staticmethod
    async def get_product_performance(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        filter_params: ReportDateRangeFilter,
        limit: int = 50,
        sort_by: str = "units_sold",
    ) -> ProductPerformanceReportResponse:
        start_dt, end_dt = ReportingService.resolve_date_bounds(filter_params)

        order_filter = [
            Order.tenant_id == tenant_id,
            Order.created_at >= start_dt,
            Order.created_at <= end_dt,
            Order.status != "CANCELLED",
        ]
        if filter_params.store_id:
            order_filter.append(Order.store_id == filter_params.store_id)

        # Aggregate items sold per product
        stmt = (
            select(
                Product.id.label("product_id"),
                Product.name.label("product_name"),
                Category.name.label("category_name"),
                func.sum(OrderItem.quantity).label("units_sold"),
                func.sum(OrderItem.total_price).label("gross_revenue"),
                func.count(distinct(OrderItem.order_id)).label("total_orders"),
            )
            .select_from(OrderItem)
            .join(Order, OrderItem.order_id == Order.id)
            .join(ProductVariant, OrderItem.variant_id == ProductVariant.id)
            .join(Product, ProductVariant.product_id == Product.id)
            .outerjoin(Category, Product.category_id == Category.id)
            .where(*order_filter)
            .group_by(Product.id, Product.name, Category.name)
        )

        if sort_by == "revenue":
            stmt = stmt.order_by(func.sum(OrderItem.total_price).desc())
        else:
            stmt = stmt.order_by(func.sum(OrderItem.quantity).desc())

        stmt = stmt.limit(limit)
        rows = (await db.execute(stmt)).fetchall()

        # Query stock on hand for each product
        prod_ids = [r.product_id for r in rows]
        stock_dict: dict[UUID, int] = {}
        if prod_ids:
            stock_stmt = (
                select(
                    ProductVariant.product_id,
                    func.coalesce(func.sum(StockBalance.on_hand_qty), 0).label("stock"),
                )
                .join(StockBalance, ProductVariant.id == StockBalance.variant_id)
                .where(
                    ProductVariant.tenant_id == tenant_id,
                    ProductVariant.product_id.in_(prod_ids),
                )
            )
            if filter_params.store_id:
                stock_stmt = stock_stmt.where(StockBalance.store_id == filter_params.store_id)
            stock_stmt = stock_stmt.group_by(ProductVariant.product_id)
            for s_row in (await db.execute(stock_stmt)).fetchall():
                stock_dict[s_row.product_id] = s_row.stock

        records: list[ProductPerformanceRecord] = []
        tot_units = 0
        for r in rows:
            units = r.units_sold or 0
            tot_units += units
            stock = stock_dict.get(r.product_id, 0)
            gross = Decimal(str(r.gross_revenue or "0.00"))

            # Determine movement status
            if stock <= 0 and units > 0:
                movement = "OUT_OF_STOCK"
            elif units >= 10:
                movement = "FAST_MOVING"
            elif units == 0:
                movement = "SLOW_MOVING"
            else:
                movement = "STEADY"

            records.append(
                ProductPerformanceRecord(
                    product_id=r.product_id,
                    product_name=r.product_name,
                    category_name=r.category_name,
                    units_sold=units,
                    gross_revenue=gross,
                    net_revenue=gross,
                    total_orders=r.total_orders or 0,
                    current_stock_on_hand=stock,
                    movement_status=movement,
                )
            )

        return ProductPerformanceReportResponse(
            tenant_id=tenant_id,
            start_date=start_dt,
            end_date=end_dt,
            total_products_sold=len(records),
            total_units_sold=tot_units,
            records=records,
        )

    @staticmethod
    async def get_category_performance(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        filter_params: ReportDateRangeFilter,
    ) -> CategoryPerformanceReportResponse:
        start_dt, end_dt = ReportingService.resolve_date_bounds(filter_params)

        order_filter = [
            Order.tenant_id == tenant_id,
            Order.created_at >= start_dt,
            Order.created_at <= end_dt,
            Order.status != "CANCELLED",
        ]
        if filter_params.store_id:
            order_filter.append(Order.store_id == filter_params.store_id)

        stmt = (
            select(
                Category.id.label("category_id"),
                func.coalesce(Category.name, "Uncategorized").label("category_name"),
                func.sum(OrderItem.quantity).label("units_sold"),
                func.sum(OrderItem.total_price).label("gross_revenue"),
                func.count(distinct(OrderItem.order_id)).label("orders_count"),
            )
            .select_from(OrderItem)
            .join(Order, OrderItem.order_id == Order.id)
            .join(ProductVariant, OrderItem.variant_id == ProductVariant.id)
            .join(Product, ProductVariant.product_id == Product.id)
            .outerjoin(Category, Product.category_id == Category.id)
            .where(*order_filter)
            .group_by(Category.id, Category.name)
            .order_by(func.sum(OrderItem.total_price).desc())
        )
        rows = (await db.execute(stmt)).fetchall()

        total_cat_rev = sum(Decimal(str(r.gross_revenue or "0.00")) for r in rows)

        records: list[CategoryPerformanceRecord] = []
        for r in rows:
            rev = Decimal(str(r.gross_revenue or "0.00"))
            share = (
                (rev / total_cat_rev * Decimal("100.0")).quantize(Decimal("0.01"))
                if total_cat_rev > Decimal("0.00")
                else Decimal("0.00")
            )
            records.append(
                CategoryPerformanceRecord(
                    category_id=r.category_id,
                    category_name=r.category_name,
                    units_sold=r.units_sold or 0,
                    gross_revenue=rev,
                    orders_count=r.orders_count or 0,
                    revenue_share_percentage=share,
                )
            )

        return CategoryPerformanceReportResponse(
            tenant_id=tenant_id,
            start_date=start_dt,
            end_date=end_dt,
            records=records,
        )

    # -------------------------------------------------------------------------
    # 4. Inventory & Stock Valuation Reports
    # -------------------------------------------------------------------------
    @staticmethod
    async def get_inventory_report(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        filter_params: ReportDateRangeFilter,
    ) -> InventoryReportResponse:
        bal_filter = [StockBalance.tenant_id == tenant_id]
        if filter_params.store_id:
            bal_filter.append(StockBalance.store_id == filter_params.store_id)

        # 1. Stock balances per variant and store
        stmt = (
            select(
                StockBalance.variant_id,
                ProductVariant.sku,
                Product.name.label("product_name"),
                ProductVariant.name.label("variant_name"),
                StockBalance.store_id,
                Store.name.label("store_name"),
                StockBalance.on_hand_qty,
                StockBalance.reserved_qty,
                StockBalance.available_qty,
                StockBalance.in_transit_qty,
                ProductVariant.base_price,
                StockBalance.low_stock_alert,
            )
            .join(ProductVariant, StockBalance.variant_id == ProductVariant.id)
            .join(Product, ProductVariant.product_id == Product.id)
            .join(Store, StockBalance.store_id == Store.id)
            .where(*bal_filter)
            .order_by(Product.name, ProductVariant.sku)
        )
        rows = (await db.execute(stmt)).fetchall()

        # Fetch latest unit_cost from stock receipt items for accurate valuation
        var_ids = [r.variant_id for r in rows]
        cost_dict: dict[UUID, Decimal] = {}
        if var_ids:
            cost_subq = (
                select(
                    StockReceiptItem.variant_id,
                    StockReceiptItem.unit_cost,
                    func.row_number()
                    .over(
                        partition_by=StockReceiptItem.variant_id,
                        order_by=StockReceiptItem.created_at.desc(),
                    )
                    .label("rn"),
                )
                .where(StockReceiptItem.variant_id.in_(var_ids))
                .subquery()
            )
            cost_stmt = select(cost_subq.c.variant_id, cost_subq.c.unit_cost).where(
                cost_subq.c.rn == 1
            )
            for c_row in (await db.execute(cost_stmt)).fetchall():
                cost_dict[c_row.variant_id] = Decimal(str(c_row.unit_cost))

        total_on_hand = 0
        total_reserved = 0
        total_available = 0
        total_val_cost = Decimal("0.00")
        total_val_retail = Decimal("0.00")
        low_stock_cnt = 0
        out_of_stock_cnt = 0

        stock_records: list[StockBalanceReportRecord] = []
        for r in rows:
            on_hand = r.on_hand_qty or 0
            reserved = r.reserved_qty or 0
            available = r.available_qty or 0
            in_transit = r.in_transit_qty or 0
            base_p = Decimal(str(r.base_price or "0.00"))
            u_cost = cost_dict.get(r.variant_id, base_p)

            val_cost = (Decimal(on_hand) * u_cost).quantize(Decimal("0.01"))
            val_retail = (Decimal(on_hand) * base_p).quantize(Decimal("0.01"))

            total_on_hand += on_hand
            total_reserved += reserved
            total_available += available
            total_val_cost += val_cost
            total_val_retail += val_retail

            if available <= 0:
                out_of_stock_cnt += 1
            elif r.low_stock_alert:
                low_stock_cnt += 1

            stock_records.append(
                StockBalanceReportRecord(
                    variant_id=r.variant_id,
                    sku=r.sku,
                    product_name=r.product_name,
                    variant_name=r.variant_name,
                    store_id=r.store_id,
                    store_name=r.store_name,
                    on_hand_qty=on_hand,
                    reserved_qty=reserved,
                    available_qty=available,
                    in_transit_qty=in_transit,
                    unit_cost=u_cost,
                    valuation_at_cost=val_cost,
                    valuation_at_retail=val_retail,
                    low_stock_alert=r.low_stock_alert,
                )
            )

        # 2. Damaged / Loss Stock from Inventory Ledger
        start_dt, end_dt = ReportingService.resolve_date_bounds(filter_params)
        dmg_filter = [
            InventoryLedger.tenant_id == tenant_id,
            InventoryLedger.movement_type.in_(["DAMAGE", "LOSS"]),
            InventoryLedger.created_at >= start_dt,
            InventoryLedger.created_at <= end_dt,
        ]
        if filter_params.store_id:
            dmg_filter.append(InventoryLedger.store_id == filter_params.store_id)

        dmg_stmt = (
            select(
                InventoryLedger.store_id,
                Store.name.label("store_name"),
                InventoryLedger.variant_id,
                ProductVariant.sku,
                Product.name.label("product_name"),
                InventoryLedger.movement_type,
                func.sum(InventoryLedger.quantity).label("quantity"),
            )
            .join(Store, InventoryLedger.store_id == Store.id)
            .join(ProductVariant, InventoryLedger.variant_id == ProductVariant.id)
            .join(Product, ProductVariant.product_id == Product.id)
            .where(*dmg_filter)
            .group_by(
                InventoryLedger.store_id,
                Store.name,
                InventoryLedger.variant_id,
                ProductVariant.sku,
                Product.name,
                InventoryLedger.movement_type,
            )
        )
        dmg_rows = (await db.execute(dmg_stmt)).fetchall()
        damaged_records = [
            DamagedStockReportRecord(
                store_id=dr.store_id,
                store_name=dr.store_name,
                variant_id=dr.variant_id,
                sku=dr.sku,
                product_name=dr.product_name,
                movement_type=dr.movement_type,
                quantity=dr.quantity,
                total_cost_impact=(
                    Decimal(dr.quantity) * cost_dict.get(dr.variant_id, Decimal("0.00"))
                ).quantize(Decimal("0.01")),
            )
            for dr in dmg_rows
        ]

        # 3. Overall Ledger Movement Summary
        mov_filter = [
            InventoryLedger.tenant_id == tenant_id,
            InventoryLedger.created_at >= start_dt,
            InventoryLedger.created_at <= end_dt,
        ]
        if filter_params.store_id:
            mov_filter.append(InventoryLedger.store_id == filter_params.store_id)

        mov_stmt = (
            select(
                InventoryLedger.movement_type,
                func.count(InventoryLedger.id).label("txn_count"),
                func.sum(InventoryLedger.quantity).label("units"),
            )
            .where(*mov_filter)
            .group_by(InventoryLedger.movement_type)
        )
        mov_rows = (await db.execute(mov_stmt)).fetchall()
        ledger_movements = [
            InventoryLedgerMovementSummary(
                movement_type=mr.movement_type,
                transactions_count=mr.txn_count,
                units_moved=mr.units,
            )
            for mr in mov_rows
        ]

        return InventoryReportResponse(
            tenant_id=tenant_id,
            store_id=filter_params.store_id,
            total_on_hand_units=total_on_hand,
            total_reserved_units=total_reserved,
            total_available_units=total_available,
            total_valuation_at_cost=total_val_cost,
            total_valuation_at_retail=total_val_retail,
            low_stock_count=low_stock_cnt,
            out_of_stock_count=out_of_stock_cnt,
            stock_records=stock_records,
            damaged_records=damaged_records,
            ledger_movements=ledger_movements,
        )

    # -------------------------------------------------------------------------
    # 5. Order Analytics & Fulfillment Performance
    # -------------------------------------------------------------------------
    @staticmethod
    async def get_order_analytics(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        filter_params: ReportDateRangeFilter,
    ) -> OrderAnalyticsResponse:
        start_dt, end_dt = ReportingService.resolve_date_bounds(filter_params)

        order_filter = [
            Order.tenant_id == tenant_id,
            Order.created_at >= start_dt,
            Order.created_at <= end_dt,
        ]
        if filter_params.store_id:
            order_filter.append(Order.store_id == filter_params.store_id)

        # 1. Total and Status breakdown
        stmt = (
            select(
                Order.status,
                func.count(Order.id).label("cnt"),
                func.coalesce(func.sum(Order.total_amount), Decimal("0.00")).label("val"),
            )
            .where(*order_filter)
            .group_by(Order.status)
        )
        rows = (await db.execute(stmt)).fetchall()

        total_orders = sum(r.cnt for r in rows)
        status_breakdown: list[OrderStatusBreakdown] = []
        cancellation_cnt = 0
        return_cnt = 0

        for r in rows:
            pct = (
                (Decimal(r.cnt) / Decimal(total_orders) * Decimal("100.0")).quantize(
                    Decimal("0.01")
                )
                if total_orders > 0
                else Decimal("0.00")
            )
            if r.status == "CANCELLED":
                cancellation_cnt = r.cnt
            elif r.status == "RETURNED":
                return_cnt = r.cnt

            status_breakdown.append(
                OrderStatusBreakdown(
                    status=r.status,
                    count=r.cnt,
                    percentage=pct,
                    value=Decimal(str(r.val)),
                )
            )

        cancel_rate = (
            (Decimal(cancellation_cnt) / Decimal(total_orders) * Decimal("100.0")).quantize(
                Decimal("0.01")
            )
            if total_orders > 0
            else Decimal("0.00")
        )
        delivered_cnt = sum(r.cnt for r in rows if r.status == "DELIVERED")
        return_rate = (
            (Decimal(return_cnt) / Decimal(delivered_cnt) * Decimal("100.0")).quantize(
                Decimal("0.01")
            )
            if delivered_cnt > 0
            else Decimal("0.00")
        )

        # 2. Fulfillment lead time (Order Created -> Dispatched)
        ship_filter = [
            Shipment.tenant_id == tenant_id,
            Shipment.created_at >= start_dt,
            Shipment.created_at <= end_dt,
            Shipment.dispatched_at.is_not(None),
        ]
        if filter_params.store_id:
            ship_filter.append(Shipment.store_id == filter_params.store_id)

        lead_stmt = (
            select(
                func.avg(func.extract("epoch", Shipment.dispatched_at - Order.created_at) / 3600.0)
            )
            .join(Order, Shipment.order_id == Order.id)
            .where(*ship_filter)
        )
        avg_lead = (await db.execute(lead_stmt)).scalar()
        avg_lead_dec = Decimal(str(avg_lead)).quantize(Decimal("0.01")) if avg_lead else None

        # 3. Delivery transit time (Dispatched -> Delivered)
        transit_filter = [
            Shipment.tenant_id == tenant_id,
            Shipment.created_at >= start_dt,
            Shipment.created_at <= end_dt,
            Shipment.delivered_at.is_not(None),
            Shipment.dispatched_at.is_not(None),
        ]
        if filter_params.store_id:
            transit_filter.append(Shipment.store_id == filter_params.store_id)

        transit_stmt = select(
            func.avg(func.extract("epoch", Shipment.delivered_at - Shipment.dispatched_at) / 3600.0)
        ).where(*transit_filter)
        avg_transit = (await db.execute(transit_stmt)).scalar()
        avg_transit_dec = (
            Decimal(str(avg_transit)).quantize(Decimal("0.01")) if avg_transit else None
        )

        return OrderAnalyticsResponse(
            tenant_id=tenant_id,
            start_date=start_dt,
            end_date=end_dt,
            total_orders=total_orders,
            status_breakdown=status_breakdown,
            cancellation_count=cancellation_cnt,
            cancellation_rate=cancel_rate,
            return_count=return_cnt,
            return_rate=return_rate,
            average_fulfillment_lead_time_hours=avg_lead_dec,
            average_delivery_transit_time_hours=avg_transit_dec,
        )

    # -------------------------------------------------------------------------
    # 6. Payment & Financial Reconciliation
    # -------------------------------------------------------------------------
    @staticmethod
    async def get_payment_report(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        filter_params: ReportDateRangeFilter,
    ) -> PaymentReportResponse:
        start_dt, end_dt = ReportingService.resolve_date_bounds(filter_params)

        pay_filter = [
            PaymentTransaction.tenant_id == tenant_id,
            PaymentTransaction.created_at >= start_dt,
            PaymentTransaction.created_at <= end_dt,
        ]

        # Total captured, fees, tax
        pay_stmt = select(
            func.coalesce(
                func.sum(
                    case(
                        (PaymentTransaction.status == "captured", PaymentTransaction.amount),
                        else_=Decimal("0.00"),
                    )
                ),
                Decimal("0.00"),
            ).label("captured"),
            func.coalesce(func.sum(PaymentTransaction.gateway_fee), Decimal("0.00")).label("fees"),
            func.coalesce(func.sum(PaymentTransaction.gateway_tax), Decimal("0.00")).label("tax"),
        ).where(*pay_filter)
        pay_res = (await db.execute(pay_stmt)).one()
        captured = Decimal(str(pay_res.captured or "0.00"))
        fees = Decimal(str(pay_res.fees or "0.00"))
        tax = Decimal(str(pay_res.tax or "0.00"))

        # Refunds
        ref_stmt = select(
            func.coalesce(
                func.sum(
                    case((Refund.status == "succeeded", Refund.amount), else_=Decimal("0.00"))
                ),
                Decimal("0.00"),
            )
        ).where(
            Refund.tenant_id == tenant_id,
            Refund.created_at >= start_dt,
            Refund.created_at <= end_dt,
        )
        refunded = Decimal(str((await db.execute(ref_stmt)).scalar() or "0.00"))

        # Payment Methods breakdown
        pm_stmt = (
            select(
                PaymentTransaction.payment_method,
                func.count(PaymentTransaction.id).label("cnt"),
                func.coalesce(func.sum(PaymentTransaction.amount), Decimal("0.00")).label("tot"),
            )
            .where(*pay_filter)
            .group_by(PaymentTransaction.payment_method)
        )
        pm_rows = (await db.execute(pm_stmt)).fetchall()
        total_pm_val = sum(Decimal(str(r.tot)) for r in pm_rows)

        payment_methods = [
            PaymentMethodSummary(
                payment_method=r.payment_method,
                transaction_count=r.cnt,
                total_amount=Decimal(str(r.tot)),
                share_percentage=(
                    (Decimal(str(r.tot)) / total_pm_val * Decimal("100.0")).quantize(
                        Decimal("0.01")
                    )
                    if total_pm_val > Decimal("0.00")
                    else Decimal("0.00")
                ),
            )
            for r in pm_rows
        ]

        # COD Settlement Breakdown
        cod_stmt = select(
            func.count(CodSettlement.id).label("cnt"),
            func.coalesce(func.sum(CodSettlement.amount_collected), Decimal("0.00")).label("tot"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            CodSettlement.settlement_status == "pending_deposit",
                            CodSettlement.amount_collected,
                        ),
                        else_=Decimal("0.00"),
                    )
                ),
                Decimal("0.00"),
            ).label("pending"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            CodSettlement.settlement_status == "deposited_to_bank",
                            CodSettlement.amount_collected,
                        ),
                        else_=Decimal("0.00"),
                    )
                ),
                Decimal("0.00"),
            ).label("deposited"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            CodSettlement.settlement_status == "reconciled",
                            CodSettlement.amount_collected,
                        ),
                        else_=Decimal("0.00"),
                    )
                ),
                Decimal("0.00"),
            ).label("reconciled"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            CodSettlement.settlement_status == "discrepancy",
                            CodSettlement.amount_collected,
                        ),
                        else_=Decimal("0.00"),
                    )
                ),
                Decimal("0.00"),
            ).label("discrepancy"),
        ).where(
            CodSettlement.tenant_id == tenant_id,
            CodSettlement.collected_at >= start_dt,
            CodSettlement.collected_at <= end_dt,
        )
        cod_res = (await db.execute(cod_stmt)).one()

        cod_settlement = CodSettlementSummary(
            total_cod_orders=cod_res.cnt or 0,
            total_cod_collected=Decimal(str(cod_res.tot or "0.00")),
            pending_deposit_amount=Decimal(str(cod_res.pending or "0.00")),
            deposited_amount=Decimal(str(cod_res.deposited or "0.00")),
            reconciled_amount=Decimal(str(cod_res.reconciled or "0.00")),
            discrepancy_amount=Decimal(str(cod_res.discrepancy or "0.00")),
        )

        net_rev = (captured - refunded - fees - tax).quantize(Decimal("0.01"))

        return PaymentReportResponse(
            tenant_id=tenant_id,
            start_date=start_dt,
            end_date=end_dt,
            total_captured_amount=captured,
            total_refunded_amount=refunded,
            total_gateway_fees=fees,
            total_gateway_tax=tax,
            net_realized_revenue=net_rev,
            payment_methods=payment_methods,
            cod_settlement=cod_settlement,
        )

    # -------------------------------------------------------------------------
    # 7. Delivery & Logistics Analytics
    # -------------------------------------------------------------------------
    @staticmethod
    async def get_delivery_analytics(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        filter_params: ReportDateRangeFilter,
    ) -> DeliveryAnalyticsResponse:
        start_dt, end_dt = ReportingService.resolve_date_bounds(filter_params)

        ship_filter = [
            Shipment.tenant_id == tenant_id,
            Shipment.created_at >= start_dt,
            Shipment.created_at <= end_dt,
        ]
        if filter_params.store_id:
            ship_filter.append(Shipment.store_id == filter_params.store_id)

        # 1. Macro Delivery Metrics
        macro_stmt = select(
            func.count(Shipment.id).label("total"),
            func.count(case((Shipment.delivery_type == "INTERNAL", Shipment.id))).label(
                "internal_cnt"
            ),
            func.count(case((Shipment.delivery_type == "COURIER", Shipment.id))).label(
                "courier_cnt"
            ),
            func.count(case((Shipment.status == "DELIVERED", Shipment.id))).label("delivered_cnt"),
            func.count(
                case(
                    (
                        (Shipment.status == "DELIVERED") & (Shipment.attempt_count <= 1),
                        Shipment.id,
                    )
                )
            ).label("first_attempt_cnt"),
            func.count(case((Shipment.status == "RETURNED_TO_STORE", Shipment.id))).label(
                "rto_cnt"
            ),
        ).where(*ship_filter)
        m = (await db.execute(macro_stmt)).one()

        tot = m.total or 0
        deliv = m.delivered_cnt or 0
        first_att = m.first_attempt_cnt or 0
        rto = m.rto_cnt or 0

        first_att_rate = (
            (Decimal(first_att) / Decimal(deliv) * Decimal("100.0")).quantize(Decimal("0.01"))
            if deliv > 0
            else Decimal("0.00")
        )
        overall_success = (
            (Decimal(deliv) / Decimal(deliv + rto) * Decimal("100.0")).quantize(Decimal("0.01"))
            if (deliv + rto) > 0
            else Decimal("0.00")
        )
        rto_rate = (
            (Decimal(rto) / Decimal(tot) * Decimal("100.0")).quantize(Decimal("0.01"))
            if tot > 0
            else Decimal("0.00")
        )

        # Failure reasons
        fail_stmt = (
            select(Shipment.last_attempt_reason, func.count(Shipment.id))
            .where(
                *ship_filter,
                Shipment.last_attempt_reason.is_not(None),
            )
            .group_by(Shipment.last_attempt_reason)
        )
        failure_reasons = {r[0]: r[1] for r in (await db.execute(fail_stmt)).fetchall() if r[0]}

        # Rider Performance
        rider_stmt = (
            select(
                DeliveryPersonnel.id.label("personnel_id"),
                DeliveryPersonnel.employee_code,
                DeliveryPersonnel.full_name.label("rider_name"),
                func.count(Shipment.id).label("assigned_cnt"),
                func.count(case((Shipment.status == "DELIVERED", Shipment.id))).label(
                    "delivered_cnt"
                ),
                func.count(
                    case(
                        (
                            Shipment.status.in_(["FAILED_ATTEMPT", "RETURNED_TO_STORE"]),
                            Shipment.id,
                        )
                    )
                ).label("failed_cnt"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                (Shipment.status == "DELIVERED") & Shipment.is_cod,
                                Shipment.cod_amount,
                            ),
                            else_=Decimal("0.00"),
                        )
                    ),
                    Decimal("0.00"),
                ).label("cod_collected"),
                func.avg(
                    case(
                        (
                            (Shipment.status == "DELIVERED")
                            & Shipment.delivered_at.is_not(None)
                            & Shipment.dispatched_at.is_not(None),
                            func.extract("epoch", Shipment.delivered_at - Shipment.dispatched_at)
                            / 60.0,
                        )
                    )
                ).label("avg_mins"),
            )
            .join(Shipment, DeliveryPersonnel.id == Shipment.assigned_personnel_id)
            .where(*ship_filter)
            .group_by(
                DeliveryPersonnel.id,
                DeliveryPersonnel.employee_code,
                DeliveryPersonnel.full_name,
            )
        )
        rider_rows = (await db.execute(rider_stmt)).fetchall()
        rider_performance = [
            RiderPerformanceRecord(
                personnel_id=rr.personnel_id,
                employee_code=rr.employee_code,
                rider_name=rr.rider_name,
                total_assigned=rr.assigned_cnt,
                total_delivered=rr.delivered_cnt,
                total_failed=rr.failed_cnt,
                success_rate=(
                    (
                        Decimal(rr.delivered_cnt) / Decimal(rr.assigned_cnt) * Decimal("100.0")
                    ).quantize(Decimal("0.01"))
                    if rr.assigned_cnt > 0
                    else Decimal("0.00")
                ),
                cod_collected=Decimal(str(rr.cod_collected)),
                average_delivery_time_minutes=(
                    Decimal(str(rr.avg_mins)).quantize(Decimal("0.01")) if rr.avg_mins else None
                ),
            )
            for rr in rider_rows
        ]

        # Courier Performance
        courier_stmt = (
            select(
                Shipment.courier_provider,
                func.count(Shipment.id).label("booked_cnt"),
                func.count(case((Shipment.status == "DELIVERED", Shipment.id))).label(
                    "delivered_cnt"
                ),
                func.count(case((Shipment.status == "RETURNED_TO_STORE", Shipment.id))).label(
                    "rto_cnt"
                ),
            )
            .where(
                *ship_filter,
                Shipment.delivery_type == "COURIER",
                Shipment.courier_provider.is_not(None),
            )
            .group_by(Shipment.courier_provider)
        )
        courier_rows = (await db.execute(courier_stmt)).fetchall()
        courier_performance = [
            CourierPerformanceRecord(
                courier_provider=cr.courier_provider,
                total_booked=cr.booked_cnt,
                total_delivered=cr.delivered_cnt,
                total_rto=cr.rto_cnt,
                success_rate=(
                    (
                        Decimal(cr.delivered_cnt) / Decimal(cr.booked_cnt) * Decimal("100.0")
                    ).quantize(Decimal("0.01"))
                    if cr.booked_cnt > 0
                    else Decimal("0.00")
                ),
            )
            for cr in courier_rows
        ]

        return DeliveryAnalyticsResponse(
            tenant_id=tenant_id,
            start_date=start_dt,
            end_date=end_dt,
            total_shipments=tot,
            internal_fleet_count=m.internal_cnt or 0,
            courier_count=m.courier_cnt or 0,
            first_attempt_delivery_rate=first_att_rate,
            overall_delivery_success_rate=overall_success,
            rto_rate=rto_rate,
            failure_reasons=failure_reasons,
            rider_performance=rider_performance,
            courier_performance=courier_performance,
        )

    # -------------------------------------------------------------------------
    # 8. Customer Analytics & LTV
    # -------------------------------------------------------------------------
    @staticmethod
    async def get_customer_analytics(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        filter_params: ReportDateRangeFilter,
    ) -> CustomerAnalyticsResponse:
        start_dt, end_dt = ReportingService.resolve_date_bounds(filter_params)

        order_filter = [
            Order.tenant_id == tenant_id,
            Order.status != "CANCELLED",
        ]

        # 1. Total unique customers who ever placed an order
        stmt_tot = select(func.count(distinct(Order.customer_id))).where(*order_filter)
        total_unique = (await db.execute(stmt_tot)).scalar() or 0

        # 2. Lifetime orders count per customer
        stmt_cust = (
            select(
                Order.customer_id,
                func.count(Order.id).label("lifetime_orders"),
                func.min(Order.created_at).label("first_order_at"),
                func.max(Order.created_at).label("last_order_at"),
                func.sum(Order.total_amount).label("total_spend"),
            )
            .where(*order_filter)
            .group_by(Order.customer_id)
        )
        cust_rows = (await db.execute(stmt_cust)).fetchall()

        new_customers = 0
        repeat_customers = 0
        freq_dist = {"1_order": 0, "2_to_3_orders": 0, "4_or_more_orders": 0}

        for cr in cust_rows:
            l_cnt = cr.lifetime_orders
            if l_cnt == 1:
                freq_dist["1_order"] += 1
            elif 2 <= l_cnt <= 3:
                freq_dist["2_to_3_orders"] += 1
            else:
                freq_dist["4_or_more_orders"] += 1

            if l_cnt >= 2:
                repeat_customers += 1

            # New if first order occurred in date range
            if cr.first_order_at and start_dt <= cr.first_order_at <= end_dt:
                new_customers += 1

        repeat_rate = (
            (Decimal(repeat_customers) / Decimal(total_unique) * Decimal("100.0")).quantize(
                Decimal("0.01")
            )
            if total_unique > 0
            else Decimal("0.00")
        )

        # 3. Top 10 Customers by Spend
        top_stmt = (
            select(
                Order.customer_id,
                Order.customer_name,
                Order.customer_email,
                Order.customer_phone,
                func.count(Order.id).label("total_orders"),
                func.sum(Order.total_amount).label("total_spend"),
                func.max(Order.created_at).label("last_order_date"),
            )
            .where(*order_filter)
            .group_by(
                Order.customer_id,
                Order.customer_name,
                Order.customer_email,
                Order.customer_phone,
            )
            .order_by(func.sum(Order.total_amount).desc())
            .limit(10)
        )
        top_rows = (await db.execute(top_stmt)).fetchall()

        top_customers = [
            TopCustomerRecord(
                customer_id=tr.customer_id,
                customer_name=tr.customer_name,
                customer_email=tr.customer_email,
                customer_phone=tr.customer_phone,
                total_orders=tr.total_orders,
                total_spend=Decimal(str(tr.total_spend or "0.00")),
                average_order_value=(
                    Decimal(str(tr.total_spend or "0.00")) / tr.total_orders
                ).quantize(Decimal("0.01")),
                last_order_date=tr.last_order_date,
            )
            for tr in top_rows
        ]

        return CustomerAnalyticsResponse(
            tenant_id=tenant_id,
            start_date=start_dt,
            end_date=end_dt,
            total_unique_customers=total_unique,
            new_customers_count=new_customers,
            repeat_customers_count=repeat_customers,
            repeat_customer_rate=repeat_rate,
            purchase_frequency_distribution=freq_dist,
            top_customers=top_customers,
        )

    # -------------------------------------------------------------------------
    # 9. Multi-Store Reporting
    # -------------------------------------------------------------------------
    @staticmethod
    async def get_multi_store_comparison(
        db: AsyncSession,
        *,
        tenant_id: UUID,
        filter_params: ReportDateRangeFilter,
    ) -> MultiStoreReportResponse:
        start_dt, end_dt = ReportingService.resolve_date_bounds(filter_params)

        # 1. Fetch all stores for this tenant
        stores_stmt = select(Store).where(Store.tenant_id == tenant_id).order_by(Store.name)
        stores = (await db.execute(stores_stmt)).scalars().all()

        # 2. Sales per store in date range
        sales_stmt = (
            select(
                Order.store_id,
                func.count(Order.id).label("total_orders"),
                func.coalesce(
                    func.sum(
                        case((Order.status != "CANCELLED", Order.subtotal), else_=Decimal("0.00"))
                    ),
                    Decimal("0.00"),
                ).label("gross_sales"),
                func.coalesce(
                    func.sum(
                        case(
                            (Order.status != "CANCELLED", Order.total_amount), else_=Decimal("0.00")
                        )
                    ),
                    Decimal("0.00"),
                ).label("net_sales"),
            )
            .where(
                Order.tenant_id == tenant_id,
                Order.created_at >= start_dt,
                Order.created_at <= end_dt,
            )
            .group_by(Order.store_id)
        )
        sales_dict = {
            r.store_id: {
                "orders": r.total_orders,
                "gross": Decimal(str(r.gross_sales)),
                "net": Decimal(str(r.net_sales)),
            }
            for r in (await db.execute(sales_stmt)).fetchall()
        }

        # 3. Stock on hand & valuation per store
        stock_stmt = (
            select(
                StockBalance.store_id,
                func.coalesce(func.sum(StockBalance.on_hand_qty), 0).label("units"),
                func.coalesce(
                    func.sum(StockBalance.on_hand_qty * ProductVariant.base_price),
                    Decimal("0.00"),
                ).label("val"),
            )
            .join(ProductVariant, StockBalance.variant_id == ProductVariant.id)
            .where(StockBalance.tenant_id == tenant_id)
            .group_by(StockBalance.store_id)
        )
        stock_dict = {
            r.store_id: {"units": r.units, "val": Decimal(str(r.val))}
            for r in (await db.execute(stock_stmt)).fetchall()
        }

        # 4. Active shipments per store
        ship_stmt = (
            select(Shipment.store_id, func.count(Shipment.id).label("active_shipments"))
            .where(
                Shipment.tenant_id == tenant_id,
                Shipment.status.in_(["ASSIGNED", "PICKED_UP", "IN_TRANSIT", "OUT_FOR_DELIVERY"]),
            )
            .group_by(Shipment.store_id)
        )
        ship_dict = {
            r.store_id: r.active_shipments for r in (await db.execute(ship_stmt)).fetchall()
        }

        total_tenant_net = sum(d["net"] for d in sales_dict.values())

        records: list[StoreComparisonRecord] = []
        for s in stores:
            s_sales = sales_dict.get(
                s.id, {"orders": 0, "gross": Decimal("0.00"), "net": Decimal("0.00")}
            )
            s_stock = stock_dict.get(s.id, {"units": 0, "val": Decimal("0.00")})
            s_ships = ship_dict.get(s.id, 0)

            share = (
                (s_sales["net"] / total_tenant_net * Decimal("100.0")).quantize(Decimal("0.01"))
                if total_tenant_net > Decimal("0.00")
                else Decimal("0.00")
            )

            records.append(
                StoreComparisonRecord(
                    store_id=s.id,
                    store_name=s.name,
                    store_code=s.code,
                    city=s.city,
                    total_orders=s_sales["orders"],
                    gross_sales=s_sales["gross"],
                    net_sales=s_sales["net"],
                    revenue_share_percentage=share,
                    stock_units_on_hand=s_stock["units"],
                    stock_valuation_at_cost=s_stock["val"],
                    active_shipments_count=s_ships,
                )
            )

        return MultiStoreReportResponse(
            tenant_id=tenant_id,
            start_date=start_dt,
            end_date=end_dt,
            stores=records,
        )

    # -------------------------------------------------------------------------
    # 10. Platform Overview Analytics (TechMasters Super Admin)
    # -------------------------------------------------------------------------
    @staticmethod
    async def get_platform_overview(
        db: AsyncSession,
        *,
        filter_params: ReportDateRangeFilter,
    ) -> PlatformOverviewResponse:
        start_dt, end_dt = ReportingService.resolve_date_bounds(filter_params)

        # Macro platform aggregates
        total_tenants = (
            await db.execute(select(func.count(Tenant.id)).where(Tenant.status == "active"))
        ).scalar() or 0
        total_stores = (await db.execute(select(func.count(Store.id)))).scalar() or 0
        total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0

        # Platform GMV & orders in window
        gmv_stmt = select(
            func.count(Order.id).label("total_orders"),
            func.coalesce(
                func.sum(
                    case((Order.status != "CANCELLED", Order.total_amount), else_=Decimal("0.00"))
                ),
                Decimal("0.00"),
            ).label("gmv"),
        ).where(
            Order.created_at >= start_dt,
            Order.created_at <= end_dt,
        )
        gmv_res = (await db.execute(gmv_stmt)).one()
        tot_orders = gmv_res.total_orders or 0
        gmv = Decimal(str(gmv_res.gmv or "0.00"))
        aov = (gmv / tot_orders).quantize(Decimal("0.01")) if tot_orders > 0 else Decimal("0.00")

        # Tenant comparison table
        tenants_stmt = select(Tenant).order_by(Tenant.created_at.desc())
        all_tenants = (await db.execute(tenants_stmt)).scalars().all()

        t_orders_stmt = (
            select(
                Order.tenant_id,
                func.count(Order.id).label("cnt"),
                func.coalesce(
                    func.sum(
                        case(
                            (Order.status != "CANCELLED", Order.total_amount), else_=Decimal("0.00")
                        )
                    ),
                    Decimal("0.00"),
                ).label("gmv"),
            )
            .where(Order.created_at >= start_dt, Order.created_at <= end_dt)
            .group_by(Order.tenant_id)
        )
        t_orders_dict = {
            r.tenant_id: {"cnt": r.cnt, "gmv": Decimal(str(r.gmv))}
            for r in (await db.execute(t_orders_stmt)).fetchall()
        }

        t_stores_stmt = select(Store.tenant_id, func.count(Store.id)).group_by(Store.tenant_id)
        t_stores_dict = {r[0]: r[1] for r in (await db.execute(t_stores_stmt)).fetchall()}

        t_prods_stmt = (
            select(Product.tenant_id, func.count(Product.id))
            .where(Product.status == "active")
            .group_by(Product.tenant_id)
        )
        t_prods_dict = {r[0]: r[1] for r in (await db.execute(t_prods_stmt)).fetchall()}

        tenant_records = [
            TenantComparisonRecord(
                tenant_id=t.id,
                tenant_name=t.name,
                tenant_slug=t.slug,
                status=t.status,
                store_count=t_stores_dict.get(t.id, 0),
                total_orders=t_orders_dict.get(t.id, {}).get("cnt", 0),
                gross_merchandise_value=t_orders_dict.get(t.id, {}).get("gmv", Decimal("0.00")),
                active_products_count=t_prods_dict.get(t.id, 0),
                created_at=t.created_at,
            )
            for t in all_tenants
        ]

        return PlatformOverviewResponse(
            start_date=start_dt,
            end_date=end_dt,
            total_active_tenants=total_tenants,
            total_physical_stores=total_stores,
            platform_total_orders=tot_orders,
            platform_gmv=gmv,
            platform_average_order_value=aov,
            total_registered_users=total_users,
            tenants=tenant_records,
        )

    # -------------------------------------------------------------------------
    # 11. CSV Export Generation & Audit Logging
    # -------------------------------------------------------------------------
    @staticmethod
    def format_csv(data: list[dict], fieldnames: list[str]) -> bytes:
        """
        Builds RFC-4180 standard CSV bytes prefixed with UTF-8 BOM
        for native Microsoft Excel compatibility.
        """
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in data:
            writer.writerow(row)
        # Prepend \ufeff UTF-8 BOM
        return ("\ufeff" + output.getvalue()).encode("utf-8")

    @staticmethod
    async def log_export(
        db: AsyncSession,
        *,
        tenant_id: UUID | None,
        user_id: UUID | None,
        report_type: str,
        export_format: str,
        parameters: dict,
        row_count: int,
        file_name: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> ReportExportLog:
        # Verify user existence to satisfy foreign key constraint if user_id is provided
        actual_user_id = None
        if user_id:
            user_exists = (
                await db.execute(select(User.id).where(User.id == user_id))
            ).scalar_one_or_none()
            if user_exists:
                actual_user_id = user_id

        log_entry = ReportExportLog(
            id=uuid4(),
            tenant_id=tenant_id,
            user_id=actual_user_id,
            report_type=report_type.upper(),
            export_format=export_format.upper(),
            parameters=parameters,
            row_count=row_count,
            file_name=file_name,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.add(log_entry)
        await db.commit()
        await db.refresh(log_entry)
        return log_entry
