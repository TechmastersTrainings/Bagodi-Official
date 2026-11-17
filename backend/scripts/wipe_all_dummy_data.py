import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from app.db.session import AsyncSessionLocal

async def wipe_dummy_data():
    async with AsyncSessionLocal() as session:
        print("--- WIPING ALL DUMMY DATA FROM BAGODI PLATFORM ---")
        
        # 1. Orders, Items, Cart, Shipments, Returns, Payments
        try:
            await session.execute(text("DELETE FROM cart_items;"))
            await session.execute(text("DELETE FROM carts;"))
        except Exception as e:
            print("cart:", e)

        try:
            await session.execute(text("DELETE FROM delivery_tracking_events;"))
            await session.execute(text("DELETE FROM proof_of_deliveries;"))
            await session.execute(text("DELETE FROM delivery_audit_logs;"))
            await session.execute(text("DELETE FROM shipment_items;"))
            await session.execute(text("DELETE FROM shipments;"))
        except Exception as e:
            print("delivery:", e)

        try:
            await session.execute(text("DELETE FROM order_return_requests;"))
            await session.execute(text("DELETE FROM payment_transactions;"))
            await session.execute(text("DELETE FROM order_status_history;"))
            await session.execute(text("DELETE FROM order_items;"))
            await session.execute(text("DELETE FROM orders;"))
        except Exception as e:
            print("orders:", e)

        try:
            await session.execute(text("DELETE FROM refunds;"))
            await session.execute(text("DELETE FROM cod_settlements;"))
            await session.execute(text("DELETE FROM payment_audit_logs;"))
            await session.execute(text("DELETE FROM processed_webhook_events;"))
        except Exception as e:
            print("payments:", e)
        
        # 2. Inventory and Products
        try:
            await session.execute(text("DELETE FROM store_transfer_items;"))
            await session.execute(text("DELETE FROM store_transfers;"))
            await session.execute(text("DELETE FROM stock_receipt_items;"))
            await session.execute(text("DELETE FROM stock_receipts;"))
            await session.execute(text("DELETE FROM purchase_order_items;"))
            await session.execute(text("DELETE FROM purchase_orders;"))
            await session.execute(text("DELETE FROM inventory_ledger;"))
            await session.execute(text("DELETE FROM stock_balances;"))
            await session.execute(text("DELETE FROM product_images;"))
            await session.execute(text("DELETE FROM product_variants;"))
            await session.execute(text("DELETE FROM products;"))
        except Exception as e:
            print("catalog/inventory:", e)
        
        # 3. Coupons / Pricing
        try:
            await session.execute(text("DELETE FROM coupon_redemptions;"))
            await session.execute(text("DELETE FROM coupons;"))
            await session.execute(text("DELETE FROM promotions;"))
            await session.execute(text("DELETE FROM pricing_audit_logs;"))
        except Exception as e:
            print("pricing:", e)
        
        # 4. Reports / Notifications
        try:
            await session.execute(text("DELETE FROM report_export_logs;"))
            await session.execute(text("DELETE FROM notification_messages;"))
            await session.execute(text("DELETE FROM notification_outbox;"))
            await session.execute(text("DELETE FROM notification_audit_logs;"))
        except Exception as e:
            print("reports/notif:", e)
        
        # 5. Customer Addresses / Sessions / OTPs
        try:
            await session.execute(text("DELETE FROM customer_addresses;"))
            await session.execute(text("DELETE FROM otp_requests;"))
            await session.execute(text("DELETE FROM user_sessions;"))
        except Exception as e:
            print("sessions/addresses:", e)
        
        # 6. Delete all dummy users (Keep only techmastersinnovations@gmail.com, merchant@bagodi.in)
        try:
            await session.execute(text("""
                DELETE FROM user_roles WHERE user_id IN (
                    SELECT id FROM users WHERE email NOT IN ('techmastersinnovations@gmail.com', 'merchant@bagodi.in')
                );
            """))
            await session.execute(text("""
                DELETE FROM users WHERE email NOT IN ('techmastersinnovations@gmail.com', 'merchant@bagodi.in');
            """))
        except Exception as e:
            print("users:", e)
        
        # 7. Categories: Keep only the 5 official categories
        try:
            valid_slugs = "('mens-wear', 'womens-wear', 'kids-wear', 'sarees', 'blazers')"
            await session.execute(text(f"DELETE FROM categories WHERE slug NOT IN {valid_slugs};"))
        except Exception as e:
            print("categories:", e)
        
        # 8. Brands: Keep official brands
        try:
            valid_brand_slugs = "('bagodi-atelier', 'colorplus', 'manyavar', 'park-avenue', 'parx', 'raymond')"
            await session.execute(text(f"DELETE FROM brands WHERE slug NOT IN {valid_brand_slugs};"))
        except Exception as e:
            print("brands:", e)
        
        await session.commit()
        print("--- COMMIT COMPLETE: ALL DUMMY DATA WIPED ---")

        # Verify Counts
        tables = [
            "products", "product_variants", "product_images", 
            "orders", "order_items", "payment_transactions",
            "stock_balances", "inventory_ledger",
            "carts", "cart_items", "users", "categories", "brands"
        ]
        print("\nFINAL DATABASE COUNTS:")
        for t in tables:
            try:
                res = await session.execute(text(f"SELECT COUNT(*) FROM {t}"))
                cnt = res.scalar()
                print(f"  {t}: {cnt}")
            except Exception as e:
                print(f"  {t}: (error: {e})")

if __name__ == "__main__":
    asyncio.run(wipe_dummy_data())

