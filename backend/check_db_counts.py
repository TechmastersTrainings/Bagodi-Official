import asyncio
from sqlalchemy import text
from app.core.database import async_session_maker

async def check():
    async with async_session_maker() as session:
        tables = [
            "products", "product_variants", "product_images", 
            "orders", "order_items", "returns", "return_items",
            "payments", "transactions", "inventory_levels", "inventory_transactions",
            "cart_items", "carts", "customers", "users", "categories", "brands", "tenants", "stores"
        ]
        print("DATABASE COUNTS:")
        for t in tables:
            try:
                res = await session.execute(text(f"SELECT COUNT(*) FROM {t}"))
                cnt = res.scalar()
                print(f"  {t}: {cnt}")
            except Exception as e:
                print(f"  {t}: (error: {e})")

if __name__ == "__main__":
    asyncio.run(check())
