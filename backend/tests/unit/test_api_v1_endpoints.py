import io
import uuid
import pytest
import numpy as np
from PIL import Image
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.models.base import Base, async_engine


def make_test_jpeg(width: int = 250, height: int = 250) -> bytes:
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    for y in range(0, height, 25):
        for x in range(0, width, 25):
            arr[y:y+25, x:x+25] = [180, 120, 90]
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


async def init_tables():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@pytest.mark.asyncio
async def test_auth_negative_flows():
    await init_tables()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = f"user_{uuid.uuid4().hex[:6]}@example.com"
        res = await client.post("/api/v1/auth/signup", json={
            "email": email,
            "password": "ValidPass123!",
            "name": "Test User"
        })
        assert res.status_code == 201

        # Duplicate signup should return 409
        res_dup = await client.post("/api/v1/auth/signup", json={
            "email": email,
            "password": "ValidPass123!",
            "name": "Test User 2"
        })
        assert res_dup.status_code == 409

        # Bad password on login should return 401
        res_bad_pw = await client.post("/api/v1/auth/login", json={
            "email": email,
            "password": "WrongPassword123!"
        })
        assert res_bad_pw.status_code == 401

        # Nonexistent user login should return 401
        res_no_user = await client.post("/api/v1/auth/login", json={
            "email": "nonexistent@example.com",
            "password": "ValidPass123!"
        })
        assert res_no_user.status_code == 401

        # Protected endpoint without token should return 401
        res_no_auth = await client.get("/api/v1/users/me")
        assert res_no_auth.status_code == 401

        # Protected endpoint with malformed token should return 401
        res_malformed = await client.get("/api/v1/users/me", headers={"Authorization": "Bearer invalid.token.value"})
        assert res_malformed.status_code == 401


@pytest.mark.asyncio
async def test_user_profile_crud():
    await init_tables()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = f"profile_{uuid.uuid4().hex[:6]}@example.com"
        res = await client.post("/api/v1/auth/signup", json={
            "email": email,
            "password": "SecretPass123!",
            "name": "Initial Name"
        })
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Get profile
        res_me = await client.get("/api/v1/users/me", headers=headers)
        assert res_me.status_code == 200
        assert res_me.json()["name"] == "Initial Name"

        # Update profile
        patch_payload = {
            "name": "Updated Luxury User",
            "units": "imperial",
            "location": {"lat": 40.7128, "lon": -74.0060, "city": "New York"}
        }
        res_patch = await client.patch("/api/v1/users/me", headers=headers, json=patch_payload)
        assert res_patch.status_code == 200
        updated = res_patch.json()
        assert updated["name"] == "Updated Luxury User"
        assert updated["units"] == "imperial"
        assert updated["location"]["city"] == "New York"


@pytest.mark.asyncio
async def test_outfits_crud_and_not_found_handling():
    await init_tables()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = f"outfits_{uuid.uuid4().hex[:6]}@example.com"
        res = await client.post("/api/v1/auth/signup", json={
            "email": email,
            "password": "SecretPass123!",
            "name": "Outfit User"
        })
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Upload a clothing item to put into the outfit
        img_bytes = make_test_jpeg()
        files = {"file": ("test_item.jpg", img_bytes, "image/jpeg")}
        data = {"category": "tops", "name": "Silk Blouse"}
        res_upload = await client.post("/api/v1/wardrobe/items", headers=headers, files=files, data=data)
        assert res_upload.status_code == 201
        item_id = res_upload.json()["id"]

        # 2. Create outfit
        create_payload = {
            "occasion": "formal",
            "clothing_item_ids": [item_id],
            "source": "manual"
        }
        res_create = await client.post("/api/v1/outfits", headers=headers, json=create_payload)
        assert res_create.status_code == 201
        outfit = res_create.json()
        outfit_id = outfit["id"]
        assert outfit["occasion"] == "formal"
        assert len(outfit["items"]) == 1

        # 3. List outfits
        res_list = await client.get("/api/v1/outfits?occasion=formal", headers=headers)
        assert res_list.status_code == 200
        outfits_list = res_list.json()
        assert len(outfits_list) >= 1
        assert outfits_list[0]["id"] == outfit_id

        # 4. Get outfit by id
        res_get = await client.get(f"/api/v1/outfits/{outfit_id}", headers=headers)
        assert res_get.status_code == 200
        assert res_get.json()["id"] == outfit_id

        # 5. Get nonexistent outfit (Tests HTTPException import & clean 404 response)
        fake_id = str(uuid.uuid4())
        res_fake = await client.get(f"/api/v1/outfits/{fake_id}", headers=headers)
        assert res_fake.status_code == 404
        assert "error" in res_fake.json()

        # 6. Delete outfit
        res_del = await client.delete(f"/api/v1/outfits/{outfit_id}", headers=headers)
        assert res_del.status_code == 200

        # 7. Delete nonexistent outfit (Tests HTTPException import & clean 404 response)
        res_del_fake = await client.delete(f"/api/v1/outfits/{fake_id}", headers=headers)
        assert res_del_fake.status_code == 404
        assert "error" in res_del_fake.json()


