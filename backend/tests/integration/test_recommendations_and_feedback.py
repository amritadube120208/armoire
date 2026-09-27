"""
Integration tests for Recommendations Engine & Feedback Personalization Loop (Phases 8 & 9).
"""

import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.main import app
from app.models.base import Base, async_engine, AsyncSessionLocal
from app.models.clothing import ClothingAttributes, ClothingImage, ClothingItem
from app.models.user import User, UserPreference


async def create_ready_wardrobe(user_id: uuid.UUID) -> dict:
    """Helper to populate a standard ready wardrobe for recommendation testing."""
    async with AsyncSessionLocal() as session:
        # Top: Blue T-shirt
        top = ClothingItem(
            user_id=user_id,
            category="tops",
            subtype="t-shirt",
            status="ready",
            wear_count=0,
        )
        session.add(top)
        await session.flush()
        top_img = ClothingImage(
            clothing_item_id=top.id,
            original_url="/storage/top.jpg",
            thumbnail_url="/storage/top_thumb.jpg",
            quality_band="good",
        )
        top_attr = ClothingAttributes(
            clothing_item_id=top.id,
            color_primary="blue",
            pattern="solid",
            formality_estimate="casual",
            formality_confidence=0.90,
            season_tags=["summer", "spring"],
        )
        session.add_all([top_img, top_attr])

        # Bottom: White Jeans
        bottom = ClothingItem(
            user_id=user_id,
            category="bottoms",
            subtype="jeans",
            status="ready",
            wear_count=0,
        )
        session.add(bottom)
        await session.flush()
        bot_img = ClothingImage(
            clothing_item_id=bottom.id,
            original_url="/storage/bottom.jpg",
            thumbnail_url="/storage/bottom_thumb.jpg",
            quality_band="good",
        )
        bot_attr = ClothingAttributes(
            clothing_item_id=bottom.id,
            color_primary="white",
            pattern="solid",
            formality_estimate="casual",
            formality_confidence=0.88,
            season_tags=["all-season"],
        )
        session.add_all([bot_img, bot_attr])

        # Shoes: White Sneakers
        shoes = ClothingItem(
            user_id=user_id,
            category="shoes",
            subtype="sneakers",
            status="ready",
            wear_count=0,
        )
        session.add(shoes)
        await session.flush()
        shoe_img = ClothingImage(
            clothing_item_id=shoes.id,
            original_url="/storage/shoes.jpg",
            thumbnail_url="/storage/shoes_thumb.jpg",
            quality_band="good",
        )
        shoe_attr = ClothingAttributes(
            clothing_item_id=shoes.id,
            color_primary="white",
            pattern="solid",
            formality_estimate="casual",
            formality_confidence=0.95,
            season_tags=["all-season"],
        )
        session.add_all([shoe_img, shoe_attr])

        # Outerwear: Black Jacket
        jacket = ClothingItem(
            user_id=user_id,
            category="outerwear",
            subtype="jacket",
            status="ready",
            wear_count=0,
        )
        session.add(jacket)
        await session.flush()
        jack_img = ClothingImage(
            clothing_item_id=jacket.id,
            original_url="/storage/jacket.jpg",
            thumbnail_url="/storage/jacket_thumb.jpg",
            quality_band="good",
        )
        jack_attr = ClothingAttributes(
            clothing_item_id=jacket.id,
            color_primary="black",
            pattern="solid",
            formality_estimate="casual",
            formality_confidence=0.85,
            season_tags=["autumn", "winter"],
        )
        session.add_all([jack_img, jack_attr])

        await session.commit()
        return {
            "top": str(top.id),
            "bottom": str(bottom.id),
            "shoes": str(shoes.id),
            "jacket": str(jacket.id),
        }


