from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import SecurityPrincipal, get_security_principal
from app.db.session import get_db
from app.modules.identity.models import CustomerAddress
from app.modules.identity.schemas import (
    CustomerAddressCreate,
    CustomerAddressResponse,
    CustomerAddressUpdate,
    MessageResponse,
)
from app.modules.platform.models import Tenant

router = APIRouter(prefix="/customer/addresses", tags=["Customer Addresses"])


def get_authenticated_customer_id(
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
) -> UUID:
    if not principal.user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTHENTICATION_REQUIRED", "message": "Customer login is required."},
        )
    return principal.user_id


async def resolve_address_tenant_id(
    db: AsyncSession,
    principal: SecurityPrincipal,
    header_tenant_id: UUID | None,
    query_tenant_id: UUID | None,
) -> UUID:
    resolved = principal.tenant_id or header_tenant_id or query_tenant_id
    if resolved:
        tenant = (
            await db.execute(select(Tenant).where(Tenant.id == resolved, Tenant.status == "active"))
        ).scalar_one_or_none()
        if tenant:
            return tenant.id

    # Fallback to single active anchor tenant if none explicitly specified
    anchor = (
        await db.execute(select(Tenant).where(Tenant.status == "active").limit(1))
    ).scalar_one_or_none()
    if anchor:
        return anchor.id

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"code": "TENANT_REQUIRED", "message": "Merchant context is required for addresses."},
    )


