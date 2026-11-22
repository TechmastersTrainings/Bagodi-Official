"""
Seed script to set up foundational entities:
- Anchor Tenant: Bagodi Clothing (Bidar)
- Flagship Store: Bagodi Bidar Flagship Store
- Platform Roles & Permissions
- Foundational Fashion Categories (Silks, Kurtas, Menswear, etc.)
- 0 products seeded (Merchant performs initial live product CRUD)
"""

import asyncio
from uuid import UUID

from sqlalchemy import select
from app.db.session import engine, AsyncSessionLocal
from app.core.passwords import hash_password
from app.modules.platform.models import Tenant, Store
from app.modules.identity.models import User, Role, Permission, UserRole, RolePermission
from app.modules.catalog.models import Category


TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
STORE_ID = UUID("22222222-2222-2222-2222-222222222222")


async def seed():
    async with AsyncSessionLocal() as db:
        print("🌱 Starting Bagodi Platform Foundational Seeding...")

        # 1. Anchor Tenant: Bagodi Clothing
        stmt = select(Tenant).where(Tenant.id == TENANT_ID)
        tenant = (await db.execute(stmt)).scalar_one_or_none()
        if not tenant:
            tenant = Tenant(
                id=TENANT_ID,
                name="Bagodi Clothing",
                slug="bagodi",
                status="active",
                legal_name="Bagodi Retail Private Limited",
                contact_email="merchant@bagodi.in",
                contact_phone="+919876500002",
                business_type="Private Limited",
                gstin="29AABCB1234F1Z1",
                pan_number="AABCB1234F",
                registered_address="Bagodi Flagship Store, Main Market Road, Bidar, Karnataka - 585401",
            )
            db.add(tenant)
            await db.flush()
            print("  ✓ Created Tenant: Bagodi Clothing")
        else:
            print("  - Tenant already exists")

        # 2. Flagship Store
        stmt = select(Store).where(Store.id == STORE_ID)
        store = (await db.execute(stmt)).scalar_one_or_none()
        if not store:
            store = Store(
                id=STORE_ID,
                tenant_id=tenant.id,
                name="Bagodi Bidar Flagship Store",
                code="BIDAR-01",
                status="active",
                address_line="Main Market Road, Near Gandhi Chowk",
                city="Bidar",
                state="Karnataka",
                postal_code="585401",
                phone="+919876500002",
            )
            db.add(store)
            await db.flush()
            print("  ✓ Created Store: Bagodi Bidar Flagship Store")
        else:
            print("  - Store already exists")

        # 3. Permissions
        perm_codes = [
            "*",
            "platform.*",
            "platform.admin",
            "stores.*",
            "stores.read",
            "catalog.*",
            "catalog.products.create",
            "catalog.products.read",
            "catalog.products.update",
            "catalog.products.delete",
            "catalog.variants.create",
            "catalog.variants.update",
            "catalog.variants.delete",
            "catalog.categories.create",
            "catalog.categories.read",
            "catalog.categories.update",
            "catalog.brands.create",
            "catalog.brands.read",
            "inventory.*",
            "inventory:read",
            "inventory:write",
            "orders.*",
            "orders.create",
            "orders.read",
            "orders.update",
            "delivery.*",
            "reports:*",
            "reports:read",
            "billing:*",
            "pricing.*",
            "pricing.read",
            "pricing.write",
            "customer.*",
        ]
        perm_objs = {}
        for code in perm_codes:
            stmt = select(Permission).where(Permission.code == code)
            p = (await db.execute(stmt)).scalar_one_or_none()
            if not p:
                p = Permission(code=code, description=f"Permission for {code}")
                db.add(p)
                await db.flush()
            perm_objs[code] = p
        print(f"  ✓ Verified {len(perm_objs)} system permissions")

        # 4. Roles
        roles_config = [
            ("SUPER_ADMIN", "TechMasters Super Administrator", "PLATFORM", None, ["*", "platform.*"]),
            ("MERCHANT_OWNER", "Bagodi Merchant Owner", "TENANT", tenant.id, [
                "catalog.*", "inventory.*", "orders.*", "delivery.*", "stores.*", "reports:*", "billing:*", "pricing.*", "pricing.write", "pricing.read"
            ]),
            ("STORE_MANAGER", "Bagodi Store Manager", "STORE", tenant.id, [
                "catalog.*", "inventory.*", "orders.*", "delivery.*", "stores.read", "reports:read", "pricing.read", "pricing.write"
            ]),
            ("CUSTOMER", "Retail Customer", "GLOBAL", None, ["customer.*", "orders.create", "orders.read"]),
        ]
        role_objs = {}
        for code, name, scope, t_id, perms in roles_config:
            stmt = select(Role).where(Role.code == code)
            if t_id:
                stmt = stmt.where(Role.tenant_id == t_id)
            r = (await db.execute(stmt)).scalar_one_or_none()
            if not r:
                r = Role(code=code, name=name, scope=scope, tenant_id=t_id)
                db.add(r)
                await db.flush()
                print(f"  ✓ Created Role: {code}")

            # Ensure all specified permissions are attached to role
            for p_code in perms:
                if p_code in perm_objs:
                    p_id = perm_objs[p_code].id
                    rp_stmt = select(RolePermission).where(RolePermission.role_id == r.id, RolePermission.permission_id == p_id)
                    existing_rp = (await db.execute(rp_stmt)).scalar_one_or_none()
                    if not existing_rp:
                        db.add(RolePermission(role_id=r.id, permission_id=p_id))
            await db.flush()
            role_objs[code] = r

        # 5. Dedicated Platform Users (Read strictly from Environment Variables)
        import os
        import secrets
        initial_admin_pwd = os.environ.get("INITIAL_ADMIN_PASSWORD")
        initial_admin_email = os.environ.get("INITIAL_ADMIN_EMAIL")
        users_config = []
        if initial_admin_pwd and initial_admin_email:
            users_config.append((
                initial_admin_email,
                os.environ.get("INITIAL_ADMIN_PHONE", "+910000000001"),
                "Platform Administrator",
                initial_admin_pwd,
                True,
                None,
                ["SUPER_ADMIN"]
            ))

        for email, phone, display, pwd, is_platform, t_id, assigned_roles in users_config:
            stmt = select(User).where((User.email == email) | (User.phone_e164 == phone))
            u = (await db.execute(stmt)).scalar_one_or_none()
            if not u:
                u = User(
                    email=email,
                    phone_e164=phone,
                    display_name=display,
                    password_hash=hash_password(pwd),
                    is_platform_user=is_platform,
                    status="active",
                )
                db.add(u)
                await db.flush()
                print(f"  ✓ Created User: {email} ({display})")
            else:
                u.email = email
                u.phone_e164 = phone
                u.display_name = display
                u.password_hash = hash_password(pwd)
                u.is_platform_user = is_platform
                u.status = "active"
                print(f"  - User password and status updated: {email}")

            # Assign roles
            for r_code in assigned_roles:
                r = role_objs.get(r_code)
                if r:
                    ur_stmt = select(UserRole).where(UserRole.user_id == u.id, UserRole.role_id == r.id)
                    ur = (await db.execute(ur_stmt)).scalar_one_or_none()
                    if not ur:
                        db.add(UserRole(user_id=u.id, role_id=r.id, tenant_id=t_id))
                        await db.flush()

        # 6. Foundational Fashion Categories (silks, kurtas, etc.)
        categories_data = [
            ("Handloom Silks & Sarees", "silks-sarees", "Pure Banarasi, Kanjeevaram & Tussar silk sarees with antique zari borders", 1),
            ("Designer Kurtas & Sets", "designer-kurtas", "Handcrafted Anarkali sets, straight kurtis, dupattas & festive wear", 2),
            ("Men's Tailoring & Shirts", "mens-tailoring", "Bespoke Egyptian Giza cotton shirts, linen trousers & formal tailoring", 3),
            ("Festive & Wedding Edit", "festive-wedding", "Royal sherwanis, bandhgalas, bridal silks & ceremonial attire", 4),
            ("Indo-Western & Pret", "indo-western", "Contemporary fusion dresses, coord sets, wrap tops & modern silhouettes", 5),
            ("Pure Linen Classics", "linen-classics", "Breathable European certified pure linen Nehru jackets, kurtas & trousers", 6),
        ]

        for name, slug, desc, order in categories_data:
            stmt = select(Category).where(Category.slug == slug)
            cat = (await db.execute(stmt)).scalar_one_or_none()
            if not cat:
                cat = Category(
                    tenant_id=tenant.id,
                    name=name,
                    slug=slug,
                    description=desc,
                    sort_order=order,
                    is_active=True,
                )
                db.add(cat)
                await db.flush()
                print(f"  ✓ Created Category: {name}")

        await db.commit()
        print("\n🎉 Foundational Seeding Complete!")
        print("  • Foundational fashion categories ready in DB")
        print("  • 0 products in DB (Merchant is ready to add first live product)")


if __name__ == "__main__":
    asyncio.run(seed())