@pytest.mark.asyncio
async def test_recommendations_and_feedback_full_flow():
    # 1. Clean DB state
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 2. Signup User 1
        signup1 = {
            "email": "user1@recs.com",
            "password": "Password123!",
            "name": "Rec User 1",
        }
        res1 = await client.post("/api/v1/auth/signup", json=signup1)
        assert res1.status_code == 201
        token1 = res1.json()["access_token"]
        headers1 = {"Authorization": f"Bearer {token1}"}

        # Signup User 2 (for multi-tenant isolation verification)
        signup2 = {
            "email": "user2@recs.com",
            "password": "Password123!",
            "name": "Rec User 2",
        }
        res2 = await client.post("/api/v1/auth/signup", json=signup2)
        assert res2.status_code == 201
        token2 = res2.json()["access_token"]
        headers2 = {"Authorization": f"Bearer {token2}"}

        # Get User 1 profile to obtain user_id
        me_res = await client.get("/api/v1/users/me", headers=headers1)
        assert me_res.status_code == 200
        user1_id = uuid.UUID(me_res.json()["id"])

        # 3. Create ready wardrobe items for User 1
        wardrobe = await create_ready_wardrobe(user1_id)
        assert wardrobe["top"] is not None

        # 4. Request recommendations for User 1
        rec_res = await client.get(
            "/api/v1/recommendations?occasion=casual&lat=28.6&lon=77.2",
            headers=headers1,
        )
        assert rec_res.status_code == 200
        rec_data = rec_res.json()
        assert rec_data["total"] >= 1
        assert "recommendations" in rec_data
        assert "weather" in rec_data

        top_rec = rec_data["recommendations"][0]
        assert "items" in top_rec
        assert "score_breakdown" in top_rec
        assert "final_score" in top_rec
        assert top_rec["final_score"] > 0.0

        outfit_id = top_rec["id"]
        rec_id = top_rec.get("recommendation_id")

        # 5. Test "Why this outfit?" explain endpoint
        explain_res = await client.get(
            f"/api/v1/recommendations/{outfit_id}/explain",
            headers=headers1,
        )
        assert explain_res.status_code == 200
        explain_data = explain_res.json()
        assert "score_breakdown" in explain_data
        assert "reasoning" in explain_data
        assert "weather" in explain_data["reasoning"]
        assert "occasion" in explain_data["reasoning"]
        assert "color" in explain_data["reasoning"]

        # If rec_id exists, test lookup via recommendation_id as well
        if rec_id:
            explain_by_rec = await client.get(
                f"/api/v1/recommendations/{rec_id}/explain",
                headers=headers1,
            )
            assert explain_by_rec.status_code == 200

        # Verify User 2 cannot access User 1's recommendation explanation
        unauth_explain = await client.get(
            f"/api/v1/recommendations/{outfit_id}/explain",
            headers=headers2,
        )
        assert unauth_explain.status_code in [403, 404]

        # 6. Test Feedback: LIKE action
        fb_like_payload = {
            "outfit_id": outfit_id,
            "action": "like",
        }
        like_res = await client.post(
            "/api/v1/feedback",
            headers=headers1,
            json=fb_like_payload,
        )
        assert like_res.status_code == 201
        like_data = like_res.json()
        assert like_data["status"] == "success"
        assert like_data["data"]["preference_updated"] is True

        # Verify UserPreference updated via EMA in DB
        async with AsyncSessionLocal() as session:
            pref_stmt = select(UserPreference).where(UserPreference.user_id == user1_id)
            pref_res = await session.execute(pref_stmt)
            pref = pref_res.scalars().first()
            assert pref is not None
            # Blue and White were in the outfit -> should be boosted
            assert "blue" in pref.color_affinity or "white" in pref.color_affinity
            # Tops and Bottoms were in the outfit -> should be boosted
            assert "tops" in pref.category_affinity or "bottoms" in pref.category_affinity

        # 7. Test Feedback: WEAR action (tracks wear count)
        fb_wear_payload = {
            "outfit_id": outfit_id,
            "action": "wear",
        }
        wear_res = await client.post(
            "/api/v1/feedback",
            headers=headers1,
            json=fb_wear_payload,
        )
        assert wear_res.status_code == 201
        wear_data = wear_res.json()
        assert wear_data["data"]["wear_count_updated"] is True

        # Verify items in outfit have wear_count incremented and last_worn_date set
        async with AsyncSessionLocal() as session:
            item_stmt = select(ClothingItem).where(
                ClothingItem.id.in_([uuid.UUID(wardrobe["top"]), uuid.UUID(wardrobe["bottom"])])
            )
            items_res = await session.execute(item_stmt)
            items = items_res.scalars().all()
            for it in items:
                assert it.wear_count >= 1
                assert it.last_worn_date is not None

        # 8. Test Feedback: DISLIKE action
        fb_dislike_payload = {
            "outfit_id": outfit_id,
            "action": "dislike",
        }
        dislike_res = await client.post(
            "/api/v1/feedback",
            headers=headers1,
            json=fb_dislike_payload,
        )
        assert dislike_res.status_code == 201
        assert dislike_res.json()["data"]["preference_updated"] is True

        # 9. Verify User 2 cannot provide feedback for User 1's outfit
        unauth_fb = await client.post(
            "/api/v1/feedback",
            headers=headers2,
            json=fb_like_payload,
        )
        assert unauth_fb.status_code in [404, 422]
