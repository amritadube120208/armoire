import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_error_envelopes():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. 401 Unauthorized envelope
        res_401 = await client.get("/api/v1/users/me")
        assert res_401.status_code == 401
        body_401 = res_401.json()
        assert "data" in body_401 and body_401["data"] is None
        assert "error" in body_401
        assert body_401["error"]["code"] == 401
        assert "message" in body_401["error"]

        # 2. 404 Not Found envelope
        res_404 = await client.get("/api/v1/nonexistent-route-for-testing")
        assert res_404.status_code == 404
        body_404 = res_404.json()
        assert "data" in body_404 and body_404["data"] is None
        assert "error" in body_404
        assert body_404["error"]["code"] == 404

        # 3. 422 Validation Error envelope
        res_422 = await client.post("/api/v1/auth/signup", json={"email": "not-an-email"})
        assert res_422.status_code == 422
        body_422 = res_422.json()
        assert "data" in body_422 and body_422["data"] is None
        assert "error" in body_422
        assert body_422["error"]["code"] == 422
        assert "Validation Error" in body_422["error"]["message"]
        assert "details" in body_422["error"]
