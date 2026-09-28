import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from app.core.security import decode_token
from app.main import app
from app.models.base import Base, async_engine, AsyncSessionLocal
from app.models.user import UserSession
from sqlalchemy import select


@pytest.mark.asyncio
async def test_session_lifecycle_and_atomic_rotation():
    # Setup fresh database tables
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Signup creates user and persisted session
        signup_payload = {
            "email": "session_user@smartwardrobe.com",
            "password": "Password123!",
            "name": "Session Tester"
        }
        res = await client.post("/api/v1/auth/signup", json=signup_payload)
        assert res.status_code == 201
        data = res.json()
        assert "access_token" in data
        refresh_cookie_1 = res.cookies.get("refresh_token")
        assert refresh_cookie_1 is not None

        # Verify claims
        payload_1 = decode_token(refresh_cookie_1)
        assert payload_1 is not None
        assert payload_1["type"] == "refresh"
        jti_1 = payload_1["jti"]
        family_1 = payload_1["family"]
        assert jti_1 is not None
        assert family_1 is not None

        # Verify session persisted in DB
        async with AsyncSessionLocal() as db:
            stmt = select(UserSession).where(UserSession.jti == jti_1)
            session_1 = (await db.execute(stmt)).scalar_one_or_none()
            assert session_1 is not None
            assert session_1.is_revoked is False
            assert str(session_1.token_family) == family_1

        # 2. Refresh token: Atomic rotation
        res_refresh = await client.post("/api/v1/auth/refresh")
        assert res_refresh.status_code == 200
        refresh_cookie_2 = res_refresh.cookies.get("refresh_token")
        assert refresh_cookie_2 is not None
        assert refresh_cookie_2 != refresh_cookie_1

        payload_2 = decode_token(refresh_cookie_2)
        jti_2 = payload_2["jti"]
        family_2 = payload_2["family"]
        assert jti_2 != jti_1
        assert family_2 == family_1  # Family preserved across rotation

        # Verify in DB: session 1 is now revoked, session 2 is active
        async with AsyncSessionLocal() as db:
            s1 = (await db.execute(select(UserSession).where(UserSession.jti == jti_1))).scalar_one()
            assert s1.is_revoked is True

            s2 = (await db.execute(select(UserSession).where(UserSession.jti == jti_2))).scalar_one()
            assert s2.is_revoked is False
            assert s2.token_family == s1.token_family

        # 3. REUSE DETECTION: Re-presenting old token (refresh_cookie_1)
        client.cookies.set("refresh_token", refresh_cookie_1)
        res_reuse = await client.post("/api/v1/auth/refresh")
        err_data = res_reuse.json()
        error_msg = (err_data.get("error", {}).get("message") if isinstance(err_data.get("error"), dict) else None) or err_data.get("detail", "")
        assert "compromised" in error_msg.lower()

        # Entire token family must now be revoked
        async with AsyncSessionLocal() as db:
            stmt = select(UserSession).where(UserSession.token_family == uuid.UUID(family_1))
            family_sessions = (await db.execute(stmt)).scalars().all()
            assert len(family_sessions) >= 2
            assert all(s.is_revoked is True for s in family_sessions)

        # Even the newer token (refresh_cookie_2) must now be rejected
        client.cookies.set("refresh_token", refresh_cookie_2)
        res_rejected = await client.post("/api/v1/auth/refresh")
        assert res_rejected.status_code == 401


@pytest.mark.asyncio
async def test_logout_revocation():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Login with demo or signup new user
        signup_payload = {
            "email": "logout_test@smartwardrobe.com",
            "password": "Password123!",
            "name": "Logout Tester"
        }
        res = await client.post("/api/v1/auth/signup", json=signup_payload)
        assert res.status_code == 201
        access_token = res.json()["access_token"]
        refresh_cookie = res.cookies.get("refresh_token")
        payload = decode_token(refresh_cookie)
        jti = payload["jti"]

        headers = {"Authorization": f"Bearer {access_token}"}
        res_logout = await client.post("/api/v1/auth/logout", headers=headers)
        assert res_logout.status_code == 200

        # DB session must be marked revoked
        async with AsyncSessionLocal() as db:
            s = (await db.execute(select(UserSession).where(UserSession.jti == jti))).scalar_one()
            assert s.is_revoked is True

        # Refresh attempt must fail
        client.cookies.set("refresh_token", refresh_cookie)
        res_refresh = await client.post("/api/v1/auth/refresh")
        assert res_refresh.status_code == 401


@pytest.mark.asyncio
async def test_password_length_guard():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Password > 72 bytes should fail validation (HTTP 422)
        long_password = "a" * 73
        res = await client.post(
            "/api/v1/auth/signup",
            json={
                "email": "toolong@smartwardrobe.com",
                "password": long_password,
                "name": "Too Long"
            }
        )
        assert res.status_code == 422
