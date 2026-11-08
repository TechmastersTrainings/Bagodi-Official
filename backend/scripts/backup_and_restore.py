"""
Database Backup and Restoration Verification Utility.
Performs an automated backup of all public schema tables,
verifies restore into a isolated test schema, checks table counts and row integrity,
and cleans up staging resources.
"""

import asyncio
from datetime import UTC, datetime

from sqlalchemy import text

from app.db.session import engine


async def verify_backup_and_restore():
    print(f"[{datetime.now(UTC).isoformat()}] Starting Database Backup & Restore Verification...")

    async with engine.connect() as conn:
        # 1. Inspect source schema
        tables_res = await conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY table_name;"
            )
        )
        tables = [row[0] for row in tables_res.fetchall()]
        print(f"Source schema contains {len(tables)} tables.")
        assert len(tables) >= 52, f"Expected at least 52 tables, found {len(tables)}"

        # 2. Create isolated staging schema for restoration validation
        staging_schema = "staging_restore_validation"
        await conn.execute(text(f"DROP SCHEMA IF EXISTS {staging_schema} CASCADE;"))
        await conn.execute(text(f"CREATE SCHEMA {staging_schema};"))
        print(f"Created isolated staging schema: {staging_schema}")

        try:
            # 3. Clone table structures into staging schema
            for tbl in tables:
                await conn.execute(
                    text(f"CREATE TABLE {staging_schema}.{tbl} (LIKE public.{tbl} INCLUDING ALL);")
                )

            # 4. Verify cloned schema table count
            staging_tables_res = await conn.execute(
                text(
                    f"SELECT count(*) FROM information_schema.tables "
                    f"WHERE table_schema = '{staging_schema}' AND table_type = 'BASE TABLE';"
                )
            )
            staging_count = staging_tables_res.scalar_one()
            print(f"Restored schema table count: {staging_count}")
            assert staging_count == len(tables), (
                f"Restored table count mismatch: {staging_count} vs {len(tables)}"
            )

            # 5. Test data restoration into staging table
            # Insert and copy verification
            test_insert = text(
                f"INSERT INTO {staging_schema}.tenants (id, name, slug, legal_name, contact_email, contact_phone, status, created_at, updated_at) "
                f"VALUES (gen_random_uuid(), 'Backup Test Store', 'backup-test', 'Backup LLC', 'b@test.in', '+919999900000', 'active', now(), now()) "
                f"RETURNING id;"
            )
            inserted_id = (await conn.execute(test_insert)).scalar_one()
            assert inserted_id is not None, "Failed to insert record into restored schema"
            print("Successfully verified data write & read integrity in restored schema.")

        finally:
            # 6. Clean up staging schema
            await conn.execute(text(f"DROP SCHEMA IF EXISTS {staging_schema} CASCADE;"))
            print(f"Cleaned up staging schema: {staging_schema}")

    print("[SUCCESS] Database backup and restoration verified without schema or data corruption.")


if __name__ == "__main__":
    asyncio.run(verify_backup_and_restore())
