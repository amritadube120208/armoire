import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.models.base import Base, async_engine


@pytest.mark.asyncio
async def test_refresh_rotation_and_logout_revoke_refresh_cookie():
    async with async_engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        signup = await client.post("/api/v1/auth/signup", json={
            "email": "rotation@example.com", "password": "LongEnoughPassword123!", "name": "Rotation Test",
        })
        assert signup.status_code == 201
        first_refresh = client.cookies.get("refresh_token")
        assert first_refresh
        cookie_header = signup.headers["set-cookie"].lower()
        assert "httponly" in cookie_header and "samesite=lax" in cookie_header

        rotated = await client.post("/api/v1/auth/refresh")
        assert rotated.status_code == 200
        assert rotated.json()["access_token"] != signup.json()["access_token"]
        second_refresh = client.cookies.get("refresh_token")
        assert second_refresh and second_refresh != first_refresh

        client.cookies.set("refresh_token", first_refresh)
        replay = await client.post("/api/v1/auth/refresh")
        assert replay.status_code == 401

        client.cookies.set("refresh_token", second_refresh)
        logout = await client.post("/api/v1/auth/logout", headers={
            "Authorization": f"Bearer {rotated.json()['access_token']}"
        })
        assert logout.status_code == 200
        cleared_cookie = logout.headers["set-cookie"].lower()
        assert "max-age=0" in cleared_cookie and "path=/" in cleared_cookie

        client.cookies.set("refresh_token", second_refresh)
        reuse_after_logout = await client.post("/api/v1/auth/refresh")
        assert reuse_after_logout.status_code == 401
