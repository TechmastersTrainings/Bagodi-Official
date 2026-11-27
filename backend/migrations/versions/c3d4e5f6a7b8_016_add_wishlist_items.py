"""016_add_wishlist_items

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-11-27 11:00:00.000000
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "wishlist_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "customer_id", "product_id", name="uq_wishlist_items_tenant_customer_product"
        ),
    )
    op.create_index("ix_wishlist_items_tenant_id", "wishlist_items", ["tenant_id"])
    op.create_index("ix_wishlist_items_customer_id", "wishlist_items", ["customer_id"])
    op.create_index("ix_wishlist_items_product_id", "wishlist_items", ["product_id"])


def downgrade():
    op.drop_index("ix_wishlist_items_product_id", table_name="wishlist_items")
    op.drop_index("ix_wishlist_items_customer_id", table_name="wishlist_items")
    op.drop_index("ix_wishlist_items_tenant_id", table_name="wishlist_items")
    op.drop_table("wishlist_items")

