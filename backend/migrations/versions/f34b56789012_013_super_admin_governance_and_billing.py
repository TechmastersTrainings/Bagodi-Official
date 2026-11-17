"""013_super_admin_governance_and_billing

Revision ID: f34b56789012
Revises: e12a34567890
Create Date: 2026-11-10 19:10:00.000000
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "f34b56789012"
down_revision = "e12a34567890"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Enhance tenants with business & tax fields
    op.add_column("tenants", sa.Column("business_type", sa.String(length=50), nullable=True))
    op.add_column("tenants", sa.Column("pan_number", sa.String(length=20), nullable=True))
    op.add_column("tenants", sa.Column("gstin", sa.String(length=25), nullable=True))
    op.add_column("tenants", sa.Column("registered_address", sa.Text(), nullable=True))

    # 2. Tenant KYC Documents
    op.create_table(
        "tenant_kyc_documents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("document_type", sa.String(length=50), nullable=False),
        sa.Column("document_number", sa.String(length=100), nullable=False),
        sa.Column("document_url", sa.String(length=500), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="PENDING"),
        sa.Column("rejection_reason", sa.String(length=500), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["verified_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_tenant_kyc_documents_tenant_id"),
        "tenant_kyc_documents",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tenant_kyc_documents_status"),
        "tenant_kyc_documents",
        ["status"],
        unique=False,
    )

    # 3. Tenant Status / Lifecycle Logs
    op.create_table(
        "tenant_status_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("previous_status", sa.String(length=30), nullable=False),
        sa.Column("new_status", sa.String(length=30), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("actor_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_tenant_status_logs_tenant_id"),
        "tenant_status_logs",
        ["tenant_id"],
        unique=False,
    )

    # 4. Merchant Subscription Plans
    op.create_table(
        "merchant_subscription_plans",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("billing_cycle", sa.String(length=30), nullable=False, server_default="MONTHLY"),
        sa.Column("price", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0.00"),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="INR"),
        sa.Column("max_stores", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_staff_users", sa.Integer(), nullable=False, server_default="5"),
        sa.Column(
            "commission_rate_percent",
            sa.Numeric(precision=5, scale=2),
            nullable=False,
            server_default="0.00",
        ),
        sa.Column("features", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_merchant_subscription_plans_code"),
    )

    # 5. Merchant Subscriptions
    op.create_table(
        "merchant_subscriptions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("plan_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="ACTIVE"),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("auto_renew", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["plan_id"], ["merchant_subscription_plans.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_merchant_subscriptions_tenant_id"),
        "merchant_subscriptions",
        ["tenant_id"],
        unique=False,
    )

    # 6. Merchant Invoices
    op.create_table(
        "merchant_invoices",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("subscription_id", sa.UUID(), nullable=True),
        sa.Column("invoice_number", sa.String(length=100), nullable=False),
        sa.Column("billing_period_start", sa.Date(), nullable=False),
        sa.Column("billing_period_end", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0.00"),
        sa.Column("tax_amount", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0.00"),
        sa.Column("total_amount", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0.00"),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="INR"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="PENDING"),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payment_reference", sa.String(length=150), nullable=True),
        sa.Column("line_items", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["subscription_id"], ["merchant_subscriptions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invoice_number", name="uq_merchant_invoices_number"),
    )
    op.create_index(
        op.f("ix_merchant_invoices_tenant_id"),
        "merchant_invoices",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_merchant_invoices_status"),
        "merchant_invoices",
        ["status"],
        unique=False,
    )

    # 7. Global Platform Administrative Audit Logs
    op.create_table(
        "platform_audit_logs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("actor_id", sa.UUID(), nullable=True),
        sa.Column("actor_email", sa.String(length=320), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=False),
        sa.Column("target_id", sa.String(length=100), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("ip_address", sa.String(length=50), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_platform_audit_logs_action"),
        "platform_audit_logs",
        ["action"],
        unique=False,
    )
    op.create_index(
        op.f("ix_platform_audit_logs_target_type"),
        "platform_audit_logs",
        ["target_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_platform_audit_logs_created_at"),
        "platform_audit_logs",
        ["created_at"],
        unique=False,
    )


def downgrade():
    op.drop_table("platform_audit_logs")
    op.drop_table("merchant_invoices")
    op.drop_table("merchant_subscriptions")
    op.drop_table("merchant_subscription_plans")
    op.drop_table("tenant_status_logs")
    op.drop_table("tenant_kyc_documents")
    op.drop_column("tenants", "registered_address")
    op.drop_column("tenants", "gstin")
    op.drop_column("tenants", "pan_number")
    op.drop_column("tenants", "business_type")

