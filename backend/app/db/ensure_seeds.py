import logging
from decimal import Decimal
from uuid import UUID
from sqlalchemy import select, or_, text, delete
from app.db.session import AsyncSessionLocal
from app.core.passwords import hash_password, verify_password
from app.modules.platform.models import Tenant, Store
from app.modules.identity.models import User, Role, Permission, UserRole, RolePermission, UserSession
import secrets
import os
from app.modules.catalog.models import Category, Brand, Product
from app.modules.delivery.models import (
    DeliveryZone,
    DeliveryZonePincode,
    DeliveryVehicle,
    DeliveryPersonnel,
)

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
                ("DELIVERY_AGENT", "Bagodi Delivery Agent", "TENANT", tenant.id, [
                    "delivery.read", "delivery.write", "delivery.staff", "delivery.*", "orders.read"
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

            # 5. Core Platform & Store Operations Users
            admin_pwd = (
                os.environ.get("INITIAL_ADMIN_PASSWORD")
                or os.environ.get("ADMIN_PASSWORD")
                or "Fri10Feb@2023"
            )

            staff_users_config = [
                (
                    "techmastersinnovations@gmail.com",
                    "+919999900001",
                    "TechMasters Admin",
                    admin_pwd,
                    True,
                    tenant.id,
                    ["SUPER_ADMIN", "MERCHANT_OWNER", "STORE_MANAGER"],
                ),
                (
                    "admin@techmasters.in",
                    "+919999900002",
                    "Platform Administrator",
                    admin_pwd,
                    True,
                    None,
                    ["SUPER_ADMIN"],
                ),
                (
                    "merchant@bagodi.in",
                    "+919876500002",
                    "Bagodi Merchant Owner",
                    admin_pwd,
                    False,
                    tenant.id,
                    ["MERCHANT_OWNER", "STORE_MANAGER"],
                ),
                (
                    "customer@bagodi.in",
                    "+919876500003",
                    "Customer Account",
                    "Fri10Feb@2023",
                    False,
                    None,
                    ["CUSTOMER"],
                ),
            ]

            for email, phone, display, pwd, is_platform, t_id, assigned_roles in staff_users_config:
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
                    logger.info(f"✓ Provisioned operating staff user: {email} ({display})")
                else:
                    u.email = email
                    u.display_name = display
                    u.password_hash = hash_password(pwd)
                    u.is_platform_user = is_platform
                    u.status = "active"
                    logger.info(f"✓ Verified operating staff credentials: {email}")

                for r_code in assigned_roles:
                    r = role_objs.get(r_code)
                    if r:
                        ur_stmt = select(UserRole).where(
                            UserRole.user_id == u.id, UserRole.role_id == r.id
                        )
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

            # 8. Delivery Logistics Infrastructure (Vehicles, Zones, Personnel)
            # 8.1 Delivery Vehicles
            vehicles_config = [
                ("KA-38-EA-1024", "MOTORCYCLE", "Hero Splendor Plus", Decimal("25.00")),
                ("KA-38-EA-2048", "SCOOTER", "Honda Activa 6G", Decimal("20.00")),
            ]
            vehicle_objs = {}
            for reg, v_type, model, cap in vehicles_config:
                v_stmt = select(DeliveryVehicle).where(
                    DeliveryVehicle.tenant_id == tenant.id,
                    DeliveryVehicle.registration_number == reg,
                )
                vehicle = (await db.execute(v_stmt)).scalar_one_or_none()
                if not vehicle:
                    vehicle = DeliveryVehicle(
                        tenant_id=tenant.id,
                        store_id=store.id,
                        registration_number=reg,
                        vehicle_type=v_type,
                        brand_model=model,
                        max_weight_capacity_kg=cap,
                        status="AVAILABLE",
                        is_active=True,
                    )
                    db.add(vehicle)
                    await db.flush()
                vehicle_objs[reg] = vehicle

            # 8.2 Central Delivery Zone for Bidar
            z_stmt = select(DeliveryZone).where(
                DeliveryZone.tenant_id == tenant.id,
                DeliveryZone.code == "BIDAR-CENTRAL",
            )
            zone = (await db.execute(z_stmt)).scalar_one_or_none()
            if not zone:
                zone = DeliveryZone(
                    tenant_id=tenant.id,
                    store_id=store.id,
                    code="BIDAR-CENTRAL",
                    name="Bidar City Central Zone",
                    description="Immediate hyper-local fulfillment zone for Bidar city and surrounding areas",
                    base_delivery_fee=Decimal("0.00"),
                    free_delivery_threshold=Decimal("0.00"),
                    estimated_delivery_hours=2,
                    supports_internal_delivery=True,
                    supports_courier=True,
                    supports_cod=True,
                    is_active=True,
                )
                db.add(zone)
                await db.flush()

                # Add serviceable PIN codes
                for pin in ["585401", "585402", "585403", "585404"]:
                    p_stmt = select(DeliveryZonePincode).where(
                        DeliveryZonePincode.tenant_id == tenant.id,
                        DeliveryZonePincode.pincode == pin,
                    )
                    if not (await db.execute(p_stmt)).scalar_one_or_none():
                        db.add(
                            DeliveryZonePincode(
                                tenant_id=tenant.id,
                                zone_id=zone.id,
                                pincode=pin,
                                is_serviceable=True,
                            )
                        )
                await db.flush()

            # 8.3 Delivery Personnel Linking
            agents_config = [
                ("delivery1@bagodi.in", "DEL-BID-001", "Vikram Jadhav", "+919845011221", "KA-38-EA-1024"),
                ("delivery2@bagodi.in", "DEL-BID-002", "Mohammed Zeeshan", "+919845011222", "KA-38-EA-2048"),
            ]
            for email, code, name, phone, reg in agents_config:
                u_stmt = select(User).where(User.email == email)
                agent_user = (await db.execute(u_stmt)).scalar_one_or_none()
                if agent_user:
                    dp_stmt = select(DeliveryPersonnel).where(
                        DeliveryPersonnel.tenant_id == tenant.id,
                        DeliveryPersonnel.employee_code == code,
                    )
                    personnel = (await db.execute(dp_stmt)).scalar_one_or_none()
                    veh = vehicle_objs.get(reg)
                    if not personnel:
                        personnel = DeliveryPersonnel(
                            tenant_id=tenant.id,
                            store_id=store.id,
                            user_id=agent_user.id,
                            employee_code=code,
                            full_name=name,
                            phone_number=phone,
                            driving_license_number=f"KA38-{code}",
                            assigned_vehicle_id=veh.id if veh else None,
                            verification_status="VERIFIED",
                            duty_status="AVAILABLE",
                            is_active=True,
                        )
                        db.add(personnel)
                        await db.flush()
                    else:
                        personnel.verification_status = "VERIFIED"
                        personnel.is_active = True
                        if veh and not personnel.assigned_vehicle_id:
                            personnel.assigned_vehicle_id = veh.id

            await db.commit()
            logger.info("✓ Foundational data successfully verified in PostgreSQL.")
    except Exception as exc:
        logger.error(f"Failed to ensure foundational data: {exc}", exc_info=True)

