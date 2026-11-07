import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db.session import engine
from app.main import app


@pytest_asyncio.fixture(autouse=True)
async def cleanup_db_after_each_test():
    yield
    # Clean up test transactions to keep the database completely clean and free of leftover test data
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE stores, role_permissions, user_roles, roles, tenants, users, permissions CASCADE;"
            )
        )
    await engine.dispose()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