@router.get(
    "",
    response_model=list[CustomerAddressResponse],
    summary="List saved shipping addresses for current customer",
)
async def list_addresses(
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    customer_id: Annotated[UUID, Depends(get_authenticated_customer_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_tenant_id: Annotated[UUID | None, Header(alias="X-Tenant-ID")] = None,
    tenant_id: Annotated[UUID | None, Query(description="Merchant organization ID")] = None,
):
    target_tenant_id = await resolve_address_tenant_id(db, principal, x_tenant_id, tenant_id)
    stmt = (
        select(CustomerAddress)
        .where(
            CustomerAddress.customer_id == customer_id,
            CustomerAddress.tenant_id == target_tenant_id,
        )
        .order_by(desc(CustomerAddress.is_default), desc(CustomerAddress.created_at))
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post(
    "",
    response_model=CustomerAddressResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save a new customer delivery address",
)
async def create_address(
    data: CustomerAddressCreate,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    customer_id: Annotated[UUID, Depends(get_authenticated_customer_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_tenant_id: Annotated[UUID | None, Header(alias="X-Tenant-ID")] = None,
    tenant_id: Annotated[UUID | None, Query(description="Merchant organization ID")] = None,
):
    target_tenant_id = await resolve_address_tenant_id(db, principal, x_tenant_id, tenant_id)

    # Check existing count
    existing_count_stmt = select(CustomerAddress.id).where(
        CustomerAddress.customer_id == customer_id,
        CustomerAddress.tenant_id == target_tenant_id,
    )
    existing_ids = (await db.execute(existing_count_stmt)).scalars().all()

    # If first address or marked default, set is_default = True
    make_default = data.is_default or len(existing_ids) == 0

    if make_default:
        await db.execute(
            update(CustomerAddress)
            .where(
                CustomerAddress.customer_id == customer_id,
                CustomerAddress.tenant_id == target_tenant_id,
            )
            .values(is_default=False)
        )

    new_address = CustomerAddress(
        tenant_id=target_tenant_id,
        customer_id=customer_id,
        full_name=data.full_name,
        phone=data.phone,
        address_line1=data.address_line1,
        address_line2=data.address_line2,
        landmark=data.landmark,
        city=data.city,
        state=data.state,
        postal_code=data.postal_code,
        address_type=data.address_type,
        is_default=make_default,
    )
    db.add(new_address)
    await db.commit()
    await db.refresh(new_address)
    return new_address


@router.get(
    "/{address_id}",
    response_model=CustomerAddressResponse,
    summary="Get details of a specific saved address",
)
async def get_address(
    address_id: UUID,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    customer_id: Annotated[UUID, Depends(get_authenticated_customer_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    stmt = select(CustomerAddress).where(
        CustomerAddress.id == address_id,
        CustomerAddress.customer_id == customer_id,
    )
    address = (await db.execute(stmt)).scalar_one_or_none()
    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ADDRESS_NOT_FOUND", "message": "Address not found."},
        )
    return address


@router.put(
    "/{address_id}",
    response_model=CustomerAddressResponse,
    summary="Update an existing delivery address",
)
async def update_address(
    address_id: UUID,
    data: CustomerAddressUpdate,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    customer_id: Annotated[UUID, Depends(get_authenticated_customer_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    stmt = select(CustomerAddress).where(
        CustomerAddress.id == address_id,
        CustomerAddress.customer_id == customer_id,
    )
    address = (await db.execute(stmt)).scalar_one_or_none()
    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ADDRESS_NOT_FOUND", "message": "Address not found."},
        )

    if data.is_default is True:
        await db.execute(
            update(CustomerAddress)
            .where(
                CustomerAddress.customer_id == customer_id,
                CustomerAddress.tenant_id == address.tenant_id,
                CustomerAddress.id != address_id,
            )
            .values(is_default=False)
        )
        address.is_default = True

    if data.full_name is not None:
        address.full_name = data.full_name
    if data.phone is not None:
        address.phone = data.phone
    if data.address_line1 is not None:
        address.address_line1 = data.address_line1
    if data.address_line2 is not None:
        address.address_line2 = data.address_line2
    if data.landmark is not None:
        address.landmark = data.landmark
    if data.city is not None:
        address.city = data.city
    if data.state is not None:
        address.state = data.state
    if data.postal_code is not None:
        address.postal_code = data.postal_code
    if data.address_type is not None:
        address.address_type = data.address_type

    await db.commit()
    await db.refresh(address)
    return address


@router.delete(
    "/{address_id}",
    response_model=MessageResponse,
    summary="Delete a saved delivery address",
)
async def delete_address(
    address_id: UUID,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    customer_id: Annotated[UUID, Depends(get_authenticated_customer_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    stmt = select(CustomerAddress).where(
        CustomerAddress.id == address_id,
        CustomerAddress.customer_id == customer_id,
    )
    address = (await db.execute(stmt)).scalar_one_or_none()
    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ADDRESS_NOT_FOUND", "message": "Address not found."},
        )

    was_default = address.is_default
    tenant_id = address.tenant_id
    await db.delete(address)
    await db.flush()

    # If was default, elect the most recent remaining address as default
    if was_default:
        next_addr_stmt = (
            select(CustomerAddress)
            .where(
                CustomerAddress.customer_id == customer_id,
                CustomerAddress.tenant_id == tenant_id,
            )
            .order_by(desc(CustomerAddress.created_at))
            .limit(1)
        )
        next_addr = (await db.execute(next_addr_stmt)).scalar_one_or_none()
        if next_addr:
            next_addr.is_default = True

    await db.commit()
    return MessageResponse(message="Address deleted successfully.")


@router.post(
    "/{address_id}/default",
    response_model=CustomerAddressResponse,
    summary="Set an address as the default delivery address",
)
async def set_default_address(
    address_id: UUID,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    customer_id: Annotated[UUID, Depends(get_authenticated_customer_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    stmt = select(CustomerAddress).where(
        CustomerAddress.id == address_id,
        CustomerAddress.customer_id == customer_id,
    )
    address = (await db.execute(stmt)).scalar_one_or_none()
    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ADDRESS_NOT_FOUND", "message": "Address not found."},
        )

    await db.execute(
        update(CustomerAddress)
        .where(
            CustomerAddress.customer_id == customer_id,
            CustomerAddress.tenant_id == address.tenant_id,
        )
        .values(is_default=False)
    )
    address.is_default = True
    await db.commit()
    await db.refresh(address)
    return address

