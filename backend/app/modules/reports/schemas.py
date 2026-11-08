from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


# -----------------------------------------------------------------------------
# Common Query Filters
# -----------------------------------------------------------------------------
class ReportDateRangeFilter(BaseModel):
    start_date: date | datetime | None = Field(
        None, description="Start date for reporting window (inclusive)"
    )
    end_date: date | datetime | None = Field(
        None, description="End date for reporting window (inclusive)"
    )
    time_window: str = Field(
        "last_30_days",
        description="Preset window: today, yesterday, last_7_days, last_30_days, this_month, last_month, custom",
    )
    granularity: str = Field(
        "daily",
        description="Time granularity: daily, weekly, monthly",
    )
    store_id: UUID | None = Field(
        None, description="Optional store ID filter for multi-store scoping"
    )
    format: Literal["json", "csv"] = Field(
        "json", description="Output format: json (default) or csv"
    )


# -----------------------------------------------------------------------------
# 1. Merchant Dashboard
# -----------------------------------------------------------------------------
class SalesKpiCard(BaseModel):
    gross_sales: Decimal = Decimal("0.00")
    discount_total: Decimal = Decimal("0.00")
    shipping_fee_total: Decimal = Decimal("0.00")
    net_sales: Decimal = Decimal("0.00")
    total_orders: int = 0
    delivered_orders: int = 0
    cancelled_orders: int = 0
    returned_orders: int = 0
    aov: Decimal = Decimal("0.00")
    cancellation_rate: Decimal = Decimal("0.00")
    return_rate: Decimal = Decimal("0.00")
    pending_fulfillment_orders: int = 0
    out_for_delivery_shipments: int = 0


class TimeSeriesPoint(BaseModel):
    date: str
    orders_count: int = 0
    gross_sales: Decimal = Decimal("0.00")
    net_sales: Decimal = Decimal("0.00")


class ProductPerformanceRecord(BaseModel):
    product_id: UUID
    product_name: str
    category_name: str | None = None
    units_sold: int = 0
    gross_revenue: Decimal = Decimal("0.00")
    net_revenue: Decimal = Decimal("0.00")
    total_orders: int = 0
    current_stock_on_hand: int = 0
    movement_status: str = "STEADY"  # FAST_MOVING, STEADY, SLOW_MOVING, OUT_OF_STOCK


class MerchantDashboardResponse(BaseModel):
    tenant_id: UUID
    period: str
    start_date: datetime
    end_date: datetime
    store_id: UUID | None = None
    kpis: SalesKpiCard
    time_series: list[TimeSeriesPoint]
    top_selling_products: list[ProductPerformanceRecord]
    order_status_summary: dict[str, int]


# -----------------------------------------------------------------------------
# 2. Sales & Revenue Reports
# -----------------------------------------------------------------------------
class SalesIntervalRecord(BaseModel):
    interval_date: str
    orders_count: int = 0
    gross_sales: Decimal = Decimal("0.00")
    discounts: Decimal = Decimal("0.00")
    shipping_fees: Decimal = Decimal("0.00")
    net_sales: Decimal = Decimal("0.00")
    captured_revenue: Decimal = Decimal("0.00")
    refunded_amount: Decimal = Decimal("0.00")
    aov: Decimal = Decimal("0.00")


class SalesReportResponse(BaseModel):
    tenant_id: UUID
    store_id: UUID | None = None
    start_date: datetime
    end_date: datetime
    granularity: str
    summary: SalesKpiCard
    records: list[SalesIntervalRecord]


# -----------------------------------------------------------------------------
# 3. Product & Category Performance
# -----------------------------------------------------------------------------
class ProductPerformanceReportResponse(BaseModel):
    tenant_id: UUID
    start_date: datetime
    end_date: datetime
    total_products_sold: int = 0
    total_units_sold: int = 0
    records: list[ProductPerformanceRecord]


class CategoryPerformanceRecord(BaseModel):
    category_id: UUID | None = None
    category_name: str
    units_sold: int = 0
    gross_revenue: Decimal = Decimal("0.00")
    orders_count: int = 0
    revenue_share_percentage: Decimal = Decimal("0.00")


