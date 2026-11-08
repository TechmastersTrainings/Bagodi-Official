from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import SecurityPrincipal, get_security_principal, require_permission
from app.db.session import get_db
from app.modules.reports.models import ReportExportLog
from app.modules.reports.schemas import (
    CategoryPerformanceReportResponse,
    CustomerAnalyticsResponse,
    DeliveryAnalyticsResponse,
    InventoryReportResponse,
    MerchantDashboardResponse,
    MultiStoreReportResponse,
    OrderAnalyticsResponse,
    PaymentReportResponse,
    ProductPerformanceReportResponse,
    ReportDateRangeFilter,
    ReportExportLogResponse,
    SalesReportResponse,
)
from app.modules.reports.services import ReportingService

router = APIRouter(prefix="/merchant/reports", tags=["Merchant Reports & Analytics"])


# -----------------------------------------------------------------------------
# 1. Dashboard KPIs
# -----------------------------------------------------------------------------
@router.get(
    "/dashboard",
    response_model=MerchantDashboardResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission("reports:read"))],
)
async def get_merchant_dashboard(
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
    time_window: Annotated[str, Query(description="Preset window")] = "last_30_days",
    start_date: Annotated[date | None, Query(description="Optional custom start date")] = None,
    end_date: Annotated[date | None, Query(description="Optional custom end date")] = None,
    store_id: Annotated[UUID | None, Query(description="Optional store ID")] = None,
):
    filter_params = ReportDateRangeFilter(
        time_window=time_window,
        start_date=start_date,
        end_date=end_date,
        store_id=store_id,
    )
    return await ReportingService.get_merchant_dashboard(
        db, tenant_id=principal.tenant_id, filter_params=filter_params
    )


