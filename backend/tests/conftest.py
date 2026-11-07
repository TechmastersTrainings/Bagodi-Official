import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db.session import engine
from app.main import app


@pytest_asyncio.fixture(autouse=True)
async def cleanup_engine():
    yield
    await engine.dispose()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
