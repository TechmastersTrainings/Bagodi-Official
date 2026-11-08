import pytest
from sqlalchemy import text

from app.db.session import engine


@pytest.mark.asyncio
async def test_database_connection_and_version():
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar() == 1


@pytest.mark.asyncio
async def test_database_tables_exist():
    expected_tables = {
        "alembic_version",
        "tenants",
        "stores",
        "users",
        "roles",
        "permissions",
        "user_roles",
        "role_permissions",
        "otp_requests",
        "user_sessions",
        "categories",
        "brands",
        "products",
        "product_variants",
        "product_images",
        "suppliers",
        "stock_balances",
        "inventory_ledger",
        "purchase_orders",
        "purchase_order_items",
        "stock_receipts",
        "stock_receipt_items",
        "store_transfers",
        "store_transfer_items",
        "carts",
        "cart_items",
        "orders",
        "order_items",
        "order_status_history",
        "payment_transactions",
        "promotions",
        "coupons",
        "coupon_redemptions",
        "pricing_audit_logs",
        "refunds",
        "cod_settlements",
        "payment_audit_logs",
        "processed_webhook_events",
        "notification_outbox",
        "notification_messages",
        "notification_templates",
        "customer_communication_preferences",
        "notification_audit_logs",
        "delivery_zones",
        "delivery_zone_pincodes",
        "delivery_vehicles",
        "delivery_personnel",
        "shipments",
        "shipment_items",
        "delivery_tracking_events",
        "proof_of_deliveries",
        "delivery_audit_logs",
        "report_export_logs",
    }
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        )
        existing_tables = {row[0] for row in result.fetchall()}
        assert expected_tables.issubset(existing_tables)


@pytest.mark.asyncio
async def test_database_contains_zero_dummy_records():
    tables_to_check = [
        "tenants",
        "stores",
        "users",
        "roles",
        "permissions",
        "user_roles",
        "role_permissions",
        "otp_requests",
        "user_sessions",
        "categories",
        "brands",
        "products",
        "product_variants",
        "product_images",
        "suppliers",
        "stock_balances",
        "inventory_ledger",
        "purchase_orders",
        "purchase_order_items",
        "stock_receipts",
        "stock_receipt_items",
        "store_transfers",
        "store_transfer_items",
        "carts",
        "cart_items",
        "orders",
        "order_items",
        "order_status_history",
        "payment_transactions",
        "promotions",
        "coupons",
        "coupon_redemptions",
        "pricing_audit_logs",
        "refunds",
        "cod_settlements",
        "payment_audit_logs",
        "processed_webhook_events",
        "notification_outbox",
        "notification_messages",
        "notification_templates",
        "customer_communication_preferences",
        "notification_audit_logs",
        "delivery_zones",
        "delivery_zone_pincodes",
        "delivery_vehicles",
        "delivery_personnel",
        "shipments",
        "shipment_items",
        "delivery_tracking_events",
        "proof_of_deliveries",
        "delivery_audit_logs",
        "report_export_logs",
    ]
    async with engine.connect() as conn:
        for table in tables_to_check:
            result = await conn.execute(text(f"SELECT count(*) FROM {table}"))
            count = result.scalar()
            assert count == 0, f"Table {table} must be empty, but found {count} records"