@pytest.mark.asyncio
async def test_favorites_api():
    await init_tables()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = f"fav_{uuid.uuid4().hex[:6]}@example.com"
        res = await client.post("/api/v1/auth/signup", json={
            "email": email,
            "password": "SecretPass123!",
            "name": "Fav User"
        })
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        fake_outfit_id = str(uuid.uuid4())
        # Favorite
        res_fav = await client.post(f"/api/v1/favorites/{fake_outfit_id}", headers=headers)
        assert res_fav.status_code == 200
        assert res_fav.json()["message"] == "Outfit favorited."

        # Unfavorite
        res_unfav = await client.delete(f"/api/v1/favorites/{fake_outfit_id}", headers=headers)
        assert res_unfav.status_code == 200
        assert res_unfav.json()["message"] == "Outfit unfavorited."


@pytest.mark.asyncio
async def test_image_enhancement_choice():
    await init_tables()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = f"enhance_{uuid.uuid4().hex[:6]}@example.com"
        res = await client.post("/api/v1/auth/signup", json={
            "email": email,
            "password": "SecretPass123!",
            "name": "Enhance User"
        })
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Upload an item first
        img_bytes = make_test_jpeg()
        files = {"file": ("enhance_test.jpg", img_bytes, "image/jpeg")}
        res_up = await client.post("/api/v1/wardrobe/items", headers=headers, files=files)
        assert res_up.status_code == 201
        item_id = res_up.json()["id"]

        # Confirm enhancement choice 'use_original'
        res_choice = await client.post(
            f"/api/v1/images/{item_id}/enhance",
            headers=headers,
            json={"action": "use_original"}
        )
        assert res_choice.status_code == 200
        assert res_choice.json()["id"] == item_id

        # Nonexistent item returns 404
        fake_id = str(uuid.uuid4())
        res_fake = await client.post(
            f"/api/v1/images/{fake_id}/enhance",
            headers=headers,
            json={"action": "use_original"}
        )
        assert res_fake.status_code == 404


@pytest.mark.asyncio
async def test_weather_and_cities_api():
    await init_tables()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = f"weather_{uuid.uuid4().hex[:6]}@example.com"
        res = await client.post("/api/v1/auth/signup", json={
            "email": email,
            "password": "SecretPass123!",
            "name": "Weather User"
        })
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Weather with lat & lon
        res_wx = await client.get("/api/v1/weather/current?lat=19.076&lon=72.877", headers=headers)
        assert res_wx.status_code == 200
        wx = res_wx.json()
        assert "temperature" in wx
        assert "requirement_band" in wx

        # Weather with city search
        res_city = await client.get("/api/v1/weather/current?city=London", headers=headers)
        assert res_city.status_code == 200
        assert "London" in res_city.json().get("city", "")

        # Cities search
        res_search = await client.get("/api/v1/weather/cities?q=Paris", headers=headers)
        assert res_search.status_code == 200
        assert isinstance(res_search.json(), list)


@pytest.mark.asyncio
async def test_stylist_chat_api():
    await init_tables()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = f"stylist_{uuid.uuid4().hex[:6]}@example.com"
        res = await client.post("/api/v1/auth/signup", json={
            "email": email,
            "password": "SecretPass123!",
            "name": "Stylist User"
        })
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Fashion styling query
        req_payload = {
            "message": "What colors pair nicely with a camel coat?",
            "occasion": "casual",
            "lat": 28.6,
            "lon": 77.2
        }
        res_chat = await client.post("/api/v1/stylist/chat", headers=headers, json=req_payload)
        assert res_chat.status_code == 200
        chat_data = res_chat.json()
        assert len(chat_data["reply"]) > 20
        assert isinstance(chat_data["suggestions"], list)

        # 2. Strict refusal of academic/study content
        study_payload = {
            "message": "Can you solve this physics homework equation?"
        }
        res_study = await client.post("/api/v1/stylist/chat", headers=headers, json=study_payload)
        assert res_study.status_code == 200
        study_data = res_study.json()
        reply_lower = study_data["reply"].lower()
        assert "fashion" in reply_lower or "style" in reply_lower or "wardrobe" in reply_lower


@pytest.mark.asyncio
async def test_clothing_alias_routes():
    await init_tables()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        email = f"alias_{uuid.uuid4().hex[:6]}@example.com"
        res = await client.post("/api/v1/auth/signup", json={
            "email": email,
            "password": "SecretPass123!",
            "name": "Alias User"
        })
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Access /api/v1/clothing/items
        res_items = await client.get("/api/v1/clothing/items", headers=headers)
        assert res_items.status_code == 200
        assert "items" in res_items.json()
        assert "total" in res_items.json()
