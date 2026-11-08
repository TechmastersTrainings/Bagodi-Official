from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_permission
from app.core.tenant import TenantContext, get_current_tenant
from app.db.session import get_db
from app.modules.catalog.schemas import BarcodeLookupResponse
from app.modules.catalog.services import ProductService

router = APIRouter(prefix="/barcodes", tags=["Barcode Operations"])


@router.get(
    "/{barcode}",
    response_model=BarcodeLookupResponse,
    summary="Resolve a barcode scan to its exact variant and product details",
    dependencies=[Depends(require_permission("catalog.products.read"))],
)
async def lookup_barcode(
    barcode: str,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    variant, product = await ProductService.lookup_by_barcode(db, tenant.tenant_id, barcode)
    return BarcodeLookupResponse(variant=variant, product=product)