class CategoryPerformanceReportResponse(BaseModel):
    tenant_id: UUID
    start_date: datetime
    end_date: datetime
    records: list[CategoryPerformanceRecord]


# -----------------------------------------------------------------------------
# 4. Inventory & Stock Valuation Reports
# -----------------------------------------------------------------------------
class StockBalanceReportRecord(BaseModel):
    variant_id: UUID
    sku: str
    product_name: str
    variant_name: str
    store_id: UUID
    store_name: str
    on_hand_qty: int = 0
    reserved_qty: int = 0
    available_qty: int = 0
    in_transit_qty: int = 0
    unit_cost: Decimal = Decimal("0.00")
    valuation_at_cost: Decimal = Decimal("0.00")
    valuation_at_retail: Decimal = Decimal("0.00")
    low_stock_alert: bool = False


class DamagedStockReportRecord(BaseModel):
    store_id: UUID
    store_name: str
    variant_id: UUID
    sku: str
    product_name: str
    movement_type: str
    quantity: int = 0
    total_cost_impact: Decimal = Decimal("0.00")


class InventoryLedgerMovementSummary(BaseModel):
    movement_type: str
    transactions_count: int = 0
    units_moved: int = 0


class InventoryReportResponse(BaseModel):
    tenant_id: UUID
    store_id: UUID | None = None
    total_on_hand_units: int = 0
    total_reserved_units: int = 0
    total_available_units: int = 0
    total_valuation_at_cost: Decimal = Decimal("0.00")
    total_valuation_at_retail: Decimal = Decimal("0.00")
    low_stock_count: int = 0
    out_of_stock_count: int = 0
    stock_records: list[StockBalanceReportRecord]
    damaged_records: list[DamagedStockReportRecord]
    ledger_movements: list[InventoryLedgerMovementSummary]


# -----------------------------------------------------------------------------
# 5. Order Analytics & Fulfillment Lead Time
# -----------------------------------------------------------------------------
class OrderStatusBreakdown(BaseModel):
    status: str
    count: int = 0
    percentage: Decimal = Decimal("0.00")
    value: Decimal = Decimal("0.00")


class OrderAnalyticsResponse(BaseModel):
    tenant_id: UUID
    start_date: datetime
    end_date: datetime
    total_orders: int = 0
    status_breakdown: list[OrderStatusBreakdown]
    cancellation_count: int = 0
    cancellation_rate: Decimal = Decimal("0.00")
    return_count: int = 0
    return_rate: Decimal = Decimal("0.00")
    average_fulfillment_lead_time_hours: Decimal | None = None
    average_delivery_transit_time_hours: Decimal | None = None


# -----------------------------------------------------------------------------
# 6. Payment & Financial Reconciliation
# -----------------------------------------------------------------------------
class PaymentMethodSummary(BaseModel):
    payment_method: str
    transaction_count: int = 0
    total_amount: Decimal = Decimal("0.00")
    share_percentage: Decimal = Decimal("0.00")


class CodSettlementSummary(BaseModel):
    total_cod_orders: int = 0
    total_cod_collected: Decimal = Decimal("0.00")
    pending_deposit_amount: Decimal = Decimal("0.00")
    deposited_amount: Decimal = Decimal("0.00")
    reconciled_amount: Decimal = Decimal("0.00")
    discrepancy_amount: Decimal = Decimal("0.00")


class PaymentReportResponse(BaseModel):
    tenant_id: UUID
    start_date: datetime
    end_date: datetime
    total_captured_amount: Decimal = Decimal("0.00")
    total_refunded_amount: Decimal = Decimal("0.00")
    total_gateway_fees: Decimal = Decimal("0.00")
    total_gateway_tax: Decimal = Decimal("0.00")
    net_realized_revenue: Decimal = Decimal("0.00")
    payment_methods: list[PaymentMethodSummary]
    cod_settlement: CodSettlementSummary


