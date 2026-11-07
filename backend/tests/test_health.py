import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check_returns_ok_and_request_id(client: AsyncClient):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "app" in data
    assert "environment" in data
    assert "X-Request-ID" in response.headers
    assert len(response.headers["X-Request-ID"]) > 0


@pytest.mark.asyncio
async def test_health_check_preserves_client_request_id(client: AsyncClient):
    custom_request_id = "test-req-trace-12345"
    response = await client.get("/api/v1/health", headers={"X-Request-ID": custom_request_id})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == custom_request_id


@pytest.mark.asyncio
async def test_readiness_probe_verifies_database_connection(client: AsyncClient):
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"
    assert "X-Request-ID" in response.headers

