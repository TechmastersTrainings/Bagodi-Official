from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.catalog.models import Category, Product, ProductVariant
from app.modules.identity.models import User
from app.modules.orders.models import Cart
from app.modules.pricing.models import (
    Coupon,
    CouponRedemption,
    PricingAuditLog,
    Promotion,
)
from app.modules.pricing.schemas import (
    AppliedCouponDetail,
    AppliedPromotionDetail,
    CouponCreate,
    CouponUpdate,
    DiscountBreakdown,
    PriceQuoteItem,
    PriceQuoteResponse,
    PromotionCreate,
    PromotionUpdate,
)


async def _resolve_user_id(db: AsyncSession, user_id: UUID | None) -> UUID | None:
    if not user_id:
        return None
    exists = (await db.execute(select(User.id).where(User.id == user_id))).scalar_one_or_none()
    return user_id if exists else None


class PromotionService:
    @staticmethod
    async def create_promotion(
        db: AsyncSession,
        tenant_id: UUID,
        data: PromotionCreate,
        user_id: UUID | None = None,
    ) -> Promotion:
        # Validate target entity if scope is not CART
        if data.scope == "VARIANT":
            variant = (
                await db.execute(
                    select(ProductVariant).where(
                        ProductVariant.id == data.target_id, ProductVariant.tenant_id == tenant_id
                    )
                )
            ).scalar_one_or_none()
            if not variant:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "code": "TARGET_NOT_FOUND",
                        "message": "Target product variant not found in merchant catalogue.",
                    },
                )
        elif data.scope == "PRODUCT":
            product = (
                await db.execute(
                    select(Product).where(
                        Product.id == data.target_id, Product.tenant_id == tenant_id
                    )
                )
            ).scalar_one_or_none()
            if not product:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "code": "TARGET_NOT_FOUND",
                        "message": "Target product not found in merchant catalogue.",
                    },
                )
        elif data.scope == "CATEGORY":
            category = (
                await db.execute(
                    select(Category).where(
                        Category.id == data.target_id,
                        (Category.tenant_id == tenant_id) | (Category.tenant_id.is_(None)),
                    )
                )
            ).scalar_one_or_none()
            if not category:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"code": "TARGET_NOT_FOUND", "message": "Target category not found."},
                )

        promotion = Promotion(
            tenant_id=tenant_id,
            name=data.name,
            description=data.description,
            promotion_type=data.promotion_type,
            scope=data.scope,
            target_id=data.target_id,
            discount_value=data.discount_value,
            max_discount_amount=data.max_discount_amount,
            min_order_amount=data.min_order_amount,
            start_date=data.start_date,
            end_date=data.end_date,
            status=data.status,
            priority=data.priority,
            is_stackable=data.is_stackable,
        )
        db.add(promotion)
        await db.flush()

        # Audit Log
        db.add(
            PricingAuditLog(
                tenant_id=tenant_id,
                entity_type="promotion",
                entity_id=promotion.id,
                action="CREATE",
                changed_by_user_id=await _resolve_user_id(db, user_id),
                changes={"new": data.model_dump(mode="json")},
                created_at=datetime.now(UTC),
            )
        )
        await db.commit()
        await db.refresh(promotion)
        return promotion

    @staticmethod
    async def update_promotion(
        db: AsyncSession,
        tenant_id: UUID,
        promotion_id: UUID,
        data: PromotionUpdate,
        user_id: UUID | None = None,
    ) -> Promotion:
        stmt = select(Promotion).where(
            Promotion.id == promotion_id, Promotion.tenant_id == tenant_id
        )
        promotion = (await db.execute(stmt)).scalar_one_or_none()
        if not promotion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "PROMOTION_NOT_FOUND", "message": "Promotion not found."},
            )

        old_values = {
            "name": promotion.name,
            "description": promotion.description,
            "discount_value": str(promotion.discount_value),
            "max_discount_amount": str(promotion.max_discount_amount)
            if promotion.max_discount_amount
            else None,
            "min_order_amount": str(promotion.min_order_amount),
            "start_date": promotion.start_date.isoformat(),
            "end_date": promotion.end_date.isoformat() if promotion.end_date else None,
            "status": promotion.status,
            "priority": promotion.priority,
            "is_stackable": promotion.is_stackable,
        }

        update_dict = data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(promotion, key, value)

        db.add(
            PricingAuditLog(
                tenant_id=tenant_id,
                entity_type="promotion",
                entity_id=promotion.id,
                action="UPDATE",
                changed_by_user_id=await _resolve_user_id(db, user_id),
                changes={
                    "old": old_values,
                    "new": data.model_dump(mode="json", exclude_unset=True),
                },
                created_at=datetime.now(UTC),
            )
        )
        await db.commit()
        await db.refresh(promotion)
        return promotion

    @staticmethod
    async def delete_promotion(
        db: AsyncSession,
        tenant_id: UUID,
        promotion_id: UUID,
        user_id: UUID | None = None,
    ) -> None:
        stmt = select(Promotion).where(
            Promotion.id == promotion_id, Promotion.tenant_id == tenant_id
        )
        promotion = (await db.execute(stmt)).scalar_one_or_none()
        if not promotion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "PROMOTION_NOT_FOUND", "message": "Promotion not found."},
            )

        db.add(
            PricingAuditLog(
                tenant_id=tenant_id,
                entity_type="promotion",
                entity_id=promotion.id,
                action="DELETE",
                changed_by_user_id=await _resolve_user_id(db, user_id),
                changes={"status": "archived"},
                created_at=datetime.now(UTC),
            )
        )
        promotion.status = "archived"
        await db.commit()

    @staticmethod
    async def list_promotions(
        db: AsyncSession,
        tenant_id: UUID,
        status: str | None = None,
        scope: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Promotion]:
        stmt = select(Promotion).where(Promotion.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(Promotion.status == status)
        if scope:
            stmt = stmt.where(Promotion.scope == scope)
        stmt = (
            stmt.order_by(Promotion.priority.desc(), Promotion.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def get_promotion(db: AsyncSession, tenant_id: UUID, promotion_id: UUID) -> Promotion:
        stmt = select(Promotion).where(
            Promotion.id == promotion_id, Promotion.tenant_id == tenant_id
        )
        promotion = (await db.execute(stmt)).scalar_one_or_none()
        if not promotion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "PROMOTION_NOT_FOUND", "message": "Promotion not found."},
            )
        return promotion


class CouponService:
    @staticmethod
    async def create_coupon(
        db: AsyncSession,
        tenant_id: UUID,
        data: CouponCreate,
        user_id: UUID | None = None,
    ) -> Coupon:
        # Check duplicate code
        dup_stmt = select(Coupon).where(Coupon.tenant_id == tenant_id, Coupon.code == data.code)
        if (await db.execute(dup_stmt)).scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "COUPON_CODE_EXISTS",
                    "message": f"Coupon code '{data.code}' already exists.",
                },
            )

        coupon = Coupon(
            tenant_id=tenant_id,
            code=data.code,
            name=data.name,
            description=data.description,
            discount_type=data.discount_type,
            discount_value=data.discount_value,
            max_discount_amount=data.max_discount_amount,
            min_order_amount=data.min_order_amount,
            start_date=data.start_date,
            end_date=data.end_date,
            status=data.status,
            total_usage_limit=data.total_usage_limit,
            usage_limit_per_customer=data.usage_limit_per_customer,
            total_redeemed_count=0,
            is_stackable=data.is_stackable,
        )
        db.add(coupon)
        await db.flush()

        db.add(
            PricingAuditLog(
                tenant_id=tenant_id,
                entity_type="coupon",
                entity_id=coupon.id,
                action="CREATE",
                changed_by_user_id=await _resolve_user_id(db, user_id),
                changes={"new": data.model_dump(mode="json")},
                created_at=datetime.now(UTC),
            )
        )
        await db.commit()
        await db.refresh(coupon)
        return coupon

    @staticmethod
    async def update_coupon(
        db: AsyncSession,
        tenant_id: UUID,
        coupon_id: UUID,
        data: CouponUpdate,
        user_id: UUID | None = None,
    ) -> Coupon:
        stmt = select(Coupon).where(Coupon.id == coupon_id, Coupon.tenant_id == tenant_id)
        coupon = (await db.execute(stmt)).scalar_one_or_none()
        if not coupon:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "COUPON_NOT_FOUND", "message": "Coupon not found."},
            )

        old_values = {
            "name": coupon.name,
            "description": coupon.description,
            "discount_value": str(coupon.discount_value),
            "max_discount_amount": str(coupon.max_discount_amount)
            if coupon.max_discount_amount
            else None,
            "min_order_amount": str(coupon.min_order_amount),
            "start_date": coupon.start_date.isoformat(),
            "end_date": coupon.end_date.isoformat(),
            "status": coupon.status,
            "total_usage_limit": coupon.total_usage_limit,
            "usage_limit_per_customer": coupon.usage_limit_per_customer,
            "is_stackable": coupon.is_stackable,
        }

        update_dict = data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(coupon, key, value)

        db.add(
            PricingAuditLog(
                tenant_id=tenant_id,
                entity_type="coupon",
                entity_id=coupon.id,
                action="UPDATE",
                changed_by_user_id=await _resolve_user_id(db, user_id),
                changes={
                    "old": old_values,
                    "new": data.model_dump(mode="json", exclude_unset=True),
                },
                created_at=datetime.now(UTC),
            )
        )
        await db.commit()
        await db.refresh(coupon)
        return coupon

    @staticmethod
    async def delete_coupon(
        db: AsyncSession,
        tenant_id: UUID,
        coupon_id: UUID,
        user_id: UUID | None = None,
    ) -> None:
        stmt = select(Coupon).where(Coupon.id == coupon_id, Coupon.tenant_id == tenant_id)
        coupon = (await db.execute(stmt)).scalar_one_or_none()
        if not coupon:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "COUPON_NOT_FOUND", "message": "Coupon not found."},
            )

        coupon.status = "expired"
        db.add(
            PricingAuditLog(
                tenant_id=tenant_id,
                entity_type="coupon",
                entity_id=coupon.id,
                action="DELETE",
                changed_by_user_id=await _resolve_user_id(db, user_id),
                changes={"status": "expired"},
                created_at=datetime.now(UTC),
            )
        )
        await db.commit()

    @staticmethod
    async def list_coupons(
        db: AsyncSession,
        tenant_id: UUID,
        status: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Coupon]:
        stmt = select(Coupon).where(Coupon.tenant_id == tenant_id)
        if status:
            stmt = stmt.where(Coupon.status == status)
        stmt = stmt.order_by(Coupon.created_at.desc()).offset(skip).limit(limit)
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def get_coupon(db: AsyncSession, tenant_id: UUID, coupon_id: UUID) -> Coupon:
        stmt = select(Coupon).where(Coupon.id == coupon_id, Coupon.tenant_id == tenant_id)
        coupon = (await db.execute(stmt)).scalar_one_or_none()
        if not coupon:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "COUPON_NOT_FOUND", "message": "Coupon not found."},
            )
        return coupon


