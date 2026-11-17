"""015_real_user_auth_and_merchant_onboarding

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-11-11 17:15:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add password_hash to users table
    op.add_column(
        "users",
        sa.Column("password_hash", sa.String(length=255), nullable=True),
    )

    # 2. Add merchant onboarding details to tenants table
    op.add_column(
        "tenants",
        sa.Column("owner_name", sa.String(length=150), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("bank_account_number", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("bank_ifsc", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("bank_name", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("category_specialization", sa.String(length=150), nullable=True),
    )


def downgrade():
    op.drop_column("tenants", "category_specialization")
    op.drop_column("tenants", "bank_name")
    op.drop_column("tenants", "bank_ifsc")
    op.drop_column("tenants", "bank_account_number")
    op.drop_column("tenants", "owner_name")
    op.drop_column("users", "password_hash")

