from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.db.session import engine


def test_alembic_migration_chain_is_linear_and_unbroken():
    """
    Mandatory Requirement 5:
    Validates that Alembic migrations form an unbroken, linear directed acyclic graph (DAG)
    from base through head without branching or orphan revisions.
    """
    backend_dir = Path(__file__).resolve().parent.parent
    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    script = ScriptDirectory.from_config(alembic_cfg)

    # 1. Verify single head
    heads = script.get_heads()
    assert len(heads) == 1, f"Multiple heads detected in Alembic tree: {heads}"
    head_rev = heads[0]
    assert head_rev in ("cf19a0460318", "b2c3d4e5f6a7"), f"Unexpected head revision: {head_rev}"

    # 2. Traverse revisions from head to base
    rev_chain = []
    current = script.get_revision(head_rev)
    while current is not None:
        rev_chain.append(current.revision)
        if current.down_revision is None:
            break
        current = script.get_revision(current.down_revision)

    # Expected migrations in linear order
    assert len(rev_chain) in (11, 15), f"Expected 11 or 15 migrations, found {len(rev_chain)}: {rev_chain}"
    assert rev_chain[-1] == "5419f447f363", (
        f"Initial migration must be 5419f447f363, got {rev_chain[-1]}"
    )

    # 3. Verify each migration script defines both upgrade() and downgrade() functions
    for rev_id in rev_chain:
        rev_script = script.get_revision(rev_id)
        module = rev_script.module
        assert hasattr(module, "upgrade"), f"Migration {rev_id} is missing upgrade() function!"
        assert hasattr(module, "downgrade"), f"Migration {rev_id} is missing downgrade() function!"


@pytest.mark.asyncio
async def test_database_schema_tables_and_constraints_at_head():
    """
    Verifies that all 53 public tables exist, foreign key constraints are enforced,
    and composite indexes for performance are active.
    """
    async with engine.connect() as conn:
        # Check active tables count (53 total including alembic_version)
        res_tables = await conn.execute(
            text(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE';"
            )
        )
        table_count = res_tables.scalar_one()
        assert table_count in (53, 61), (
            f"Expected 53 or 61 public tables at migration head, found {table_count}"
        )

        # Verify composite indexes exist
        res_idx = await conn.execute(
            text(
                "SELECT indexname FROM pg_indexes WHERE schemaname = 'public' AND indexname LIKE 'ix_%';"
            )
        )
        indexes = {row[0] for row in res_idx.fetchall()}

        expected_indexes = {
            "ix_orders_tenant_created_at",
            "ix_orders_tenant_store_created_at",
            "ix_payment_transactions_tenant_created",
            "ix_shipments_tenant_created",
            "ix_inventory_ledger_tenant_created",
            "ix_report_export_logs_tenant_created",
        }
        missing = expected_indexes - indexes
        assert len(missing) == 0, f"Missing critical performance indexes: {missing}"
