from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.modules.identity.models import User
    from app.modules.platform.models import Tenant


class ReportExportLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Immutable audit log tracking report generation, analytical exports,
    and access to sensitive business data.
    """

    __tablename__ = "report_export_logs"

    tenant_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    report_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # SALES, INVENTORY, ORDERS, PAYMENTS, PRODUCTS, CATEGORIES, DELIVERY, CUSTOMERS, STORES, PLATFORM_OVERVIEW
    export_format: Mapped[str] = mapped_column(
        String(20), nullable=False, default="CSV"
    )  # CSV, JSON
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    file_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(60), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    tenant: Mapped["Tenant | None"] = relationship("Tenant")
    user: Mapped["User | None"] = relationship("User")
