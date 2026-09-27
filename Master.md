# Master.md — Smart Wardrobe & AI Recommendation System
### Master Document — Single Source of Truth

> **Strategic Instruction:** "CHECK ALL EXISTING IDEAS OF THIS SOLUTION AND THEN MAKE MINE BETTER THAN THEM IN EVERY ASPECT."

---

## Project Overview

Smart Wardrobe is an AI-assisted personal styling application that helps users build outfits from clothes they **already own**. Users photograph their existing wardrobe; the system understands, categorizes, and enhances those photos where needed, then recommends complete outfits based on real-time weather, occasion, personal style, and learned preference — always explaining *why* an outfit was chosen, and never suggesting an item the user doesn't actually own.

## Problem Statement

People own more clothes than they actively use, and "what should I wear" is a recurring daily decision made harder by scattered physical wardrobes, unpredictable weather, and no easy way to see combinations across everything owned at once. Existing digital-wardrobe apps (Whering, Acloset, Alta, Stylebook, Cladwell) have proven the category has real demand, but each has a specific, documented gap: opaque "black box" recommendations with no visible reasoning, feature bloat that overwhelms new users, paywalled core features, or no real AI assistance at all.

## Proposed Solution

A digital wardrobe platform where:
1. Users upload photos of clothes they own.
2. AI classifies, tags, and (when needed, transparently) enhances low-quality photos.
3. A deterministic, explainable multi-factor scoring engine — not an opaque single model call — generates and ranks outfit recommendations from the user's own wardrobe.
4. Every recommendation shows its reasoning (weather / occasion / color / style / personalization / diversity breakdown).
5. Feedback (likes, dislikes, wears) continuously personalizes future recommendations.

## Target Users

- Style-conscious individuals who feel they "have nothing to wear" despite a full closet.
- Busy professionals who want fast, weather-appropriate outfit decisions each morning.
- Minimalists/sustainability-minded users trying to use more of what they already own rather than buying new.
- Students/young professionals building a personal style with a limited but growing wardrobe.

## Core Features

- Photo-based wardrobe digitization with AI classification.
- Transparent, opt-in AI image enhancement for blurry/poor-quality photos.
- Weather-based outfit recommendation using live conditions.
- Occasion-based outfit recommendation with configurable dress-code rules.
- Explainable scoring ("Why this outfit") for every recommendation.
- Feedback-driven personalization loop.
- Wardrobe browsing, search, and outfit history/saved outfits.
- Wardrobe-constrained recommendations only — never suggests items the user doesn't own.

## Unique Selling Proposition

**"See exactly why every outfit was picked — from clothes you already own — not a black box, and not a shopping funnel in disguise."**

## Competitive Differentiation

| Dimension | Whering | Acloset | Alta | Stylebook | Cladwell | **Smart Wardrobe** |
|---|---|---|---|---|---|---|
| Explainable recommendations ("why this outfit") | No | No | No (adaptive but opaque) | N/A (manual) | No | **Yes — full score breakdown shown** |
| Honest, transparent image enhancement UX | Partial | Partial | Yes ("Prettify") but limitation not framed | N/A | N/A | **Yes — before/after + explicit limitation copy** |
| Recommends only owned items (not brand partner stock) | Yes | Yes | No (curates partner-brand looks) | Yes | Yes | **Yes** |
| Deterministic-to-ML upgrade path documented | Not public | Not public | Not public | N/A | Not public | **Yes — explicit in Upgradation.md** |
| Free core recommendation features | Yes | Yes | Yes | Paid | Paid | **Yes (MVP)** |
| Onboarding friction | Medium-high (feature-dense) | Low-medium | Low | Medium | Medium | **Low — progressive, usable at 3-5 items** |

## User Journey

1. **Discover & sign up** → landing page explains the loop in seconds.
2. **Onboarding** → style preferences, location, first 3–5 clothing photos (skippable, low-friction).
3. **Upload continues over time** → wardrobe grows via Add Clothing flow; AI classifies, user reviews/corrects.
4. **Daily use** → opens app, sees today's weather-matched hero outfit with reasoning, browses alternates.
5. **Occasion planning** → picks a specific occasion (interview, date, party) for a scoped recommendation set.
6. **Feedback** → likes/dislikes/saves/marks-as-worn, which sharpens future recommendations.
7. **Growth loop** → saved outfits, wardrobe stats, and (later) social/sharing features deepen engagement.

## Complete System Architecture

See `Backend.md` §1 for the full diagram. Summary: Next.js frontend → FastAPI backend, split into Auth, Wardrobe, Image Processing, AI/ML, Recommendation Engine, Weather, and Feedback services, backed by PostgreSQL (+pgvector), Redis, and S3-compatible object storage, with AI-heavy work processed asynchronously via a background job queue.

