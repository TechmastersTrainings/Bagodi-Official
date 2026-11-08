from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import SecurityPrincipal, get_security_principal, require_platform_admin
from app.db.session import get_db
from app.modules.reports.schemas import (
    PlatformOverviewResponse,
    ReportDateRangeFilter,
    TenantComparisonRecord,
)
from app.modules.reports.services import ReportingService

router = APIRouter(prefix="/platform/reports", tags=["Platform Super Admin Analytics"])


@router.get(
    "/overview",
    response_model=PlatformOverviewResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_platform_admin)],
)
async def get_platform_overview(
    db: Annotated[AsyncSession, Depends(get_db)],
    time_window: Annotated[str, Query(description="Preset window")] = "last_30_days",
    start_date: Annotated[date | None, Query(description="Optional custom start date")] = None,
    end_date: Annotated[date | None, Query(description="Optional custom end date")] = None,
):
    filter_params = ReportDateRangeFilter(
        time_window=time_window,
        start_date=start_date,
        end_date=end_date,
    )
    return await ReportingService.get_platform_overview(db, filter_params=filter_params)


@router.get(
    "/tenants-comparison",
    response_model=list[TenantComparisonRecord],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_platform_admin)],
)
async def get_tenants_comparison(
    request: Request,
    principal: Annotated[SecurityPrincipal, Depends(get_security_principal)],
    db: Annotated[AsyncSession, Depends(get_db)],
    time_window: Annotated[str, Query(description="Preset window")] = "last_30_days",
    start_date: Annotated[date | None, Query(description="Optional custom start date")] = None,
    end_date: Annotated[date | None, Query(description="Optional custom end date")] = None,
    format: Annotated[Literal["json", "csv"], Query(description="Output format")] = "json",
):
    filter_params = ReportDateRangeFilter(
        time_window=time_window,
        start_date=start_date,
        end_date=end_date,
        format=format,
    )
    overview = await ReportingService.get_platform_overview(db, filter_params=filter_params)

    if format == "csv":
        fieldnames = [
            "tenant_id",
            "tenant_name",
            "tenant_slug",
            "status",
            "store_count",
            "total_orders",
            "gross_merchandise_value",
            "active_products_count",
            "created_at",
        ]
        csv_data = [r.model_dump() for r in overview.tenants]
        csv_bytes = ReportingService.format_csv(csv_data, fieldnames)
        fname = f"platform_tenants_comparison_{overview.start_date.strftime('%Y%m%d')}_{overview.end_date.strftime('%Y%m%d')}.csv"

        await ReportingService.log_export(
            db,
            tenant_id=None,
            user_id=principal.user_id,
            report_type="PLATFORM_OVERVIEW",
            export_format="CSV",
            parameters=filter_params.model_dump(mode="json"),
            row_count=len(csv_data),
            file_name=fname,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        return Response(
            content=csv_bytes,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )

    return overview.tenants
