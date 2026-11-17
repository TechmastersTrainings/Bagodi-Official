"""014_email_and_mobile_auth

Revision ID: a1b2c3d4e5f6
Revises: f34b56789012
Create Date: 2026-11-10 22:50:00.000000
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "f34b56789012"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Allow phone_e164 to be nullable in otp_requests so users can request OTP via email
    op.alter_column(
        "otp_requests",
        "phone_e164",
        existing_type=sa.String(length=20),
        nullable=True,
    )

    # 2. Add email column to otp_requests
    op.add_column(
        "otp_requests",
        sa.Column("email", sa.String(length=320), nullable=True),
    )
    op.create_index(
        op.f("ix_otp_requests_email"),
        "otp_requests",
        ["email"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_otp_requests_email"), table_name="otp_requests")
    op.drop_column("otp_requests", "email")
    op.alter_column(
        "otp_requests",
        "phone_e164",
        existing_type=sa.String(length=20),
        nullable=False,
    )