## Frontend Architecture

Next.js 15 (App Router) + TypeScript + Tailwind CSS + shadcn/ui, Zustand for UI state, TanStack Query for server state, responsive PWA-first (mobile app shell is a later phase). Full rationale in `Skills.md` §1.

## Backend Architecture

Python 3.12 + FastAPI, layered as `api → services → repositories`, with dedicated `ai/`, `recommendations/`, `weather/`, and `image_processing/` modules and Celery/Redis for background jobs. Full structure in `Backend.md` §2.

## Database Architecture

PostgreSQL as the system of record (users, clothing items, outfits, feedback, weather snapshots), pgvector extension for embeddings (MVP), Redis for cache/queues, S3-compatible object storage for images. Full ER diagram in `Backend.md` §5.

## AI Architecture

Deterministic logic is used wherever it is more reliable than a model (blur detection, color extraction, weather/occasion rule mapping); AI/ML is used specifically for clothing detection, classification, pattern/style estimation, image enhancement, and embeddings — each with an attached confidence score. Full breakdown in `Skills.md` §3 and `Backend.md` §6.

## Recommendation Engine

A weighted multi-factor scoring formula (Weather, Occasion, Color, Style, Personalization, Diversity) applied to candidate outfits generated from the user's filtered wardrobe, fully detailed with the scoring formula in `Backend.md` Pipeline 7. Designed to evolve from fixed weights → per-user learned weights → a full learned ranking model without changing its API contract.

## Image Enhancement System

A three-band quality gate (Good/Borderline/Poor) determines whether enhancement runs at all; when it does, the user always sees an honest before/after comparison and can choose original, enhanced, or retake. Enhancement is constrained to sharpening/upscaling existing pixel data — it never generatively invents garment detail that isn't in the photo. Full pipeline in `Backend.md` Pipeline 3, full UX in `Design.md` §5.

## Weather Integration

OpenWeatherMap data (temperature, feels-like, humidity, precipitation, wind) is normalized into deterministic clothing-requirement bands that filter and score the wardrobe. Cached per-location (~30 min) to control API cost and latency. Full pipeline in `Backend.md` Pipeline 5.

## Complete Data Flow

```
Upload → Validate/Store Original → Quality Gate → [Enhance if needed] → Detect/Segment
   → Classify + Extract Attributes (confidence-scored) → Embed → Wardrobe Library
   
Recommendation request → Weather fetched/cached → Occasion rules applied
   → Wardrobe filtered → Candidates generated → Multi-factor scored → Ranked → Displayed with reasoning
   
User feedback → Preference weights updated → Future recommendations adjusted
```

## Security & Privacy

JWT-based auth, per-user row-level access control, re-encoded uploads (EXIF/GPS stripped), encryption at rest and in transit, signed URLs for all private image access, explicit consent flow, minimal retention of abandoned uploads, full account-deletion cascade. Full detail in `Skills.md` §7 and `Backend.md` §10.

## Technology Stack

| Layer | Choice |
|---|---|
| Frontend | Next.js + TypeScript + Tailwind + shadcn/ui |
| Backend | Python + FastAPI |
| Database | PostgreSQL + pgvector |
| Cache/Queue | Redis + Celery |
| Object storage | S3-compatible (AWS S3 / Cloudflare R2) |
| Weather | OpenWeatherMap |
| AI (vision/enhancement) | Hosted inference APIs initially, self-hostable later |
| Auth | Custom JWT (FastAPI) + optional Google OAuth |
| Deployment | Vercel (frontend), Render/Fly.io/Railway or AWS ECS (backend) |
| Monitoring | Sentry + structured logging |

Full rationale for every choice: `Skills.md`.

## Folder Structure

See `Backend.md` §2 for the complete annotated backend folder structure.

## API Overview

REST API under `/api/v1` covering auth, users, wardrobe items, images/enhancement, weather, recommendations (+ explain endpoint), outfits, favorites, and feedback. Full endpoint table in `Backend.md` §4.

## Development Roadmap

See `Upgradation.md` for the full phase-by-phase roadmap (Phase 0–12) and the four-level product evolution (MVP → Advanced MVP → Production → AI Wardrobe Platform).

## MVP Scope

- Auth (email/password + Google OAuth)
- Wardrobe upload with AI classification (category, color, basic pattern) + manual correction
- Basic quality gate + enhancement (Borderline/Poor band handling)
- Weather-based recommendation (rule-based)
- Occasion-based recommendation (rule-based, fixed occasion list)
- Deterministic multi-factor scoring engine with fixed default weights
- Feedback capture (like/dislike/save/wear) feeding simple preference updates
- Responsive web PWA UI covering all 15 screens in `Design.md`

