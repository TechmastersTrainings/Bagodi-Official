import logging
from uuid import UUID
from sqlalchemy import select, or_, text
from app.db.session import AsyncSessionLocal
from app.core.passwords import hash_password
from app.modules.platform.models import Tenant, Store
from app.modules.identity.models import User, Role, Permission, UserRole, RolePermission
from app.modules.catalog.models import Category, Brand, Product

logger = logging.getLogger("bagodi.platform")

TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
STORE_ID = UUID("22222222-2222-2222-2222-222222222222")

REQUIRED_CATEGORIES = [
    ("Men's Wear", "mens-wear", "Bespoke tailored shirts, trousers, kurtas, jackets and menswear", 1),
    ("Women's Wear", "womens-wear", "Designer kurtis, ethnic coordinates, gowns, dresses and festive pret", 2),
    ("Kid's Wear", "kids-wear", "Traditional ethnic kurtas, lehengas, gowns and celebration wear for kids", 3),
    ("Sarees", "sarees", "Pure Banarasi, Kanjeevaram, Tussar silk sarees with authentic zari borders", 4),
    ("Blazers", "blazers", "Royal bespoke blazers, bandhgalas, tuxedo jackets, suiting and ceremonial coats", 5),
]

REQUIRED_BRANDS = [
    ("Bagodi Atelier", "bagodi-atelier", "Flagship heritage silk and luxury bespoke atelier in Bidar"),
    ("Raymond", "raymond", "Authorised fine suiting, shirting, executive formalwear and fabrics"),
    ("Park Avenue", "park-avenue", "Contemporary executive apparel, formal blazers and trousers"),
    ("Parx", "parx", "Premium urban casualwear, printed shirts, polos and chinos"),
    ("ColorPlus", "colorplus", "Smart casual cotton garments, chinos and leisure apparel"),
    ("Manyavar", "manyavar", "Royal Indian celebratory kurtas, sherwanis and festive coordinates"),
]


async def ensure_foundational_data():
    try:
        async with AsyncSessionLocal() as db:
            logger.info("Initializing foundational platform data (Tenant, Store, Roles, Users, Categories, Brands)...")

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

            # 3. Permissions
            perm_codes = [
                "*", "platform.*", "platform.admin", "stores.*", "stores.read",
                "catalog.*", "catalog.products.create", "catalog.products.read",
                "catalog.products.update", "catalog.products.delete",
                "catalog.variants.create", "catalog.variants.update", "catalog.variants.delete",
                "catalog.categories.create", "catalog.categories.read", "catalog.categories.update",
                "catalog.brands.create", "catalog.brands.read",
                "inventory.*", "inventory:read", "inventory:write",
                "orders.*", "orders.create", "orders.read", "orders.update",
                "delivery.*", "reports:*", "reports:read", "billing:*",
                "pricing.*", "pricing.read", "pricing.write", "customer.*",
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
                for p_code in perms:
                    if p_code in perm_objs:
                        p_id = perm_objs[p_code].id
                        rp_stmt = select(RolePermission).where(RolePermission.role_id == r.id, RolePermission.permission_id == p_id)
                        existing_rp = (await db.execute(rp_stmt)).scalar_one_or_none()
                        if not existing_rp:
                            db.add(RolePermission(role_id=r.id, permission_id=p_id))
                await db.flush()
                role_objs[code] = r

            # 5. Core Platform Users (Security-Hardened: Never seed default passwords in production)
            import os
            initial_admin_pwd = os.environ.get("INITIAL_ADMIN_PASSWORD")
            if settings.app_env == "production" and not initial_admin_pwd:
                logger.info("Production mode: Skipping automated demo credential seeding.")
                users_config = []
            else:
                default_pwd = initial_admin_pwd or "Fri10Feb@2023"
                users_config = [
                    ("techmastersinnovations@gmail.com", "+919999900001", "TechMasters Admin", default_pwd, True, None, ["SUPER_ADMIN"]),
                    ("admin@techmasters.in", "+919999900002", "Platform Administrator", default_pwd, True, None, ["SUPER_ADMIN"]),
                    ("merchant@bagodi.in", "+919876500002", "Bagodi Merchant Owner", default_pwd, False, tenant.id, ["MERCHANT_OWNER", "STORE_MANAGER"]),
                    ("customer@bagodi.in", "+919876500003", "Customer Account", default_pwd, False, None, ["CUSTOMER"]),
                ]

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
                else:
                    u.display_name = display
                    u.is_platform_user = is_platform
                    u.status = "active"
                    # Security rule: Never overwrite existing user password hashes on startup

                for r_code in assigned_roles:
                    r = role_objs.get(r_code)
                    if r:
                        ur_stmt = select(UserRole).where(UserRole.user_id == u.id, UserRole.role_id == r.id)
                        ur = (await db.execute(ur_stmt)).scalar_one_or_none()
                        if not ur:
                            db.add(UserRole(user_id=u.id, role_id=r.id, tenant_id=t_id))
                            await db.flush()

            # 6. Required Categories (MEN'S WEAR, WOMEN'S WEAR, KID'S WEAR, SAREES, BLAZERS)
            for name, slug, desc, order in REQUIRED_CATEGORIES:
                stmt = select(Category).where(Category.slug == slug)
                cat = (await db.execute(stmt)).scalar_one_or_none()
                if not cat:
                    cat = Category(
                        tenant_id=None,  # Global platform category available to all merchants & admin
                        name=name,
                        slug=slug,
                        description=desc,
                        sort_order=order,
                        is_active=True,
                    )
                    db.add(cat)
                    await db.flush()
                else:
                    cat.name = name
                    cat.description = desc
                    cat.is_active = True

            # 7. Required Brands (Bagodi Atelier, Raymond, Park Avenue, Parx, ColorPlus, Manyavar)
            for name, slug, desc in REQUIRED_BRANDS:
                stmt = select(Brand).where(Brand.slug == slug)
                b = (await db.execute(stmt)).scalar_one_or_none()
                if not b:
                    b = Brand(
                        tenant_id=None,  # Global brand available to all
                        name=name,
                        slug=slug,
                        description=desc,
                        is_active=True,
                    )
                    db.add(b)
                    await db.flush()
                else:
                    b.name = name
                    b.description = desc
                    b.is_active = True

            await db.commit()
            logger.info("✓ Foundational data successfully verified in PostgreSQL.")
    except Exception as exc:
        logger.error(f"Failed to ensure foundational data: {exc}", exc_info=True)

