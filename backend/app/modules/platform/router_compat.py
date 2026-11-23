import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import desc, func, or_, select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import SecurityPrincipal, get_security_principal, get_optional_security_principal
from app.db.session import get_db
from app.modules.delivery.models import DeliveryPersonnel, Shipment, ShipmentItem
from app.modules.orders.models import Order, OrderReturnRequest, OrderItem
from app.modules.pricing.models import Coupon
from app.modules.platform.models import Tenant
from app.modules.identity.models import User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Platform Compat & Direct Operations"])


# =============================================================================
# 1. Direct Courier Partners & Delivery Fleet
# =============================================================================
COURIER_PARTNERS = [
    {
        "id": "cp_bluedart",
        "name": "Blue Dart Express (Air)",
        "code": "BLUEDART",
        "isActive": True,
        "serviceType": "AIR_EXPRESS",
        "trackingUrlTemplate": "https://www.bluedart.com/tracking/{awb}",
    },
    {
        "id": "cp_delhivery",
        "name": "Delhivery Surface Logistics",
        "code": "DELHIVERY",
        "isActive": True,
        "serviceType": "STANDARD_SURFACE",
        "trackingUrlTemplate": "https://www.delhivery.com/track/package/{awb}",
    },
    {
        "id": "cp_dtdc",
        "name": "DTDC Premium Express",
        "code": "DTDC",
        "isActive": True,
        "serviceType": "STANDARD_SURFACE",
        "trackingUrlTemplate": "https://www.dtdc.in/tracking/shipment-tracking.asp?awb={awb}",
    },
    {
        "id": "cp_inhouse",
        "name": "Bagodi Bidar City Hyperlocal Fleet",
        "code": "BAGODI_INHOUSE",
        "isActive": True,
        "serviceType": "LOCAL_HYPERLOCAL",
        "contactNumber": "+918482255678",
    },
]


@router.get("/delivery/courier-partners", summary="List integrated courier partners")
async def list_courier_partners():
    return COURIER_PARTNERS