# -----------------------------------------------------------------------------
# 2. Sales & Revenue Reports
# -----------------------------------------------------------------------------
@router.get(
    "/sales",
    response_model=SalesReportResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission("reports:read"))],
)
async def get_sales_report(
    request: Request,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
    time_window: Annotated[str, Query(description="Preset window")] = "last_30_days",
    granularity: Annotated[str, Query(description="daily, weekly, monthly")] = "daily",
    start_date: Annotated[date | None, Query(description="Optional custom start date")] = None,
    end_date: Annotated[date | None, Query(description="Optional custom end date")] = None,
    store_id: Annotated[UUID | None, Query(description="Optional store ID")] = None,
    format: Annotated[Literal["json", "csv"], Query(description="Output format")] = "json",
):
    filter_params = ReportDateRangeFilter(
        time_window=time_window,
        granularity=granularity,
        start_date=start_date,
        end_date=end_date,
        store_id=store_id,
        format=format,
    )
    report = await ReportingService.get_sales_report(
        db, tenant_id=principal.tenant_id, filter_params=filter_params
    )

    if format == "csv":
        fieldnames = [
            "interval_date",
            "orders_count",
            "gross_sales",
            "discounts",
            "shipping_fees",
            "net_sales",
            "captured_revenue",
            "refunded_amount",
            "aov",
        ]
        csv_data = [r.model_dump() for r in report.records]
        csv_bytes = ReportingService.format_csv(csv_data, fieldnames)
        fname = f"sales_report_{report.start_date.strftime('%Y%m%d')}_{report.end_date.strftime('%Y%m%d')}.csv"

        await ReportingService.log_export(
            db,
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            report_type="SALES",
            export_format="CSV",
            parameters=filter_params.model_dump(mode="json"),
            row_count=len(csv_data),
            file_name=fname,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        return Response(
            content=csv_bytes,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )

    return report


# -----------------------------------------------------------------------------
# 3. Product Performance Reports
# -----------------------------------------------------------------------------
@router.get(
    "/products",
    response_model=ProductPerformanceReportResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission("reports:read"))],
)
async def get_product_performance(
    request: Request,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
    time_window: Annotated[str, Query(description="Preset window")] = "last_30_days",
    limit: Annotated[int, Query(description="Result count limit")] = 50,
    sort_by: Annotated[str, Query(description="Sort by units_sold or revenue")] = "units_sold",
    start_date: Annotated[date | None, Query(description="Optional custom start date")] = None,
    end_date: Annotated[date | None, Query(description="Optional custom end date")] = None,
    store_id: Annotated[UUID | None, Query(description="Optional store ID")] = None,
    format: Annotated[Literal["json", "csv"], Query(description="Output format")] = "json",
):
    filter_params = ReportDateRangeFilter(
        time_window=time_window,
        start_date=start_date,
        end_date=end_date,
        store_id=store_id,
        format=format,
    )
    report = await ReportingService.get_product_performance(
        db,
        tenant_id=principal.tenant_id,
        filter_params=filter_params,
        limit=limit,
        sort_by=sort_by,
    )

    if format == "csv":
        fieldnames = [
            "product_id",
            "product_name",
            "category_name",
            "units_sold",
            "gross_revenue",
            "net_revenue",
            "total_orders",
            "current_stock_on_hand",
            "movement_status",
        ]
        csv_data = [r.model_dump() for r in report.records]
        csv_bytes = ReportingService.format_csv(csv_data, fieldnames)
        fname = f"products_report_{report.start_date.strftime('%Y%m%d')}_{report.end_date.strftime('%Y%m%d')}.csv"

        await ReportingService.log_export(
            db,
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            report_type="PRODUCTS",
            export_format="CSV",
            parameters=filter_params.model_dump(mode="json"),
            row_count=len(csv_data),
            file_name=fname,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        return Response(
            content=csv_bytes,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )

    return report


# -----------------------------------------------------------------------------
# 4. Category Performance Reports
# -----------------------------------------------------------------------------
@router.get(
    "/categories",
    response_model=CategoryPerformanceReportResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission("reports:read"))],
)
async def get_category_performance(
    request: Request,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
    time_window: Annotated[str, Query(description="Preset window")] = "last_30_days",
    start_date: Annotated[date | None, Query(description="Optional custom start date")] = None,
    end_date: Annotated[date | None, Query(description="Optional custom end date")] = None,
    store_id: Annotated[UUID | None, Query(description="Optional store ID")] = None,
    format: Annotated[Literal["json", "csv"], Query(description="Output format")] = "json",
):
    filter_params = ReportDateRangeFilter(
        time_window=time_window,
        start_date=start_date,
        end_date=end_date,
        store_id=store_id,
        format=format,
    )
    report = await ReportingService.get_category_performance(
        db, tenant_id=principal.tenant_id, filter_params=filter_params
    )

    if format == "csv":
        fieldnames = [
            "category_id",
            "category_name",
            "units_sold",
            "gross_revenue",
            "orders_count",
            "revenue_share_percentage",
        ]
        csv_data = [r.model_dump() for r in report.records]
        csv_bytes = ReportingService.format_csv(csv_data, fieldnames)
        fname = f"categories_report_{report.start_date.strftime('%Y%m%d')}_{report.end_date.strftime('%Y%m%d')}.csv"

        await ReportingService.log_export(
            db,
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            report_type="CATEGORIES",
            export_format="CSV",
            parameters=filter_params.model_dump(mode="json"),
            row_count=len(csv_data),
            file_name=fname,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        return Response(
            content=csv_bytes,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )

    return report


# -----------------------------------------------------------------------------
# 5. Inventory & Stock Valuation Reports
# -----------------------------------------------------------------------------
@router.get(
    "/inventory",
    response_model=InventoryReportResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission("reports:read"))],
)
async def get_inventory_report(
    request: Request,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
    store_id: Annotated[UUID | None, Query(description="Optional store ID")] = None,
    time_window: Annotated[str, Query(description="Preset window for movements")] = "last_30_days",
    start_date: Annotated[date | None, Query(description="Optional custom start date")] = None,
    end_date: Annotated[date | None, Query(description="Optional custom end date")] = None,
    format: Annotated[Literal["json", "csv"], Query(description="Output format")] = "json",
):
    filter_params = ReportDateRangeFilter(
        store_id=store_id,
        time_window=time_window,
        start_date=start_date,
        end_date=end_date,
        format=format,
    )
    report = await ReportingService.get_inventory_report(
        db, tenant_id=principal.tenant_id, filter_params=filter_params
    )

    if format == "csv":
        fieldnames = [
            "variant_id",
            "sku",
            "product_name",
            "variant_name",
            "store_id",
            "store_name",
            "on_hand_qty",
            "reserved_qty",
            "available_qty",
            "in_transit_qty",
            "unit_cost",
            "valuation_at_cost",
            "valuation_at_retail",
            "low_stock_alert",
        ]
        csv_data = [r.model_dump() for r in report.stock_records]
        csv_bytes = ReportingService.format_csv(csv_data, fieldnames)
        fname = f"inventory_report_{filter_params.time_window}.csv"

        await ReportingService.log_export(
            db,
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            report_type="INVENTORY",
            export_format="CSV",
            parameters=filter_params.model_dump(mode="json"),
            row_count=len(csv_data),
            file_name=fname,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        return Response(
            content=csv_bytes,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )

    return report


# -----------------------------------------------------------------------------
# 6. Order Analytics Reports
# -----------------------------------------------------------------------------
@router.get(
    "/orders",
    response_model=OrderAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission("reports:read"))],
)
async def get_order_analytics(
    request: Request,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
    time_window: Annotated[str, Query(description="Preset window")] = "last_30_days",
    start_date: Annotated[date | None, Query(description="Optional custom start date")] = None,
    end_date: Annotated[date | None, Query(description="Optional custom end date")] = None,
    store_id: Annotated[UUID | None, Query(description="Optional store ID")] = None,
    format: Annotated[Literal["json", "csv"], Query(description="Output format")] = "json",
):
    filter_params = ReportDateRangeFilter(
        time_window=time_window,
        start_date=start_date,
        end_date=end_date,
        store_id=store_id,
        format=format,
    )
    report = await ReportingService.get_order_analytics(
        db, tenant_id=principal.tenant_id, filter_params=filter_params
    )

    if format == "csv":
        fieldnames = ["status", "count", "percentage", "value"]
        csv_data = [r.model_dump() for r in report.status_breakdown]
        csv_bytes = ReportingService.format_csv(csv_data, fieldnames)
        fname = f"orders_report_{report.start_date.strftime('%Y%m%d')}_{report.end_date.strftime('%Y%m%d')}.csv"

        await ReportingService.log_export(
            db,
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            report_type="ORDERS",
            export_format="CSV",
            parameters=filter_params.model_dump(mode="json"),
            row_count=len(csv_data),
            file_name=fname,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        return Response(
            content=csv_bytes,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )

    return report


# -----------------------------------------------------------------------------
# 7. Payment & Financial Reconciliation Reports
# -----------------------------------------------------------------------------
@router.get(
    "/payments",
    response_model=PaymentReportResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission("reports:read"))],
)
async def get_payment_report(
    request: Request,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
    time_window: Annotated[str, Query(description="Preset window")] = "last_30_days",
    start_date: Annotated[date | None, Query(description="Optional custom start date")] = None,
    end_date: Annotated[date | None, Query(description="Optional custom end date")] = None,
    format: Annotated[Literal["json", "csv"], Query(description="Output format")] = "json",
):
    filter_params = ReportDateRangeFilter(
        time_window=time_window,
        start_date=start_date,
        end_date=end_date,
        format=format,
    )
    report = await ReportingService.get_payment_report(
        db, tenant_id=principal.tenant_id, filter_params=filter_params
    )

    if format == "csv":
        fieldnames = ["payment_method", "transaction_count", "total_amount", "share_percentage"]
        csv_data = [r.model_dump() for r in report.payment_methods]
        csv_bytes = ReportingService.format_csv(csv_data, fieldnames)
        fname = f"payments_report_{report.start_date.strftime('%Y%m%d')}_{report.end_date.strftime('%Y%m%d')}.csv"

        await ReportingService.log_export(
            db,
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            report_type="PAYMENTS",
            export_format="CSV",
            parameters=filter_params.model_dump(mode="json"),
            row_count=len(csv_data),
            file_name=fname,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        return Response(
            content=csv_bytes,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )

    return report


# -----------------------------------------------------------------------------
# 8. Delivery & Logistics Analytics
# -----------------------------------------------------------------------------
@router.get(
    "/delivery",
    response_model=DeliveryAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission("reports:read"))],
)
async def get_delivery_analytics(
    request: Request,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
    time_window: Annotated[str, Query(description="Preset window")] = "last_30_days",
    start_date: Annotated[date | None, Query(description="Optional custom start date")] = None,
    end_date: Annotated[date | None, Query(description="Optional custom end date")] = None,
    store_id: Annotated[UUID | None, Query(description="Optional store ID")] = None,
    format: Annotated[Literal["json", "csv"], Query(description="Output format")] = "json",
):
    filter_params = ReportDateRangeFilter(
        time_window=time_window,
        start_date=start_date,
        end_date=end_date,
        store_id=store_id,
        format=format,
    )
    report = await ReportingService.get_delivery_analytics(
        db, tenant_id=principal.tenant_id, filter_params=filter_params
    )

    if format == "csv":
        fieldnames = [
            "personnel_id",
            "employee_code",
            "rider_name",
            "total_assigned",
            "total_delivered",
            "total_failed",
            "success_rate",
            "cod_collected",
            "average_delivery_time_minutes",
        ]
        csv_data = [r.model_dump() for r in report.rider_performance]
        csv_bytes = ReportingService.format_csv(csv_data, fieldnames)
        fname = f"delivery_report_{report.start_date.strftime('%Y%m%d')}_{report.end_date.strftime('%Y%m%d')}.csv"

        await ReportingService.log_export(
            db,
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            report_type="DELIVERY",
            export_format="CSV",
            parameters=filter_params.model_dump(mode="json"),
            row_count=len(csv_data),
            file_name=fname,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        return Response(
            content=csv_bytes,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )

    return report


# -----------------------------------------------------------------------------
# 9. Customer Analytics
# -----------------------------------------------------------------------------
@router.get(
    "/customers",
    response_model=CustomerAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission("reports:read"))],
)
async def get_customer_analytics(
    request: Request,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
    time_window: Annotated[str, Query(description="Preset window")] = "last_30_days",
    start_date: Annotated[date | None, Query(description="Optional custom start date")] = None,
    end_date: Annotated[date | None, Query(description="Optional custom end date")] = None,
    format: Annotated[Literal["json", "csv"], Query(description="Output format")] = "json",
):
    filter_params = ReportDateRangeFilter(
        time_window=time_window,
        start_date=start_date,
        end_date=end_date,
        format=format,
    )
    report = await ReportingService.get_customer_analytics(
        db, tenant_id=principal.tenant_id, filter_params=filter_params
    )

    if format == "csv":
        fieldnames = [
            "customer_id",
            "customer_name",
            "customer_email",
            "customer_phone",
            "total_orders",
            "total_spend",
            "average_order_value",
            "last_order_date",
        ]
        csv_data = [r.model_dump() for r in report.top_customers]
        csv_bytes = ReportingService.format_csv(csv_data, fieldnames)
        fname = f"customers_report_{report.start_date.strftime('%Y%m%d')}_{report.end_date.strftime('%Y%m%d')}.csv"

        await ReportingService.log_export(
            db,
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            report_type="CUSTOMERS",
            export_format="CSV",
            parameters=filter_params.model_dump(mode="json"),
            row_count=len(csv_data),
            file_name=fname,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        return Response(
            content=csv_bytes,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )

    return report


# -----------------------------------------------------------------------------
# 10. Multi-Store Reporting
# -----------------------------------------------------------------------------
@router.get(
    "/stores",
    response_model=MultiStoreReportResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission("reports:read"))],
)
async def get_multi_store_comparison(
    request: Request,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
    time_window: Annotated[str, Query(description="Preset window")] = "last_30_days",
    start_date: Annotated[date | None, Query(description="Optional custom start date")] = None,
    end_date: Annotated[date | None, Query(description="Optional custom end date")] = None,
    format: Annotated[Literal["json", "csv"], Query(description="Output format")] = "json",
):
    filter_params = ReportDateRangeFilter(
        time_window=time_window,
        start_date=start_date,
        end_date=end_date,
        format=format,
    )
    report = await ReportingService.get_multi_store_comparison(
        db, tenant_id=principal.tenant_id, filter_params=filter_params
    )

    if format == "csv":
        fieldnames = [
            "store_id",
            "store_name",
            "store_code",
            "city",
            "total_orders",
            "gross_sales",
            "net_sales",
            "revenue_share_percentage",
            "stock_units_on_hand",
            "stock_valuation_at_cost",
            "active_shipments_count",
        ]
        csv_data = [r.model_dump() for r in report.stores]
        csv_bytes = ReportingService.format_csv(csv_data, fieldnames)
        fname = f"stores_comparison_{report.start_date.strftime('%Y%m%d')}_{report.end_date.strftime('%Y%m%d')}.csv"

        await ReportingService.log_export(
            db,
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            report_type="STORES",
            export_format="CSV",
            parameters=filter_params.model_dump(mode="json"),
            row_count=len(csv_data),
            file_name=fname,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        return Response(
            content=csv_bytes,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )

    return report


# -----------------------------------------------------------------------------
# 11. Export Audit History
# -----------------------------------------------------------------------------
@router.get(
    "/exports/history",
    response_model=list[ReportExportLogResponse],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission("reports:read"))],
)
async def list_export_history(
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(description="Max log entries")] = 50,
):
    stmt = (
        select(ReportExportLog)
        .where(ReportExportLog.tenant_id == principal.tenant_id)
        .order_by(ReportExportLog.created_at.desc())
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all())