class PricingService:
    @staticmethod
    async def calculate_cart_pricing(
        db: AsyncSession,
        tenant_id: UUID,
        cart: Cart,
        coupon_code: str | None = None,
        customer_id: UUID | None = None,
    ) -> PriceQuoteResponse:
        """Authoritative backend engine executing precedence, stacking, and calculation rules."""
        now = datetime.now(UTC)

        # 1. Fetch all active promotions for this merchant
        promo_stmt = (
            select(Promotion)
            .where(
                Promotion.tenant_id == tenant_id,
                Promotion.status == "active",
                Promotion.start_date <= now,
                (Promotion.end_date.is_(None) | (Promotion.end_date >= now)),
            )
            .order_by(Promotion.priority.desc(), Promotion.discount_value.desc())
        )
        active_promotions = list((await db.execute(promo_stmt)).scalars().all())

        variant_promos: dict[UUID, list[Promotion]] = {}
        product_promos: dict[UUID, list[Promotion]] = {}
        category_promos: dict[UUID, list[Promotion]] = {}
        cart_promos: list[Promotion] = []

        for p in active_promotions:
            if p.scope == "VARIANT" and p.target_id:
                variant_promos.setdefault(p.target_id, []).append(p)
            elif p.scope == "PRODUCT" and p.target_id:
                product_promos.setdefault(p.target_id, []).append(p)
            elif p.scope == "CATEGORY" and p.target_id:
                category_promos.setdefault(p.target_id, []).append(p)
            elif p.scope == "CART":
                cart_promos.append(p)

        # 2. Evaluate Item-Level Promotions with Specificity Precedence
        calculated_items: list[PriceQuoteItem] = []
        applied_promotions_map: dict[UUID, AppliedPromotionDetail] = {}
        subtotal = Decimal("0.00")
        item_discounts_total = Decimal("0.00")

        for item in cart.items:
            variant = item.variant
            original_unit_price = variant.base_price
            qty = item.quantity
            item_orig_total = original_unit_price * Decimal(qty)
            subtotal += item_orig_total

            # Specificity Precedence: VARIANT (Rank 3) > PRODUCT (Rank 2) > CATEGORY (Rank 1)
            selected_promo: Promotion | None = None

            if variant.id in variant_promos:
                selected_promo = variant_promos[variant.id][0]
            elif variant.product_id in product_promos:
                selected_promo = product_promos[variant.product_id][0]
            elif variant.product.category_id in category_promos:
                selected_promo = category_promos[variant.product.category_id][0]

            unit_discount = Decimal("0.00")
            applied_promo_detail: AppliedPromotionDetail | None = None

            if selected_promo and item_orig_total >= selected_promo.min_order_amount:
                if selected_promo.promotion_type == "PERCENTAGE":
                    calc_disc = (
                        original_unit_price * selected_promo.discount_value / Decimal(100)
                    ).quantize(Decimal("0.01"))
                    if selected_promo.max_discount_amount:
                        calc_disc = min(calc_disc, selected_promo.max_discount_amount)
                    unit_discount = min(calc_disc, original_unit_price)
                elif selected_promo.promotion_type == "FIXED_AMOUNT":
                    unit_discount = min(selected_promo.discount_value, original_unit_price)

                if unit_discount > 0:
                    total_item_disc = unit_discount * Decimal(qty)
                    applied_promo_detail = AppliedPromotionDetail(
                        promotion_id=selected_promo.id,
                        title=selected_promo.name,
                        scope=selected_promo.scope,
                        discount_amount=total_item_disc,
                    )
                    applied_promotions_map[selected_promo.id] = applied_promo_detail

            unit_price = max(Decimal("0.00"), original_unit_price - unit_discount)
            line_total = unit_price * Decimal(qty)
            item_discounts_total += unit_discount * Decimal(qty)

            calculated_items.append(
                PriceQuoteItem(
                    variant_id=variant.id,
                    sku=variant.sku,
                    product_name=variant.product.name,
                    variant_name=variant.name,
                    quantity=qty,
                    original_unit_price=original_unit_price,
                    unit_price=unit_price,
                    discount_amount=unit_discount * Decimal(qty),
                    line_total=line_total,
                    applied_promotion=applied_promo_detail,
                )
            )

        net_after_items = subtotal - item_discounts_total

        # 3. Evaluate Cart-Level Promotions
        cart_discount_total = Decimal("0.00")
        selected_cart_promo: Promotion | None = None

        for cp in cart_promos:
            if net_after_items >= cp.min_order_amount:
                if cp.promotion_type == "PERCENTAGE":
                    c_disc = (net_after_items * cp.discount_value / Decimal(100)).quantize(
                        Decimal("0.01")
                    )
                    if cp.max_discount_amount:
                        c_disc = min(c_disc, cp.max_discount_amount)
                    c_disc = min(c_disc, net_after_items)
                else:
                    c_disc = min(cp.discount_value, net_after_items)

                if c_disc > cart_discount_total:
                    cart_discount_total = c_disc
                    selected_cart_promo = cp

        if selected_cart_promo and cart_discount_total > 0:
            applied_promotions_map[selected_cart_promo.id] = AppliedPromotionDetail(
                promotion_id=selected_cart_promo.id,
                title=selected_cart_promo.name,
                scope="CART",
                discount_amount=cart_discount_total,
            )

        # 4. Evaluate Coupon Code
        coupon_discount_total = Decimal("0.00")
        applied_coupon_detail: AppliedCouponDetail | None = None
        code_to_eval = (coupon_code or cart.coupon_code or "").strip().upper()

        if code_to_eval:
            coupon = (
                await db.execute(
                    select(Coupon).where(Coupon.tenant_id == tenant_id, Coupon.code == code_to_eval)
                )
            ).scalar_one_or_none()

            if not coupon:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "code": "COUPON_NOT_FOUND",
                        "message": f"Coupon '{code_to_eval}' is invalid.",
                    },
                )

            # Validity Checks
            if coupon.status != "active":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "COUPON_INACTIVE",
                        "message": f"Coupon '{code_to_eval}' is no longer active.",
                    },
                )

            if coupon.start_date > now or coupon.end_date < now:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "COUPON_EXPIRED",
                        "message": f"Coupon '{code_to_eval}' has expired or is not yet valid.",
                    },
                )

            if coupon.total_usage_limit and coupon.total_redeemed_count >= coupon.total_usage_limit:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "COUPON_LIMIT_EXCEEDED",
                        "message": f"Coupon '{code_to_eval}' usage limit reached.",
                    },
                )

            if customer_id:
                user_redemption_count = (
                    await db.execute(
                        select(func.count(CouponRedemption.id)).where(
                            CouponRedemption.coupon_id == coupon.id,
                            CouponRedemption.customer_id == customer_id,
                            CouponRedemption.status == "consumed",
                        )
                    )
                ).scalar() or 0
                if user_redemption_count >= coupon.usage_limit_per_customer:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={
                            "code": "CUSTOMER_COUPON_LIMIT_EXCEEDED",
                            "message": f"You have already used coupon '{code_to_eval}' the maximum allowed times.",
                        },
                    )

            # Min Order Amount check against cart subtotal
            if subtotal < coupon.min_order_amount:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "COUPON_MIN_ORDER_NOT_MET",
                        "message": f"Coupon requires a minimum order subtotal of ₹{coupon.min_order_amount}.",
                    },
                )

            # Stacking Rules
            base_for_coupon = net_after_items
            if not coupon.is_stackable:
                # Non-stackable coupon overrides cart-level promotion
                cart_discount_total = Decimal("0.00")
                if selected_cart_promo and selected_cart_promo.id in applied_promotions_map:
                    del applied_promotions_map[selected_cart_promo.id]
            else:
                # Stackable coupon applies on net remaining amount
                base_for_coupon = max(Decimal("0.00"), net_after_items - cart_discount_total)

            if coupon.discount_type == "PERCENTAGE":
                raw_coup_disc = (base_for_coupon * coupon.discount_value / Decimal(100)).quantize(
                    Decimal("0.01")
                )
                if coupon.max_discount_amount:
                    raw_coup_disc = min(raw_coup_disc, coupon.max_discount_amount)
                coupon_discount_total = min(raw_coup_disc, base_for_coupon)
            elif coupon.discount_type == "FIXED_AMOUNT":
                coupon_discount_total = min(coupon.discount_value, base_for_coupon)

            applied_coupon_detail = AppliedCouponDetail(
                coupon_id=coupon.id,
                code=coupon.code,
                name=coupon.name,
                discount_amount=coupon_discount_total,
            )

        total_discount = item_discounts_total + cart_discount_total + coupon_discount_total
        shipping_fee = Decimal("0.00")
        total_amount = max(Decimal("0.00"), subtotal - total_discount + shipping_fee)

        breakdown = DiscountBreakdown(
            item_discounts_total=item_discounts_total,
            cart_discount_total=cart_discount_total,
            coupon_discount_total=coupon_discount_total,
            promotions_applied=list(applied_promotions_map.values()),
            coupon_applied=applied_coupon_detail,
        )

        return PriceQuoteResponse(
            subtotal=subtotal,
            item_discount=item_discounts_total,
            cart_discount=cart_discount_total,
            coupon_discount=coupon_discount_total,
            total_discount=total_discount,
            shipping_fee=shipping_fee,
            total_amount=total_amount,
            items=calculated_items,
            discount_breakdown=breakdown,
            coupon_code=code_to_eval if applied_coupon_detail else None,
        )

    @staticmethod
    async def redeem_coupon_transaction_safe(
        db: AsyncSession,
        tenant_id: UUID,
        coupon_id: UUID,
        customer_id: UUID,
        order_id: UUID,
        discount_applied: Decimal,
    ) -> CouponRedemption:
        """Locks the coupon row with `with_for_update()` to guarantee transaction safety and concurrency limits."""
        stmt = (
            select(Coupon)
            .where(Coupon.id == coupon_id, Coupon.tenant_id == tenant_id)
            .with_for_update()
        )
        coupon = (await db.execute(stmt)).scalar_one_or_none()
        if not coupon:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "COUPON_NOT_FOUND", "message": "Coupon not found for redemption."},
            )

        if coupon.total_usage_limit and coupon.total_redeemed_count >= coupon.total_usage_limit:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "COUPON_LIMIT_EXCEEDED",
                    "message": "Coupon total redemption limit exceeded.",
                },
            )

        cust_count = (
            await db.execute(
                select(func.count(CouponRedemption.id)).where(
                    CouponRedemption.coupon_id == coupon.id,
                    CouponRedemption.customer_id == customer_id,
                    CouponRedemption.status == "consumed",
                )
            )
        ).scalar() or 0

        if cust_count >= coupon.usage_limit_per_customer:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "CUSTOMER_COUPON_LIMIT_EXCEEDED",
                    "message": "Customer coupon limit reached.",
                },
            )

        redemption = CouponRedemption(
            tenant_id=tenant_id,
            coupon_id=coupon.id,
            customer_id=customer_id,
            order_id=order_id,
            discount_applied=discount_applied,
            redeemed_at=datetime.now(UTC),
            status="consumed",
        )
        db.add(redemption)
        coupon.total_redeemed_count += 1
        return redemption

    @staticmethod
    async def revert_coupon_redemption(
        db: AsyncSession,
        tenant_id: UUID,
        order_id: UUID,
    ) -> None:
        """Compensating transaction releasing redeemed coupon usage upon order cancellation."""
        stmt = (
            select(CouponRedemption)
            .where(
                CouponRedemption.order_id == order_id,
                CouponRedemption.tenant_id == tenant_id,
                CouponRedemption.status == "consumed",
            )
            .options(selectinload(CouponRedemption.coupon))
        )
        redemption = (await db.execute(stmt)).scalar_one_or_none()
        if redemption:
            redemption.status = "reverted"
            c_stmt = select(Coupon).where(Coupon.id == redemption.coupon_id).with_for_update()
            coupon = (await db.execute(c_stmt)).scalar_one_or_none()
            if coupon and coupon.total_redeemed_count > 0:
                coupon.total_redeemed_count -= 1
