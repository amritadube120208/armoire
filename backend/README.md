# Smart Wardrobe & AI Recommendation System — Backend (Phases 1–9 Complete)

FastAPI backend for the **Smart Wardrobe & AI Recommendation System**. This document describes the current implementation; the product specifications in the repository also include planned capabilities.

---

## 1. What Is Implemented

### Phase 1: Architecture & Scaffolding
- **Application Core**: FastAPI application with lifespan management, CORS middleware, centralized structured logging (`structlog`), Pydantic Settings reading `.env`.
- **Health Checks**: `GET /health` and `GET /api/v1/health` returning live service health.
- **Docker Compose**: Local development services in `docker-compose.yml`; single-host production starter in `docker-compose.prod.yml`.
- **Database Migrations**: Alembic revisions create application tables and refresh-session storage.

### Phase 3: Authentication & Security (Backend.md Pipeline 1)
- **Signup**: `POST /api/v1/auth/signup` — email format, password length and bcrypt input bound validation, unique email constraint, bcrypt password hashing, automatic default preference profile creation.
- **Login**: `POST /api/v1/auth/login` — credential verification, short-lived JWT access token issuance (15 min), httpOnly secure refresh token cookie (7 days).
- **Refresh**: `POST /api/v1/auth/refresh` — token rotation via secure httpOnly cookie.
- **Logout**: `POST /api/v1/auth/logout` — invalidates refresh session.
- **User Profile**: `GET /api/v1/users/me` and `PATCH /api/v1/users/me` for profile and onboarding style preference updates.
- **Dependencies**: `get_current_user` OAuth2 Bearer token dependency with automatic token verification.

### Phase 4: Wardrobe CRUD (Backend.md §4 & §5)
- **CRUD Endpoints**:
  - `POST /api/v1/wardrobe/items`: Multipart photo upload.
  - `GET /api/v1/wardrobe/items`: List & filter wardrobe items by `category`, `color`, `season`, `status` with pagination.
  - `GET /api/v1/wardrobe/items/{id}`: Item details including image URLs and confidence-scored attributes.
  - `PATCH /api/v1/wardrobe/items/{id}`: Manual attribute corrections (powers the user-corrected label data flywheel).
  - `DELETE /api/v1/wardrobe/items/{id}`: Deletes item and purges image assets from storage.
  - `GET /api/v1/wardrobe/items/{id}/status`: Polling endpoint for async processing status (`processing`, `ready`, `needs_review`, `failed`).
- **Multi-Tenant Row-Level Security (Backend.md §10)**: Every database query is strictly scoped to `user_id` at the `ClothingRepository` layer, guaranteeing cross-tenant data isolation.

### Phase 5: Image Processing & Quality Gate (Backend.md Pipeline 2 & 3)
- **Validation**: Magic byte inspection (JPEG, PNG, WEBP), file size caps (15MB), dimension sanity check.
- **EXIF/GPS Stripping**: Server-side re-encoding via Pillow neutralizes embedded payloads and completely removes GPS/EXIF location metadata.
- **Deterministic Quality Gate (`app/ai/quality.py`)**:
  - Blur detection via OpenCV Laplacian variance (`cv2.Laplacian.var()`).
  - Resolution checks (minimum width/height).
  - Brightness/exposure histogram analysis.
  - 3-band classification: **Good** (direct pass), **Borderline** (candidate enhancement generated for user review), **Poor** (confidence cap applied, manual entry recommended).
- **Enhancement Transparency Rule**: Enhancement (`app/ai/enhancement.py`) strictly uses bounded sharpening/contrast adjustments. It **never** generatively hallucinates missing garment details or textures. Enhancement choices (`use_enhanced`, `use_original`, `retake`) are confirmed via `POST /api/v1/images/{item_id}/enhance`.
- **Deterministic Color Extraction (`app/ai/color.py`)**: K-means clustering on pixels extracts dominant and secondary colors without model guesswork.
- **Storage**: Pluggable storage abstraction (`app/image_processing/storage.py`) supporting local filesystem storage with static mounts and S3/R2 with signed URLs.
- **Async Workers**: Celery + Redis task execution (`app/workers/tasks.py`) with automatic non-blocking asyncio fallback for standalone environments.

### Phase 6: Deterministic AI Classification (`app/ai/classification.py`)
- Deterministic placeholder category and subtype classification; it is not a trained visual model.
- Real quality-gate confidence capping (`{"poor": 0.45, "borderline": 0.72, "good": 0.92}`).
- Generates seasonal tags, pattern estimates, and formality ratings.

### Phase 7: Live Weather & Requirement Bands (`app/weather/`, `app/services/weather_service.py`)
- Live OpenWeatherMap client with deterministic mock fallback when `OPENWEATHER_API_KEY` is not configured.
- Maps raw weather into temperature bands (7 bands) and precipitation bands to produce actionable `RequirementBand` guidance.
- Redis caching (30-minute TTL, rounded coordinates) and persistence to `weather_snapshots` with graceful offline fallback.
- `GET /api/v1/weather/current`: Returns current normalized conditions + requirement band.