# -----------------------------------------------------------------------------
# 7. Delivery & Logistics Analytics
# -----------------------------------------------------------------------------
class RiderPerformanceRecord(BaseModel):
    personnel_id: UUID
    employee_code: str
    rider_name: str
    total_assigned: int = 0
    total_delivered: int = 0
    total_failed: int = 0
    success_rate: Decimal = Decimal("0.00")
    cod_collected: Decimal = Decimal("0.00")
    average_delivery_time_minutes: Decimal | None = None


class CourierPerformanceRecord(BaseModel):
    courier_provider: str
    total_booked: int = 0
    total_delivered: int = 0
    total_rto: int = 0
    success_rate: Decimal = Decimal("0.00")


class DeliveryAnalyticsResponse(BaseModel):
    tenant_id: UUID
    start_date: datetime
    end_date: datetime
    total_shipments: int = 0
    internal_fleet_count: int = 0
    courier_count: int = 0
    first_attempt_delivery_rate: Decimal = Decimal("0.00")
    overall_delivery_success_rate: Decimal = Decimal("0.00")
    rto_rate: Decimal = Decimal("0.00")
    failure_reasons: dict[str, int]
    rider_performance: list[RiderPerformanceRecord]
    courier_performance: list[CourierPerformanceRecord]


# -----------------------------------------------------------------------------
# 8. Customer Analytics
# -----------------------------------------------------------------------------
class TopCustomerRecord(BaseModel):
    customer_id: UUID
    customer_name: str
    customer_email: str | None = None
    customer_phone: str
    total_orders: int = 0
    total_spend: Decimal = Decimal("0.00")
    average_order_value: Decimal = Decimal("0.00")
    last_order_date: datetime


class CustomerAnalyticsResponse(BaseModel):
    tenant_id: UUID
    start_date: datetime
    end_date: datetime
    total_unique_customers: int = 0
    new_customers_count: int = 0
    repeat_customers_count: int = 0
    repeat_customer_rate: Decimal = Decimal("0.00")
    purchase_frequency_distribution: dict[str, int]  # 1_order, 2_to_3_orders, 4_or_more_orders
    top_customers: list[TopCustomerRecord]


# -----------------------------------------------------------------------------
# 9. Multi-Store Reporting
# -----------------------------------------------------------------------------
class StoreComparisonRecord(BaseModel):
    store_id: UUID
    store_name: str
    store_code: str
    city: str
    total_orders: int = 0
    gross_sales: Decimal = Decimal("0.00")
    net_sales: Decimal = Decimal("0.00")
    revenue_share_percentage: Decimal = Decimal("0.00")
    stock_units_on_hand: int = 0
    stock_valuation_at_cost: Decimal = Decimal("0.00")
    active_shipments_count: int = 0


class MultiStoreReportResponse(BaseModel):
    tenant_id: UUID
    start_date: datetime
    end_date: datetime
    stores: list[StoreComparisonRecord]


# -----------------------------------------------------------------------------
# 10. Platform Overview Analytics (TechMasters Super Admin)
# -----------------------------------------------------------------------------
class TenantComparisonRecord(BaseModel):
    tenant_id: UUID
    tenant_name: str
    tenant_slug: str
    status: str
    store_count: int = 0
    total_orders: int = 0
    gross_merchandise_value: Decimal = Decimal("0.00")
    active_products_count: int = 0
    created_at: datetime


class PlatformOverviewResponse(BaseModel):
    start_date: datetime
    end_date: datetime
    total_active_tenants: int = 0
    total_physical_stores: int = 0
    platform_total_orders: int = 0
    platform_gmv: Decimal = Decimal("0.00")
    platform_average_order_value: Decimal = Decimal("0.00")
    total_registered_users: int = 0
    tenants: list[TenantComparisonRecord]


# -----------------------------------------------------------------------------
# 11. Report Export Logs
# -----------------------------------------------------------------------------
class ReportExportLogResponse(BaseModel):
    id: UUID
    tenant_id: UUID | None
    user_id: UUID | None
    report_type: str
    export_format: str
    parameters: dict
    row_count: int
    file_name: str | None
    ip_address: str | None
    created_at: datetime
