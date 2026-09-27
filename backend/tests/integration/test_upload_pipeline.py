import io
import uuid
import numpy as np
import pytest
from PIL import Image
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.models.base import Base, async_engine


def make_test_jpeg(width: int = 300, height: int = 300) -> bytes:
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    for y in range(0, height, 30):
        for x in range(0, width, 30):
            if (x // 30 + y // 30) % 2 == 0:
                arr[y:y+30, x:x+30] = [200, 50, 50]
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_full_auth_and_wardrobe_upload_pipeline():
    # Ensure fresh DB tables
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Health check
        res = await client.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] == "healthy"

        # 2. Signup User 1
        signup_payload = {
            "email": "user1@smartwardrobe.com",
            "password": "Password123!",
            "name": "Jane Doe"
        }
        res = await client.post("/api/v1/auth/signup", json=signup_payload)
        assert res.status_code == 201
        data = res.json()
        assert "access_token" in data
        user1_token = data["access_token"]
        headers1 = {"Authorization": f"Bearer {user1_token}"}

        # 3. Check /users/me
        res = await client.get("/api/v1/users/me", headers=headers1)
        assert res.status_code == 200
        assert res.json()["email"] == "user1@smartwardrobe.com"

        # 4. Upload Clothing Item
        image_bytes = make_test_jpeg(350, 350)
        files = {
            "file": ("summer_shirt.jpg", image_bytes, "image/jpeg")
        }
        res = await client.post("/api/v1/wardrobe/items", headers=headers1, files=files)
        assert res.status_code == 201
        item_data = res.json()
        item_id = item_data["id"]
        assert item_data["image"] is not None
        assert item_data["image"]["quality_band"] in ["good", "borderline", "poor"]

        # 5. Poll Status
        res = await client.get(f"/api/v1/wardrobe/items/{item_id}/status", headers=headers1)
        assert res.status_code == 200
        assert res.json()["id"] == item_id

        # 6. Retrieve Item Detail
        res = await client.get(f"/api/v1/wardrobe/items/{item_id}", headers=headers1)
        assert res.status_code == 200
        assert res.json()["id"] == item_id

        # 7. Update Item Attributes (user corrections)
        patch_payload = {
            "category": "top",
            "subtype": "linen shirt",
            "color_primary": "Navy",
            "pattern": "striped"
        }
        res = await client.patch(f"/api/v1/wardrobe/items/{item_id}", headers=headers1, json=patch_payload)
        assert res.status_code == 200
        assert res.json()["category"] == "top"
        assert res.json()["subtype"] == "linen shirt"
        assert res.json()["attributes"]["color_primary"] == "Navy"

        # 8. List Wardrobe Items with Filter
        res = await client.get("/api/v1/wardrobe/items?category=top", headers=headers1)
        assert res.status_code == 200
        list_data = res.json()
        assert list_data["total"] >= 1
        assert list_data["items"][0]["id"] == item_id

        # 9. Test Multi-tenant Isolation (User 2 cannot see User 1's item)
        signup_payload_2 = {
            "email": "user2@smartwardrobe.com",
            "password": "Password123!",
            "name": "Bob Smith"
        }
        res = await client.post("/api/v1/auth/signup", json=signup_payload_2)
        assert res.status_code == 201
        user2_token = res.json()["access_token"]
        headers2 = {"Authorization": f"Bearer {user2_token}"}

        # User 2 tries to access User 1's item -> strictly 404 Not Found
        res = await client.get(f"/api/v1/wardrobe/items/{item_id}", headers=headers2)
        assert res.status_code == 404

        # User 2 tries to edit User 1's item -> strictly 404 Not Found
        res = await client.patch(f"/api/v1/wardrobe/items/{item_id}", headers=headers2, json={"category": "bottom"})
        assert res.status_code == 404

        # User 2 tries to delete User 1's item -> strictly 404 Not Found
        res = await client.delete(f"/api/v1/wardrobe/items/{item_id}", headers=headers2)
        assert res.status_code == 404

        # User 2 wardrobe list is empty
        res = await client.get("/api/v1/wardrobe/items", headers=headers2)
        assert res.status_code == 200
        assert res.json()["total"] == 0

        # 10. User 1 Deletes their item
        res = await client.delete(f"/api/v1/wardrobe/items/{item_id}", headers=headers1)
        assert res.status_code == 200

        # Verify it's gone
        res = await client.get(f"/api/v1/wardrobe/items/{item_id}", headers=headers1)
        assert res.status_code == 404