### Phase 8: Multi-Factor Recommendation Engine (`app/recommendations/`, `app/api/v1/recommendations.py`)
- 6-dimension scoring pipeline:
  1. **WeatherScore**: Curved penalty matching garment warmth against current conditions with extreme temperature exclusions.
  2. **OccasionScore**: 13 occasion formality bands with asymmetric penalties and confidence widening.
  3. **ColorScore**: HSL circular distance and color theory rules (monochrome, analogous, complementary, triadic, neutrals, clash).
  4. **StyleScore**: Cosine similarity across garment visual embeddings with pattern coherence fallback.
  5. **PersonalizationScore**: EMA preference matching (color/category) + logarithmic wear count scaling.
  6. **DiversityScore**: Jaccard index vs. recent outfits scaled by exponential recency decay.
- Candidate generation: Type A (top + bottom ± outerwear ± shoes) and Type B (dress ± outerwear ± shoes).
- Persists top candidates as AI outfits in `outfits` and `recommendations` tables.
- `GET /api/v1/recommendations`: Returns ranked recommendations with full score breakdowns.
- `GET /api/v1/recommendations/{id}/explain`: Backs the "Why this outfit" UI panel with human-readable reasoning strings.

### Phase 9: Feedback & Personalization Loop (`app/services/feedback_service.py`, `app/api/v1/feedback.py`)
- `POST /api/v1/feedback`: Accepts `like`, `dislike`, `save`, `wear`, and `swap`.
- Exponential Moving Average ($\alpha = 0.3$) updates to `UserPreference.color_affinity` and `category_affinity`.
- Increments `wear_count` and updates `last_worn_date` for worn items.
- Strict multi-tenant authorization check preventing cross-user feedback pollution.

---

## 2. API Endpoints Overview

All endpoints under `/api/v1`. Authentication required via `Authorization: Bearer <token>` unless noted:

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| POST | `/api/v1/auth/signup` | Register new account | No |
| POST | `/api/v1/auth/login` | Issue access token & refresh cookie | No |
| POST | `/api/v1/auth/refresh` | Refresh access token | Cookie |
| POST | `/api/v1/auth/logout` | Invalidate session | Yes |
| GET | `/api/v1/users/me` | Current user profile & preferences | Yes |
| PATCH | `/api/v1/users/me` | Update profile / preferences | Yes |
| POST | `/api/v1/wardrobe/items` | Upload clothing item (multipart) | Yes |
| GET | `/api/v1/wardrobe/items` | List & filter wardrobe items | Yes |
| GET | `/api/v1/wardrobe/items/{id}` | Garment details with confidence scores | Yes |
| PATCH | `/api/v1/wardrobe/items/{id}` | Edit garment attributes (corrections) | Yes |
| DELETE | `/api/v1/wardrobe/items/{id}` | Delete item and image assets | Yes |
| GET | `/api/v1/wardrobe/items/{id}/status` | Poll processing status | Yes |
| POST | `/api/v1/images/{item_id}/enhance` | Confirm enhancement choice | Yes |
| GET | `/api/v1/weather/current` | Current weather & requirement band | Yes |
| GET | `/api/v1/recommendations` | Ranked outfit recommendations | Yes |
| GET | `/api/v1/recommendations/{id}/explain` | "Why this outfit" score breakdown | Yes |
| POST | `/api/v1/outfits` | Save manual or custom outfit | Yes |
| GET | `/api/v1/outfits` | List user's saved outfits | Yes |
| GET | `/api/v1/outfits/{id}` | Get outfit detail | Yes |
| DELETE | `/api/v1/outfits/{id}` | Delete saved outfit | Yes |
| POST | `/api/v1/favorites/{outfit_id}` | Favorite an outfit | Yes |
| DELETE | `/api/v1/favorites/{outfit_id}` | Unfavorite an outfit | Yes |
| POST | `/api/v1/feedback` | Record feedback & update preferences | Yes |

---

## 3. How to Run

### Local Development (Quickstart)
1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   alembic upgrade head
   ```
2. **Start the API**:
   ```bash
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
3. **Interactive Documentation**:
   - Swagger UI: [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)
   - ReDoc: [http://localhost:8000/api/v1/redoc](http://localhost:8000/api/v1/redoc)
   - Health check: [http://localhost:8000/health](http://localhost:8000/health)

### Running the local development stack
```bash
cp .env.example .env
docker compose up --build
```
PostgreSQL and Redis ports are bound to localhost. See [DEPLOYMENT.md](DEPLOYMENT.md) for the production Compose profile, secret setup, TLS boundary, and operational checklist.

---

## 4. Running Tests

Install the test dependencies and run the suite:
```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

Frontend authentication tests run from the repository root with `node --test backend/tests/frontend/api.test.cjs`.

To run unit tests only:
```bash
python -m pytest tests/unit -v
```

To run integration tests only:
```bash
python -m pytest tests/integration -v
```
