from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.db.session import engine
from app.modules.identity.otp_provider import InMemoryTestOTPProvider


@pytest.mark.asyncio
async def test_otp_send_and_verify_success(client: AsyncClient):
    phone = "+919876543210"

    # 1. Request OTP
    send_resp = await client.post("/api/v1/auth/otp/send", json={"phone_e164": phone})
    assert send_resp.status_code == 200
    send_data = send_resp.json()
    assert send_data["status"] == "sent"
    assert "cooldown_seconds" in send_data
    assert "expires_in_seconds" in send_data
    # Public API must NEVER expose the raw OTP code
    assert "otp" not in send_data
    assert "code" not in send_data

    # 2. Retrieve actual dispatched code from test provider
    dispatched_otp = InMemoryTestOTPProvider.get_last_otp(phone)
    assert dispatched_otp is not None
    assert len(dispatched_otp) == 6

    # 3. Verify OTP
    verify_resp = await client.post(
        "/api/v1/auth/otp/verify",
        json={"phone_e164": phone, "otp": dispatched_otp},
    )
    assert verify_resp.status_code == 200
    auth_data = verify_resp.json()
    assert "access_token" in auth_data
    assert "refresh_token" in auth_data
    assert auth_data["token_type"] == "bearer"
    assert auth_data["user"]["phone_e164"] == phone
    assert auth_data["user"]["status"] == "active"


@pytest.mark.asyncio
async def test_otp_resend_cooldown(client: AsyncClient):
    phone = "+919876543211"

    # First request succeeds
    resp1 = await client.post("/api/v1/auth/otp/send", json={"phone_e164": phone})
    assert resp1.status_code == 200

    # Second request immediately fails due to cooldown
    resp2 = await client.post("/api/v1/auth/otp/send", json={"phone_e164": phone})
    assert resp2.status_code == 429
    assert resp2.json()["code"] == "COOLDOWN_ACTIVE"


@pytest.mark.asyncio
async def test_otp_expiration(client: AsyncClient):
    phone = "+919876543212"

    send_resp = await client.post("/api/v1/auth/otp/send", json={"phone_e164": phone})
    assert send_resp.status_code == 200
    otp = InMemoryTestOTPProvider.get_last_otp(phone)

    # Simulate expired OTP by rewinding expires_at in the database
    past_time = datetime.now(UTC) - timedelta(minutes=10)
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE otp_requests SET expires_at = :exp WHERE phone_e164 = :phone"),
            {"exp": past_time, "phone": phone},
        )

    verify_resp = await client.post(
        "/api/v1/auth/otp/verify",
        json={"phone_e164": phone, "otp": otp},
    )
    assert verify_resp.status_code == 400
    assert verify_resp.json()["code"] == "OTP_EXPIRED"


@pytest.mark.asyncio
async def test_otp_attempt_limits_lock(client: AsyncClient):
    phone = "+919876543213"

    send_resp = await client.post("/api/v1/auth/otp/send", json={"phone_e164": phone})
    assert send_resp.status_code == 200

    # Attempt 1: wrong code
    resp1 = await client.post(
        "/api/v1/auth/otp/verify", json={"phone_e164": phone, "otp": "000000"}
    )
    assert resp1.status_code == 400
    assert resp1.json()["code"] == "OTP_INVALID"

    # Attempt 2: wrong code
    resp2 = await client.post(
        "/api/v1/auth/otp/verify", json={"phone_e164": phone, "otp": "111111"}
    )
    assert resp2.status_code == 400
    assert resp2.json()["code"] == "OTP_INVALID"

    # Attempt 3: wrong code
    resp3 = await client.post(
        "/api/v1/auth/otp/verify", json={"phone_e164": phone, "otp": "222222"}
    )
    assert resp3.status_code == 400
    assert resp3.json()["code"] == "OTP_INVALID"

    # Attempt 4: lock kicks in
    resp4 = await client.post(
        "/api/v1/auth/otp/verify", json={"phone_e164": phone, "otp": "333333"}
    )
    assert resp4.status_code == 400
    assert resp4.json()["code"] == "OTP_MAX_ATTEMPTS_EXCEEDED"


@pytest.mark.asyncio
async def test_token_refresh_and_rotation(client: AsyncClient):
    phone = "+919876543214"
    await client.post("/api/v1/auth/otp/send", json={"phone_e164": phone})
    otp = InMemoryTestOTPProvider.get_last_otp(phone)

    verify_resp = await client.post(
        "/api/v1/auth/otp/verify", json={"phone_e164": phone, "otp": otp}
    )
    tokens_v1 = verify_resp.json()
    refresh_token_1 = tokens_v1["refresh_token"]

    # Refresh token rotation
    refresh_resp = await client.post(
        "/api/v1/auth/token/refresh", json={"refresh_token": refresh_token_1}
    )
    assert refresh_resp.status_code == 200
    tokens_v2 = refresh_resp.json()
    refresh_token_2 = tokens_v2["refresh_token"]

    assert refresh_token_2 != refresh_token_1
    assert "access_token" in tokens_v2


@pytest.mark.asyncio
async def test_refresh_token_replay_attack_detection(client: AsyncClient):
    phone = "+919876543215"
    await client.post("/api/v1/auth/otp/send", json={"phone_e164": phone})
    otp = InMemoryTestOTPProvider.get_last_otp(phone)

    verify_resp = await client.post(
        "/api/v1/auth/otp/verify", json={"phone_e164": phone, "otp": otp}
    )
    tokens_v1 = verify_resp.json()
    refresh_token_1 = tokens_v1["refresh_token"]

    # Legitimate refresh rotates to tokens_v2
    refresh_resp = await client.post(
        "/api/v1/auth/token/refresh", json={"refresh_token": refresh_token_1}
    )
    assert refresh_resp.status_code == 200
    tokens_v2 = refresh_resp.json()
    refresh_token_2 = tokens_v2["refresh_token"]

    # Replay attack: Attacker attempts to use old refresh_token_1 again!
    replay_resp = await client.post(
        "/api/v1/auth/token/refresh", json={"refresh_token": refresh_token_1}
    )
    assert replay_resp.status_code == 401
    assert replay_resp.json()["code"] == "TOKEN_REPLAY_DETECTED"

    # Security check: the replacement session tree was also terminated!
    subsequent_resp = await client.post(
        "/api/v1/auth/token/refresh", json={"refresh_token": refresh_token_2}
    )
    assert subsequent_resp.status_code == 401
    assert subsequent_resp.json()["code"] == "TOKEN_REPLAY_DETECTED"


@pytest.mark.asyncio
async def test_logout_and_get_me(client: AsyncClient):
    phone = "+919876543216"
    await client.post("/api/v1/auth/otp/send", json={"phone_e164": phone})
    otp = InMemoryTestOTPProvider.get_last_otp(phone)

    verify_resp = await client.post(
        "/api/v1/auth/otp/verify", json={"phone_e164": phone, "otp": otp}
    )
    tokens = verify_resp.json()
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    # 1. Test /api/v1/auth/me with active access token
    headers = {"Authorization": f"Bearer {access_token}"}
    me_resp = await client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200
    profile = me_resp.json()
    assert profile["phone_e164"] == phone

    # 2. Logout with refresh token
    logout_resp = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
        headers=headers,
    )
    assert logout_resp.status_code == 200

    # 3. Subsequent call to /me fails because session was revoked
    revoked_me_resp = await client.get("/api/v1/auth/me", headers=headers)
    assert revoked_me_resp.status_code == 401
    assert revoked_me_resp.json()["code"] == "SESSION_REVOKED"
