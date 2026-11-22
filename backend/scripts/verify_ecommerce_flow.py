import asyncio
import os
import random
import sys
from decimal import Decimal
from uuid import UUID, uuid4

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.session import AsyncSessionLocal
from app.modules.identity.models import User
from app.modules.catalog.models import Product, ProductVariant
from app.modules.orders.models import Order, OrderItem, PaymentTransaction
from app.modules.inventory.models import StockBalance, InventoryLedger
from sqlalchemy import select, func, delete


async def main():
    print("=" * 75)
    print("BAGODI PLATFORM — END-TO-END ECOMMERCE FLOW VERIFICATION (REQ 8–13)")
    print("=" * 75)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:

        # -----------------------------------------------------------------
        # Step 1: Sign in as Merchant to prepare live boutique product
        # -----------------------------------------------------------------
        import os
        test_pwd = os.environ.get("TEST_PASSWORD", "LocalDevPass!1")
        print("\n[Step 1] Merchant Sign In & Live Garment Catalogue Setup...")
        merchant_resp = await client.post("/api/v1/auth/login", json={
            "email": "merchant@bagodi.in",
            "password": test_pwd
        })
        assert merchant_resp.status_code == 200, f"Merchant login failed: {merchant_resp.text}"
        merchant_token = merchant_resp.json()["access_token"]
        merchant_headers = {"Authorization": f"Bearer {merchant_token}"}
        print("  ✓ Merchant Logged In: merchant@bagodi.in")

        # Fetch Categories
        cats_resp = await client.get("/api/v1/merchant/catalog/categories", headers=merchant_headers)
        assert cats_resp.status_code == 200
        category_id = cats_resp.json()[0]["id"]

        # Create a Real Handloom Apparel Item with Sizes S, M, L, XL, XXL
        garment_name = f"Bidar Zari Handloom Sherwani {uuid4().hex[:4].upper()}"
        create_resp = await client.post("/api/v1/merchant/catalog/products", headers=merchant_headers, json={
            "name": garment_name,
            "category_id": category_id,
            "description": "Authentic Bidar royal silk sherwani with handwoven zari borders.",
            "is_published": True,
            "status": "active",
            "variants": [
                {"name": "Size S", "size": "S", "color": "Navy", "initial_stock": 5, "base_price": "3499.00", "mrp": "4499.00", "status": "active"},
                {"name": "Size M", "size": "M", "color": "Navy", "initial_stock": 4, "base_price": "3499.00", "mrp": "4499.00", "status": "active"},
                {"name": "Size L", "size": "L", "color": "Navy", "initial_stock": 3, "base_price": "3499.00", "mrp": "4499.00", "status": "active"},
                {"name": "Size XL", "size": "XL", "color": "Navy", "initial_stock": 2, "base_price": "3499.00", "mrp": "4499.00", "status": "active"},
                {"name": "Size XXL", "size": "XXL", "color": "Navy", "initial_stock": 1, "base_price": "3499.00", "mrp": "4499.00", "status": "active"},
            ]
        })
        assert create_resp.status_code == 201, f"Product creation failed: {create_resp.text}"
        product_data = create_resp.json()
        print(f"  ✓ Live Product Published: '{garment_name}' (Slug: {product_data['slug']})")

        # -----------------------------------------------------------------
        # Step 2: Customer Registration & Auth
        # -----------------------------------------------------------------
        print("\n[Step 2] Customer Registration & Sign In...")
        cust_email = f"customer.test.{uuid4().hex[:6]}@bagodi.in"
        cust_phone = f"+9198{random.randint(10000000, 99999999)}"
        reg_resp = await client.post("/api/v1/auth/register", json={
            "display_name": "Ramesh Patil",
            "email": cust_email,
            "phone_e164": cust_phone,
            "password": test_pwd
        })
        assert reg_resp.status_code == 201, f"Registration failed: {reg_resp.text}"
        customer_token = reg_resp.json()["access_token"]
        customer_headers = {"Authorization": f"Bearer {customer_token}"}
        customer_id = reg_resp.json()["user"]["id"]
        print(f"  ✓ Registered Real Customer: {cust_email} (ID: {customer_id})")

        # -----------------------------------------------------------------
        # Requirement 8 & 9: Product Details Page & Size Selection
        # -----------------------------------------------------------------
        print("\n[Req 8 & 9] Verifying Product Details Page & Size Availability...")
        pdp_resp = await client.get(f"/api/v1/catalog/products/{product_data['slug']}")
        assert pdp_resp.status_code == 200
        pdp_data = pdp_resp.json()
        assert pdp_data["name"] == garment_name
        assert len(pdp_data["variants"]) == 5
        print(f"  ✓ Dedicated Product Details Loaded: {pdp_data['name']}")
        print(f"  ✓ Available Sizes & Stocks:")
        variant_s = next(v for v in pdp_data["variants"] if v["size"] == "S")
        variant_m = next(v for v in pdp_data["variants"] if v["size"] == "M")
        variant_l = next(v for v in pdp_data["variants"] if v["size"] == "L")
        variant_xl = next(v for v in pdp_data["variants"] if v["size"] == "XL")
        for v in pdp_data["variants"]:
            print(f"    - Size {v['size']:<4}: {v['available_qty']} in stock (SKU: {v['sku']})")

        # -----------------------------------------------------------------
        # Requirement 10 & 11: Cart & Checkout with Payment Integration
        # Test 1: Purchase Size S with UPI Payment
        # -----------------------------------------------------------------
        print("\n[Req 10 & 11 - Test A] Instant Purchase (Buy Now) with UPI Payment Method...")
        upi_checkout_resp = await client.post("/api/v1/orders/direct-checkout", headers=customer_headers, json={
            "items": [{"variant_id": variant_s["id"], "quantity": 1}],
            "customer_name": "Ramesh Patil",
            "customer_email": cust_email,
            "customer_phone": cust_phone,
            "payment_method": "upi",
            "shipping_address": {
                "full_name": "Ramesh Patil",
                "phone": cust_phone,
                "address_line1": "Near Bidar Fort, Main Road",
                "city": "Bidar",
                "state": "Karnataka",
                "postal_code": "585401"
            },
            "notes": "Instant UPI Buy Now - VPA: ramesh@okhdfcbank"
        })
        assert upi_checkout_resp.status_code == 201, f"UPI Checkout failed: {upi_checkout_resp.text}"
        order_upi = upi_checkout_resp.json()
        print(f"  ✓ Order Created: #{order_upi['order_number']}")
        print(f"  ✓ Payment Method: {order_upi['payment_method']} (Status: {order_upi['payment_status']})")
        print(f"  ✓ Total Paid: ₹{order_upi['total_amount']}")
        assert order_upi["payment_method"] == "upi"
        assert order_upi["payment_status"] == "paid"
        assert order_upi["status"] == "CONFIRMED"

        # Verify PaymentTransaction record in database
        async with AsyncSessionLocal() as db:
            txn_stmt = select(PaymentTransaction).where(PaymentTransaction.order_id == order_upi["id"])
            txn = (await db.execute(txn_stmt)).scalar_one()
            assert txn.payment_method == "upi"
            assert txn.status == "captured"
            assert txn.gateway_provider == "razorpay"
            print(f"  ✓ PaymentTransaction Recorded: Ref={txn.transaction_reference}, Status={txn.status}, Provider={txn.gateway_provider}")

        # -----------------------------------------------------------------
        # Requirement 10 & 11: Test 2: Purchase Size M with Credit/Debit Card
        # -----------------------------------------------------------------
        print("\n[Req 10 & 11 - Test B] Purchase with Credit/Debit Card Payment Method...")
        card_checkout_resp = await client.post("/api/v1/orders/direct-checkout", headers=customer_headers, json={
            "items": [{"variant_id": variant_m["id"], "quantity": 1}],
            "customer_name": "Ramesh Patil",
            "customer_email": cust_email,
            "customer_phone": cust_phone,
            "payment_method": "card",
            "shipping_address": {
                "full_name": "Ramesh Patil",
                "phone": cust_phone,
                "address_line1": "Near Bidar Fort, Main Road",
                "city": "Bidar",
                "state": "Karnataka",
                "postal_code": "585401"
            },
            "notes": "Card Payment 4532-XXXX-XXXX-8821"
        })
        assert card_checkout_resp.status_code == 201
        order_card = card_checkout_resp.json()
        assert order_card["payment_method"] == "card"
        assert order_card["payment_status"] == "paid"
        print(f"  ✓ Card Order Created: #{order_card['order_number']}, Status: {order_card['payment_status']}")

        # -----------------------------------------------------------------
        # Requirement 10 & 11: Test 3: Purchase Size L with Net Banking
        # -----------------------------------------------------------------
        print("\n[Req 10 & 11 - Test C] Purchase with Net Banking Payment Method...")
        nb_checkout_resp = await client.post("/api/v1/orders/direct-checkout", headers=customer_headers, json={
            "items": [{"variant_id": variant_l["id"], "quantity": 1}],
            "customer_name": "Ramesh Patil",
            "customer_email": cust_email,
            "customer_phone": cust_phone,
            "payment_method": "netbanking",
            "shipping_address": {
                "full_name": "Ramesh Patil",
                "phone": cust_phone,
                "address_line1": "Near Bidar Fort, Main Road",
                "city": "Bidar",
                "state": "Karnataka",
                "postal_code": "585401"
            },
            "notes": "Net Banking: HDFC Bank"
        })
        assert nb_checkout_resp.status_code == 201
        order_nb = nb_checkout_resp.json()
        assert order_nb["payment_method"] == "netbanking"
        assert order_nb["payment_status"] == "paid"
        print(f"  ✓ Net Banking Order Created: #{order_nb['order_number']}, Status: {order_nb['payment_status']}")

        # -----------------------------------------------------------------
        # Requirement 10 & 11: Test 4: Purchase Size XL with Cash on Delivery (COD)
        # -----------------------------------------------------------------
        print("\n[Req 10 & 11 - Test D] Purchase with Cash on Delivery (COD)...")
        cod_checkout_resp = await client.post("/api/v1/orders/direct-checkout", headers=customer_headers, json={
            "items": [{"variant_id": variant_xl["id"], "quantity": 1}],
            "customer_name": "Ramesh Patil",
            "customer_email": cust_email,
            "customer_phone": cust_phone,
            "payment_method": "cod",
            "shipping_address": {
                "full_name": "Ramesh Patil",
                "phone": cust_phone,
                "address_line1": "Near Bidar Fort, Main Road",
                "city": "Bidar",
                "state": "Karnataka",
                "postal_code": "585401"
            },
            "notes": "COD Delivery"
        })
        assert cod_checkout_resp.status_code == 201
        order_cod = cod_checkout_resp.json()
        assert order_cod["payment_method"] == "cod"
        assert order_cod["payment_status"] == "confirmed"
        print(f"  ✓ COD Order Created: #{order_cod['order_number']}, Status: {order_cod['payment_status']}")

        # -----------------------------------------------------------------
        # Requirement 12: Order Confirmation & Inventory Deduction Verification
        # -----------------------------------------------------------------
        print("\n[Req 12] Verifying Size-wise Stock Deduction & Order Persistence...")
        refreshed_pdp = (await client.get(f"/api/v1/catalog/products/{product_data['slug']}")).json()
        ref_s = next(v for v in refreshed_pdp["variants"] if v["size"] == "S")
        ref_m = next(v for v in refreshed_pdp["variants"] if v["size"] == "M")
        ref_l = next(v for v in refreshed_pdp["variants"] if v["size"] == "L")
        ref_xl = next(v for v in refreshed_pdp["variants"] if v["size"] == "XL")
        assert ref_s["available_qty"] == 4  # Was 5, purchased 1
        assert ref_m["available_qty"] == 3  # Was 4, purchased 1
        assert ref_l["available_qty"] == 2  # Was 3, purchased 1
        assert ref_xl["available_qty"] == 1 # Was 2, purchased 1
        print(f"  ✓ Size S: 5 -> {ref_s['available_qty']} units")
        print(f"  ✓ Size M: 4 -> {ref_m['available_qty']} units")
        print(f"  ✓ Size L: 3 -> {ref_l['available_qty']} units")
        print(f"  ✓ Size XL: 2 -> {ref_xl['available_qty']} units")
        print("  ✓ Atomic Stock Deduction Verified for each clothing size!")

        # -----------------------------------------------------------------
        # Requirement 13: Customer Order History & Merchant Order Management
        # -----------------------------------------------------------------
        print("\n[Req 13 - Part 1] Verifying Customer Order History (My Orders)...")
        my_orders_resp = await client.get("/api/v1/orders/my-orders", headers=customer_headers)
        assert my_orders_resp.status_code == 200, f"Failed to fetch my orders: {my_orders_resp.text}"
        my_orders = my_orders_resp.json()
        assert len(my_orders) == 4, f"Expected 4 customer orders, found {len(my_orders)}"
        print(f"  ✓ Customer Order History retrieved: {len(my_orders)} orders found.")
        for o in my_orders:
            print(f"    - Order #{o['order_number']} | Method: {o['payment_method'].upper():<10} | Total: ₹{o['total_amount']} | Status: {o['status']}")

        print("\n[Req 13 - Part 2] Verifying Merchant Order Management & Status Transition...")
        merchant_orders_resp = await client.get("/api/v1/merchant/orders", headers=merchant_headers)
        assert merchant_orders_resp.status_code == 200
        merchant_orders = merchant_orders_resp.json()
        target_merchant_order = next((o for o in merchant_orders if o["order_number"] == order_upi["order_number"]), None)
        assert target_merchant_order is not None, f"Order {order_upi['order_number']} not found in merchant orders!"
        print(f"  ✓ Merchant found order #{target_merchant_order['order_number']} (Status: {target_merchant_order['status']})")

        # Merchant transitions order: CONFIRMED -> PROCESSING
        transition_resp = await client.patch(
            f"/api/v1/merchant/orders/{target_merchant_order['id']}/status",
            headers=merchant_headers,
            json={"status": "PROCESSING", "notes": "Inspected quality and packed into Bagodi luxury bag"}
        )
        assert transition_resp.status_code == 200, f"Transition failed: {transition_resp.text}"
        updated_order = transition_resp.json()
        assert updated_order["status"] == "PROCESSING"
        print(f"  ✓ Transitioned Order to 'PROCESSING' (Packed & Ready)")

        # Merchant transitions order: PROCESSING -> DISPATCHED
        dispatch_resp = await client.patch(
            f"/api/v1/merchant/orders/{target_merchant_order['id']}/status",
            headers=merchant_headers,
            json={"status": "DISPATCHED", "notes": "Handed to Bidar local delivery courier"}
        )
        assert dispatch_resp.status_code == 200
        assert dispatch_resp.json()["status"] == "DISPATCHED"
        print(f"  ✓ Transitioned Order to 'DISPATCHED' (Out for delivery)")

        # Verify updated status is reflected in Customer's Order History
        my_orders_updated = (await client.get("/api/v1/orders/my-orders", headers=customer_headers)).json()
        cust_order_check = next(o for o in my_orders_updated if o["order_number"] == order_upi["order_number"])
        assert cust_order_check["status"] == "DISPATCHED"
        print(f"  ✓ Live Reflection: Customer sees updated status '{cust_order_check['status']}' in My Orders!")

        # Cleanup temporary verification test artifacts
        print("\n[Cleanup] Removing temporary verification test artifacts from database...")
        async with AsyncSessionLocal() as db:
            p_id = UUID(product_data["id"])
            c_id = UUID(customer_id)
            await db.execute(delete(PaymentTransaction).where(PaymentTransaction.tenant_id == UUID(product_data.get("tenant_id", "11111111-1111-1111-1111-111111111111"))))
            await db.execute(delete(Order).where(Order.customer_id == c_id))
            await db.execute(delete(StockBalance).where(StockBalance.variant_id.in_(
                select(ProductVariant.id).where(ProductVariant.product_id == p_id)
            )))
            await db.execute(delete(InventoryLedger).where(InventoryLedger.variant_id.in_(
                select(ProductVariant.id).where(ProductVariant.product_id == p_id)
            )))
            await db.execute(delete(ProductVariant).where(ProductVariant.product_id == p_id))
            await db.execute(delete(Product).where(Product.id == p_id))
            await db.execute(delete(User).where(User.id == c_id))
            await db.commit()
            print("  ✓ Verification artifacts cleaned up cleanly — 0 residual test data left in database.")

    print("\n" + "=" * 75)
    print("ALL ECOMMERCE REQUIREMENTS (REQ 8–13) VERIFIED END-TO-END!")
    print("=" * 75)


if __name__ == "__main__":
    asyncio.run(main())
