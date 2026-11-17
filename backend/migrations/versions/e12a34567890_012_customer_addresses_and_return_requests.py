"""012_customer_addresses_and_return_requests

Revision ID: e12a34567890
Revises: cf19a0460318
Create Date: 2026-11-09 15:45:00.000000
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "e12a34567890"
down_revision = "cf19a0460318"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "customer_addresses",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("address_line1", sa.String(length=255), nullable=False),
        sa.Column("address_line2", sa.String(length=255), nullable=True),
        sa.Column("landmark", sa.String(length=150), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("state", sa.String(length=100), nullable=False),
        sa.Column("postal_code", sa.String(length=10), nullable=False),
        sa.Column("address_type", sa.String(length=20), nullable=False, server_default="home"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_customer_addresses_customer_id"),
        "customer_addresses",
        ["customer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_customer_addresses_postal_code"),
        "customer_addresses",
        ["postal_code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_customer_addresses_tenant_id"), "customer_addresses", ["tenant_id"], unique=False
    )

    op.create_table(
        "order_return_requests",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("order_id", sa.UUID(), nullable=False),
        sa.Column("order_item_id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.UUID(), nullable=False),
        sa.Column("request_type", sa.String(length=30), nullable=False, server_default="RETURN"),
        sa.Column("reason", sa.String(length=100), nullable=False),
        sa.Column("detailed_reason", sa.Text(), nullable=True),
        sa.Column("requested_variant_id", sa.UUID(), nullable=True),
        sa.Column("requested_size", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="REQUESTED"),
        sa.Column("refund_amount", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("admin_notes", sa.Text(), nullable=True),
        sa.Column("reviewed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pickup_tracking_id", sa.String(length=100), nullable=True),
        sa.Column("images", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_item_id"], ["order_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_variant_id"], ["product_variants.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_order_return_requests_customer_id"),
        "order_return_requests",
        ["customer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_order_return_requests_order_id"),
        "order_return_requests",
        ["order_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_order_return_requests_order_item_id"),
        "order_return_requests",
        ["order_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_order_return_requests_requested_variant_id"),
        "order_return_requests",
        ["requested_variant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_order_return_requests_reviewed_by_user_id"),
        "order_return_requests",
        ["reviewed_by_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_order_return_requests_status"), "order_return_requests", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_order_return_requests_tenant_id"),
        "order_return_requests",
        ["tenant_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_order_return_requests_tenant_id"), table_name="order_return_requests")
    op.drop_index(op.f("ix_order_return_requests_status"), table_name="order_return_requests")
    op.drop_index(
        op.f("ix_order_return_requests_reviewed_by_user_id"), table_name="order_return_requests"
    )
    op.drop_index(
        op.f("ix_order_return_requests_requested_variant_id"), table_name="order_return_requests"
    )
    op.drop_index(
        op.f("ix_order_return_requests_order_item_id"), table_name="order_return_requests"
    )
    op.drop_index(op.f("ix_order_return_requests_order_id"), table_name="order_return_requests")
    op.drop_index(op.f("ix_order_return_requests_customer_id"), table_name="order_return_requests")
    op.drop_table("order_return_requests")

    op.drop_index(op.f("ix_customer_addresses_tenant_id"), table_name="customer_addresses")
    op.drop_index(op.f("ix_customer_addresses_postal_code"), table_name="customer_addresses")
    op.drop_index(op.f("ix_customer_addresses_customer_id"), table_name="customer_addresses")
    op.drop_table("customer_addresses")