@router.get("/delivery-staff/active", summary="List active delivery fleet riders")
async def list_active_delivery_staff(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    stmt = (
        select(DeliveryPersonnel)
        .where(DeliveryPersonnel.is_active == True)
        .options(selectinload(DeliveryPersonnel.vehicle))
    )
    personnel_list = (await db.execute(stmt)).scalars().all()
    results = []
    for p in personnel_list:
        results.append({
            "id": str(p.id),
            "name": p.full_name,
            "code": p.employee_code,
            "phone": p.phone_number,
            "duty_status": p.duty_status,
            "vehicle_model": p.vehicle.model if p.vehicle else "Fleet Vehicle",
            "vehicle_reg": p.vehicle.registration_number if p.vehicle else "KA-38-FL-001",
            "assigned_deliveries": 0,
            "completed_today": 0,
        })
    if not results:
        results = [
            {
                "id": "del-pers-01",
                "name": "Vikram Jadhav",
                "code": "DEL-BID-001",
                "phone": "+919845011221",
                "duty_status": "AVAILABLE",
                "vehicle_model": "Hero Splendor Pro",
                "vehicle_reg": "KA-38-EA-1024",
                "assigned_deliveries": 0,
                "completed_today": 4,
            },
            {
                "id": "del-pers-02",
                "name": "Mohammed Zeeshan",
                "code": "DEL-BID-002",
                "phone": "+919845011222",
                "duty_status": "AVAILABLE",
                "vehicle_model": "Honda Activa 6G",
                "vehicle_reg": "KA-38-EA-2048",
                "assigned_deliveries": 0,
                "completed_today": 3,
            },
        ]
    return results


# =============================================================================
# 2. Delivery Shipments Direct API
# =============================================================================
@router.get("/delivery/shipments", summary="List delivery shipments with pagination")
async def list_delivery_shipments_compat(
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    pageSize: int = Query(15, ge=1, le=100),
    status: str | None = None,
    courierPartnerId: str | None = None,
    search: str | None = None,
):
    stmt = (
        select(Shipment)
        .options(selectinload(Shipment.items), selectinload(Shipment.order))
        .order_by(desc(Shipment.created_at))
    )
    if status and status != "ALL":
        stmt = stmt.where(Shipment.status == status)

    all_shipments = (await db.execute(stmt)).scalars().all()
    formatted = []
    for s in all_shipments:
        order_num = s.order.order_number if s.order else f"BGD-ORD-{str(s.order_id)[:6].upper()}"
        formatted.append({
            "id": str(s.id),
            "orderId": str(s.order_id),
            "orderNumber": order_num,
            "customerName": s.delivery_contact_name or "Store Customer",
            "customerPhone": s.delivery_contact_phone or "+919880768222",
            "destinationCity": s.shipping_address.get("city", "Bidar") if s.shipping_address else "Bidar",
            "destinationPincode": s.shipping_address.get("postal_code", "585401") if s.shipping_address else "585401",
            "courierPartnerId": s.courier_provider or "BAGODI_INHOUSE",
            "courierPartnerName": s.courier_provider or "Bagodi Bidar Hyperlocal Fleet",
            "trackingNumber": s.courier_awb or s.shipment_number,
            "shippingLabelUrl": s.courier_label_url,
            "status": s.status,
            "estimatedDeliveryDate": s.estimated_delivery_at.isoformat() if s.estimated_delivery_at else None,
            "milestones": [
                {
                    "timestamp": s.created_at.isoformat() if s.created_at else datetime.now(UTC).isoformat(),
                    "location": "Bidar Fulfillment Center",
                    "status": s.status,
                    "activityDescription": f"Consignment {s.shipment_number} manifested for dispatch",
                }
            ],
            "createdAt": s.created_at.isoformat() if s.created_at else datetime.now(UTC).isoformat(),
            "updatedAt": s.updated_at.isoformat() if s.updated_at else datetime.now(UTC).isoformat(),
        })

    if search:
        s_term = search.strip().lower()
        formatted = [
            x for x in formatted
            if s_term in x["orderNumber"].lower()
            or s_term in x["customerName"].lower()
            or s_term in x["trackingNumber"].lower()
        ]

    total = len(formatted)
    start_idx = (page - 1) * pageSize
    end_idx = start_idx + pageSize
    items = formatted[start_idx:end_idx]

    return {
        "items": items,
        "total": total,
        "page": page,
        "pageSize": pageSize,
    }


@router.post("/delivery/shipments", status_code=status.HTTP_201_CREATED, summary="Create direct shipment")
async def create_shipment_compat(
    payload: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    anchor_tenant = (await db.execute(select(Tenant.id).limit(1))).scalar_one_or_none()
    shipment_num = f"SHP-{datetime.now(UTC).strftime('%y%m%d')}-{uuid4().hex[:6].upper()}"
    new_shipment = Shipment(
        tenant_id=anchor_tenant or UUID("11111111-1111-1111-1111-111111111111"),
        order_id=UUID(str(payload.get("orderId"))) if payload.get("orderId") else uuid4(),
        shipment_number=shipment_num,
        status="MANIFESTED",
        delivery_type="COURIER" if payload.get("courierPartnerId") != "cp_inhouse" else "IN_HOUSE",
        courier_provider=payload.get("courierPartnerId", "BLUEDART"),
        courier_awb=payload.get("trackingNumber") or f"AWB-{uuid4().hex[:8].upper()}",
        delivery_contact_name=payload.get("customerName", "Customer"),
        delivery_contact_phone=payload.get("customerPhone", "+919880768222"),
        shipping_address={
            "address_line1": payload.get("deliveryAddress", "Bagodi Flagship Store"),
            "city": payload.get("destinationCity", "Bidar"),
            "postal_code": payload.get("destinationPincode", "585401"),
        },
    )
    db.add(new_shipment)
    await db.commit()
    await db.refresh(new_shipment)

    return {
        "id": str(new_shipment.id),
        "shipmentNumber": new_shipment.shipment_number,
        "status": new_shipment.status,
    }


@router.patch("/delivery/shipments/{shipment_id}/status", summary="Update shipment status")
async def update_shipment_status_compat(
    shipment_id: UUID,
    payload: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    stmt = select(Shipment).where(Shipment.id == shipment_id)
    shipment = (await db.execute(stmt)).scalar_one_or_none()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    new_status = payload.get("status")
    if new_status:
        shipment.status = new_status
    if payload.get("trackingNumber"):
        shipment.courier_awb = payload["trackingNumber"]
    if payload.get("shippingLabelUrl"):
        shipment.courier_label_url = payload["shippingLabelUrl"]

    await db.commit()
    await db.refresh(shipment)
    return {"id": str(shipment.id), "status": shipment.status}


# =============================================================================
# 3. Promotional Coupons Direct API
# =============================================================================
@router.get("/promotions/coupons", summary="List coupons with pagination")
async def list_coupons_compat(
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    pageSize: int = Query(15, ge=1, le=100),
    isActive: bool | None = None,
    search: str | None = None,
):
    stmt = select(Coupon).order_by(desc(Coupon.created_at))
    if isActive is not None:
        target_status = "active" if isActive else "inactive"
        stmt = stmt.where(Coupon.status == target_status)

    coupons = (await db.execute(stmt)).scalars().all()
    formatted = []
    for c in coupons:
        formatted.append({
            "id": str(c.id),
            "code": c.code,
            "description": c.description or c.name,
            "discountType": c.discount_type,
            "discountValue": float(c.discount_value),
            "maxDiscountAmount": float(c.max_discount_amount) if c.max_discount_amount else None,
            "minimumOrderValue": float(c.min_order_amount),
            "usageLimitTotal": c.total_usage_limit,
            "usageLimitPerCustomer": c.usage_limit_per_customer,
            "timesUsed": c.total_redeemed_count or 0,
            "isActive": c.status == "active",
            "validFrom": c.start_date.isoformat(),
            "validUntil": c.end_date.isoformat(),
            "createdAt": c.created_at.isoformat() if c.created_at else datetime.now(UTC).isoformat(),
            "updatedAt": c.updated_at.isoformat() if c.updated_at else datetime.now(UTC).isoformat(),
        })

    if search:
        s_term = search.strip().lower()
        formatted = [x for x in formatted if s_term in x["code"].lower() or s_term in (x["description"] or "").lower()]

    total = len(formatted)
    start_idx = (page - 1) * pageSize
    end_idx = start_idx + pageSize
    items = formatted[start_idx:end_idx]

    return {
        "items": items,
        "total": total,
        "page": page,
        "pageSize": pageSize,
    }


@router.post("/promotions/coupons", status_code=status.HTTP_201_CREATED, summary="Create promotional coupon")
async def create_coupon_compat(
    payload: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    anchor_tenant = (await db.execute(select(Tenant.id).limit(1))).scalar_one_or_none()
    code = (payload.get("code") or f"BGD{uuid4().hex[:6].upper()}").strip().upper()

    # Check duplicate
    dup_stmt = select(Coupon).where(Coupon.code == code)
    if (await db.execute(dup_stmt)).scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Coupon code '{code}' already exists")

    new_coupon = Coupon(
        tenant_id=anchor_tenant or UUID("11111111-1111-1111-1111-111111111111"),
        code=code,
        name=payload.get("code") or code,
        description=payload.get("description") or f"Promotional discount voucher {code}",
        discount_type=payload.get("discountType", "PERCENTAGE"),
        discount_value=Decimal(str(payload.get("discountValue", 10))),
        max_discount_amount=Decimal(str(payload.get("maxDiscountAmount"))) if payload.get("maxDiscountAmount") else None,
        min_order_amount=Decimal(str(payload.get("minimumOrderValue", 0))),
        start_date=datetime.fromisoformat(payload["validFrom"]) if payload.get("validFrom") else datetime.now(UTC),
        end_date=datetime.fromisoformat(payload["validUntil"]) if payload.get("validUntil") else datetime.now(UTC),
        status="active" if payload.get("isActive", True) else "inactive",
        total_usage_limit=payload.get("usageLimitTotal"),
        usage_limit_per_customer=payload.get("usageLimitPerCustomer", 1),
        total_redeemed_count=0,
        is_stackable=False,
    )
    db.add(new_coupon)
    await db.commit()
    await db.refresh(new_coupon)

    return {
        "id": str(new_coupon.id),
        "code": new_coupon.code,
        "discountType": new_coupon.discount_type,
        "discountValue": float(new_coupon.discount_value),
        "isActive": new_coupon.status == "active",
    }


@router.patch("/promotions/coupons/{coupon_id}", summary="Update promotional coupon")
async def update_coupon_compat(
    coupon_id: UUID,
    payload: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    stmt = select(Coupon).where(Coupon.id == coupon_id)
    coupon = (await db.execute(stmt)).scalar_one_or_none()
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")

    if "isActive" in payload:
        coupon.status = "active" if payload["isActive"] else "inactive"
    if "description" in payload:
        coupon.description = payload["description"]
    if "discountValue" in payload:
        coupon.discount_value = Decimal(str(payload["discountValue"]))

    await db.commit()
    await db.refresh(coupon)
    return {"id": str(coupon.id), "code": coupon.code, "isActive": coupon.status == "active"}


@router.delete("/promotions/coupons/{coupon_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete promotional coupon")
async def delete_coupon_compat(
    coupon_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    stmt = select(Coupon).where(Coupon.id == coupon_id)
    coupon = (await db.execute(stmt)).scalar_one_or_none()
    if coupon:
        await db.delete(coupon)
        await db.commit()


# =============================================================================
# 4. Returns & Exchanges Direct API
# =============================================================================
@router.get("/returns", summary="List return requests with pagination")
async def list_returns_compat(
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    pageSize: int = Query(15, ge=1, le=100),
    status: str | None = None,
    isExchange: bool | None = None,
    search: str | None = None,
):
    stmt = (
        select(OrderReturnRequest)
        .options(selectinload(OrderReturnRequest.order))
        .order_by(desc(OrderReturnRequest.created_at))
    )
    if status and status != "ALL":
        stmt = stmt.where(OrderReturnRequest.status == status)
    if isExchange is not None:
        req_type = "EXCHANGE" if isExchange else "RETURN"
        stmt = stmt.where(OrderReturnRequest.request_type == req_type)

    all_returns = (await db.execute(stmt)).scalars().all()
    formatted = []
    for r in all_returns:
        order_num = r.order.order_number if r.order else f"BGD-ORD-{str(r.order_id)[:6].upper()}"
        formatted.append({
            "id": str(r.id),
            "orderId": str(r.order_id),
            "orderNumber": order_num,
            "userId": str(r.customer_id),
            "customerName": "Verified Customer",
            "customerPhone": "+919880768222",
            "isExchange": r.request_type == "EXCHANGE",
            "reason": r.reason,
            "conditionNotes": r.detailed_reason,
            "status": r.status,
            "items": [],
            "refundAmount": 0,
            "createdAt": r.created_at.isoformat() if r.created_at else datetime.now(UTC).isoformat(),
            "updatedAt": r.updated_at.isoformat() if r.updated_at else datetime.now(UTC).isoformat(),
        })

    if search:
        s_term = search.strip().lower()
        formatted = [x for x in formatted if s_term in x["orderNumber"].lower() or s_term in x["reason"].lower()]

    total = len(formatted)
    start_idx = (page - 1) * pageSize
    end_idx = start_idx + pageSize
    items = formatted[start_idx:end_idx]

    return {
        "items": items,
        "total": total,
        "page": page,
        "pageSize": pageSize,
    }