## Phase 2 (Advanced MVP)

- Improved classification accuracy via fine-tuned models on corrected-label data
- Color/pattern detection refinement
- Per-user learned scoring weights (still explainable)
- Outfit history and richer saved-outfit management
- Embedding-based similarity ("outfits like this")
- Better/self-hosted enhancement model if cost justifies

## Phase 3 (Production)

- Background job scaling (dedicated Celery worker pools)
- Caching maturity, CDN for all imagery
- Learned ranking model (gradient-boosted ranker) replacing fixed-weight scoring where enough data exists
- Analytics dashboards (internal + user-facing wardrobe stats)
- Production monitoring/alerting, formal SLAs on recommendation latency
- Hardened security review, penetration testing

## Future Vision (AI Wardrobe Platform)

Virtual try-on, body-aware recommendations, AI stylist chat, calendar-based outfit planning, packing assistant, laundry-aware recommendations, shopping-gap suggestions (only for items genuinely missing from wardrobe coverage, never a disguised ad funnel), sustainability insights. Full detail in `Upgradation.md` Level 4.

## Monetization Possibilities

- Freemium: core wardrobe + recommendations free (matches competitive baseline — Whering/Acloset/Alta are free); premium tier for advanced analytics, virtual try-on, AI stylist chat, unlimited AI enhancement credits.
- Affiliate/marketplace (opt-in only): "you're missing a versatile item" suggestions linking to retail, clearly separated from core recommendation logic so it never biases which owned items get recommended.
- B2B potential: white-label wardrobe/recommendation engine for retailers wanting a "shop your closet" feature.

## Scalability

Async job architecture and the isolated AI service layer (Backend.md §1) mean image-processing and model-serving capacity can scale independently of the API tier; pgvector can be migrated to a dedicated vector DB without touching the recommendation engine's interface; read replicas and caching absorb read-heavy wardrobe/browse traffic. Full detail in `Upgradation.md` Level 3.

## Risks and Mitigation

| Risk | Mitigation |
|---|---|
| Classification/attribute accuracy too low for trust | Confidence scores + always-editable fields + user-correction data flywheel for fine-tuning |
| Enhancement perceived as "fixing" bad photos (over-promising) | Hard product/UX constraint: honest before/after, explicit limitation copy, never generative infill |
| Cold-start personalization (new users get generic results) | Style-tag onboarding gives an immediate non-empty preference prior; diversity score prevents repetitive "safe" defaults |
| External API cost/rate limits (vision, enhancement, weather) | Caching, hosted-API-first with self-host upgrade path, circuit breakers and graceful fallbacks (Backend.md §8) |
| Privacy concerns around personal photos | Encryption, signed URLs, minimal retention, explicit consent, documented privacy policy |
| Feature creep overwhelming new users (a documented competitor weakness) | Progressive onboarding, MVP scope discipline (Section "Important Engineering Principles" in `Upgradation.md`) |

## Testing Strategy

- **Unit tests:** scoring functions (weather/occasion/color/style/personalization/diversity) tested in isolation with fixed inputs and known expected outputs; repository layer tested against a test DB.
- **Integration tests:** full upload pipeline (mocked AI clients) verifying DB rows land correctly end-to-end; recommendation endpoint tested against seeded wardrobes.
- **Frontend tests:** component tests (Vitest/React Testing Library) for critical flows (upload, recommendation display, feedback actions); Playwright/Cypress E2E for the core "sign up → upload → get recommendation" journey.
- **AI evaluation:** held-out labeled image set to track classification accuracy over time, specifically monitored after any model swap.

## Deployment Strategy

Docker containers for frontend and backend; GitHub Actions CI (lint → typecheck → test → build) gating merges to `main`; backend deployed to a managed container platform (Render/Fly.io/Railway for MVP, AWS ECS at scale); frontend deployed to Vercel; database migrations (Alembic) run as a deploy-time step with rollback support.

## Success Metrics

- **Activation:** % of new users who upload ≥3 items in their first session.
- **Engagement:** daily/weekly active users returning for outfit recommendations.
- **Trust signal:** % of recommendations where the user expands the "Why this outfit" breakdown (proxy for whether explainability is actually valued/used).
- **Personalization lift:** recommendation like-rate improvement over time per user (cold-start baseline vs. after N feedback events).
- **Classification quality:** % of AI-suggested attributes accepted without user correction (should trend upward as the fine-tuning flywheel matures).
- **Retention:** % of users still active at 30/90 days, and wardrobe growth rate per active user over time.

---

**Related documents:** `Skills.md` (technology decisions), `Design.md` (full UI/UX spec), `Backend.md` (architecture and pipelines), `Upgradation.md` (long-term evolution plan).
