# Skills.md — Smart Wardrobe & AI Recommendation System
### Technology Stack & Skills Document

> **Strategic Instruction (applies throughout):**
> "CHECK ALL EXISTING IDEAS OF THIS SOLUTION AND THEN MAKE MINE BETTER THAN THEM IN EVERY ASPECT."

---

## 0. Why This Stack — Grounded in Competitive Reality

Before choosing technology, here is what the current market (Whering, Acloset, Alta, Stylebook, Cladwell, GetWardrobe) actually does well and poorly, because the stack has to serve the gaps, not just the features:

| Existing product | Does well | Does poorly / limitation |
|---|---|---|
| Whering | Background removal, cost-per-wear analytics, social feed | Auto-tagging glitches reported; feature bloat overwhelms new users; resale features UK-only |
| Acloset | Fast AI tagging, weather+calendar suggestions, background removal | Recommendation logic is mostly a black box to the user (no "why") |
| Alta | Fast setup, "Prettify" image upscaling, adaptive styling from feedback | Free-tier virtual try-on capped by credits; styling engine not transparent; English-only |
| Stylebook | Simple, no-fuss manual wardrobe | No real AI recommendation — mostly manual planning |
| Cladwell | Capsule-wardrobe audits, ChatGPT-based "Ask Cladwell" | Paid; capsule focus limits everyday flexibility |
| GetWardrobe | Combination swipe UI, drag-drop outfit editor, packing lists | AI Studio and calendar sync are differentiators few others have |

**Pattern across all of them:** recommendation logic is opaque ("black box AI"), image enhancement is either absent or unexplained, and almost none show a *confidence score* or *reasoning* for why an outfit was suggested. Our stack is chosen specifically to make the pipeline **explainable, modular, and upgradeable** rather than a single opaque model call — that is our core technical differentiator, and it shapes every stack choice below.

---

## 1. Frontend

### Options considered
| Option | Pros | Cons |
|---|---|---|
| React (CRA/Vite) | Flexible, huge ecosystem | No built-in SSR, more manual setup |
| **Next.js (App Router) + TypeScript** | SSR/SSG, image optimization, API routes for BFF calls, file-based routing, great DX, strong deployment story (Vercel or self-hosted) | Slightly more opinionated |
| Vue/Nuxt | Simpler learning curve | Smaller ecosystem for fashion/e-commerce style UI kits |
| Flutter (cross-platform mobile) | Single codebase for iOS/Android | Wardrobe apps are increasingly used on mobile browsers too; team velocity for hackathon/MVP favors web-first |

### Chosen primary stack
- **Next.js 15 (App Router) + TypeScript** — image-heavy app benefits from `next/image` automatic optimization/lazy-loading (critical: every clothing photo, thumbnail, and enhanced image needs this), plus server components reduce client bundle size for a media-heavy UI.
- **Tailwind CSS** — enables the fast, consistent "premium minimal" design system defined in `Design.md` without fighting a component library's defaults.
- **shadcn/ui (Radix primitives)** — accessible, unstyled base components (dialogs, dropdowns, tabs, sliders) that we skin with Tailwind, instead of a heavy opinionated kit like MUI that fights fashion-app aesthetics.
- **State management:** **Zustand** for lightweight global UI state (active wardrobe filters, upload queue, selected occasion) + **TanStack Query (React Query)** for all server state (wardrobe items, recommendations, weather) — this separation avoids the classic mistake of stuffing server data into Redux/Zustand and fighting cache invalidation.
- **Forms:** React Hook Form + Zod for validated onboarding/preferences forms.
- **API integration:** typed REST client generated from the backend's OpenAPI schema (FastAPI auto-generates this), so frontend/backend contracts never silently drift.
- **Image handling on client:** `browser-image-compression` before upload (reduces bandwidth + speeds up the backend quality-check pipeline).
- **Mobile:** ship as a responsive PWA first (installable, offline-tolerant for viewing an already-loaded wardrobe); a native Flutter/React Native shell is a Phase-3+ item in `Upgradation.md`, not MVP scope.

**Why this over Whering/Acloset's native-only approach:** every competitor above is app-store first. A responsive PWA lets us ship one codebase to web + "installed" mobile immediately, which is both faster to build and removes the app-store approval bottleneck for an MVP/hackathon timeline.

---

## 2. Backend

### Options considered
| Option | Verdict |
|---|---|
| Node.js (Express/Nest) | Good for I/O-bound APIs, but AI/ML tooling (PyTorch, OpenCV, embeddings, classification models) lives natively in Python — using Node here means constant subprocess bridging. |
| Django | Batteries-included but heavier, ORM less flexible for the vector/async workloads we need. |
| **Python + FastAPI** | Native access to the entire CV/ML ecosystem, async-first, automatic OpenAPI docs (feeds the typed frontend client above), Pydantic validation matches our need for strict schemas around AI outputs (category, confidence, attributes). |

### Chosen: **Python 3.12 + FastAPI**
- **REST APIs:** FastAPI routers per domain (auth, wardrobe, images, recommendations, weather, feedback) — full structure in `Backend.md`.
- **Authentication:** OAuth2 password flow + JWT access/refresh tokens via `fastapi-users` or a custom implementation on top of `passlib` (bcrypt) — plus optional Google/Apple OAuth for low-friction signup (fashion apps live and die by onboarding friction).
- **File upload:** `python-multipart` for multipart form uploads, streamed directly to object storage (never held fully in memory for large images).
- **Image processing:** Pillow (basic ops), OpenCV (blur/quality metrics), and a dedicated enhancement model (Section 3).
- **Background/async jobs:** **Celery + Redis** (or lighter-weight **FastAPI BackgroundTasks** for MVP, upgrading to Celery once enhancement/classification volume grows — see `Upgradation.md`).
- **Recommendation APIs:** a dedicated `recommendations` service module — deterministic scoring engine described fully in `Backend.md`, callable via REST and designed to later be swapped for an ML ranker without changing the API contract.
- **Database APIs:** SQLAlchemy 2.0 (async) ORM + Alembic migrations.

---

## 3. AI / ML

This is the section where "use AI to recommend clothes" (explicitly forbidden by the brief) gets replaced with a precise map of **what is actually a model call vs. what is deterministic logic.**

| Capability | AI/ML or Deterministic? | Approach |
|---|---|---|
| Clothing detection (find garment in photo) | **AI (CV)** | Object detection model (e.g., YOLOv8-seg or a fashion-tuned detector) to localize + segment the garment from background/body. |
| Category classification (top/bottom/dress/shoe/...) | **AI (CV)** | Fine-tuned image classifier (start with an API like Google Vision / AWS Rekognition custom labels, or a fine-tuned CLIP/ViT model on a fashion dataset such as DeepFashion2) |
| Color extraction | **Deterministic** | K-means clustering on segmented pixels (post-background-removal) — far more reliable and cheap than asking a model "what color is this." |
| Pattern detection (solid/striped/floral/plaid) | **AI (CV), lower confidence tier** | Lightweight secondary classifier; always exposed with a confidence score, user can correct. |
| Material/style estimation | **AI, but treated as a *suggestion* not a fact** | LLM-assisted tagging from the image + category (e.g., a vision-LLM call), explicitly labeled "estimated" in the UI — never presented as certain, since this is the hardest attribute to get right and the #1 place competitors silently guess wrong. |
| Image quality / blur scoring | **Deterministic** | Laplacian variance (OpenCV) for blur, resolution checks, brightness histogram — no ML needed, and it must run *before* any AI enhancement decision. |
| Image enhancement (deblur/upscale) | **AI (generative, bounded)** | Off-the-shelf super-resolution / deblur model (Real-ESRGAN class), explicitly **not** allowed to invent new garment details — enhancement is sharpening/upscaling only, never generative infill of unseen regions (see `Design.md` and `Backend.md` Pipeline 3 for the guardrails). |
| Background removal | **AI (CV)** | Pretrained segmentation model (e.g., `rembg`/U²-Net) — table-stakes feature every competitor already has; we must match it, not "beat" it. |
| Embeddings for similarity / style matching | **AI** | CLIP-style multimodal embedding per clothing item, stored in a vector DB, used for "outfits similar to X" and duplicate-item detection. |
| Weather-aware recommendation | **Deterministic rule engine** | Explicit temperature/precipitation → clothing-requirement mapping (Backend.md Pipeline 5) — this must be deterministic and explainable, not an opaque model, because users need to trust "why is it suggesting a coat." |
| Occasion-aware recommendation | **Deterministic rule engine + AI-assisted tagging** | Dress-code rule tables per occasion; AI only assists in tagging formality level of an item at ingestion time. |
| Personalization / learning from feedback | **AI (progressively)** | Starts as simple weighted-preference updates (deterministic, MVP) → evolves into a learned ranking model (logistic regression → gradient-boosted ranker → optionally a lightweight neural ranker) once enough feedback data exists — explicit upgrade path in `Upgradation.md`. |
| Natural-language "AI stylist chat" | **LLM (Phase 3+, not MVP)** | Optional layer on top of the deterministic engine — the LLM explains/adjusts recommendations, it does not generate them from scratch (avoids hallucinated "wear clothes you don't own"). |

**Key principle carried into `Backend.md`:** every AI output that feeds a downstream decision (category, color, quality score, formality) is stored with a **confidence score**, and the recommendation engine treats low-confidence attributes conservatively (e.g., excludes an item from a "formal" outfit if formality-confidence is below threshold, rather than guessing).

---

## 4. Database

| Data type | Store | Why |
|---|---|---|
| Users, sessions, preferences, feedback, outfit history, structured clothing metadata (category, color, brand, size) | **PostgreSQL** | Relational integrity between User ↔ Wardrobe ↔ Outfit ↔ Feedback; strong support for JSONB (flexible attribute bags) + full-text search for wardrobe search. |
| Clothing/outfit embeddings for similarity search | **Vector DB** — start with `pgvector` extension inside the same Postgres instance (zero extra infra for MVP); graduate to a dedicated vector store (Pinecone/Weaviate/Qdrant) at scale (`Upgradation.md` Level 3). |
| Original photos, enhanced photos, thumbnails | **Object storage** (S3-compatible: AWS S3 / Cloudflare R2 / Supabase Storage) — never in the relational DB; DB stores only URLs/keys + metadata. |
| Ephemeral session/cache data, job queues | **Redis** | Celery broker, rate-limit counters, weather-cache (avoid hammering the weather API per request). |

We reject MongoDB for the core model: clothing/outfit/user relationships are inherently relational (foreign keys, joins for "outfits containing item X"), and Postgres's JSONB columns already give us the flexible-attribute benefit people usually reach for Mongo for.

---

## 5. External APIs

| Need | Options | Choice for MVP |
|---|---|---|
| Weather | OpenWeatherMap, Tomorrow.io, WeatherAPI.com | **OpenWeatherMap** (generous free tier, includes "feels-like," humidity, precipitation probability — all required by Pipeline 5) |
| Image quality / enhancement | Self-hosted Real-ESRGAN vs. Replicate/HuggingFace Inference API | Start with a **hosted inference API** (Replicate) for MVP speed, self-host once volume justifies GPU cost (`Upgradation.md`) |
| Vision/classification model hosting | Self-hosted vs. Google Vision / AWS Rekognition Custom Labels / HuggingFace Inference Endpoints | Start with a **hosted API + fine-tuned HF model endpoint**; self-host later |
| Auth | Auth0 / Clerk / Firebase Auth / custom FastAPI+JWT | **Custom FastAPI + JWT** for MVP (no vendor lock-in, full control over user data — see Security section on why this matters for photo-of-your-body-adjacent data), OAuth (Google) as an add-on |
| Cloud storage | AWS S3, Cloudflare R2, Supabase Storage | **Cloudflare R2** (S3-compatible API, no egress fees — significant for an image-heavy app) or AWS S3 if the team is already in AWS |
| LLM (Phase 3 stylist chat, attribute assist) | Anthropic Claude API, OpenAI API | Provider-agnostic wrapper interface so either can be swapped in |

---

## 6. DevOps

- **Version control:** Git + GitHub, trunk-based development with short-lived feature branches, PR review required on `main`.
- **Environment variables:** `.env` (local, gitignored) + `.env.example` committed; secrets in production via the hosting platform's secret manager (never in the repo).
- **Containerization:** Docker for both frontend and backend; `docker-compose.yml` for local dev (Postgres + Redis + backend + frontend in one command).
- **CI/CD:** GitHub Actions — lint (ruff/eslint) → type-check (mypy/tsc) → test (pytest/vitest) → build → deploy on merge to `main`.
- **Deployment:** Backend on Render/Fly.io/Railway (simple container deploy) or AWS ECS at scale; frontend on Vercel (native Next.js support).
- **Monitoring:** Sentry (error tracking, both frontend and backend), Prometheus + Grafana or a hosted equivalent (e.g., Better Stack) for API latency/queue depth once background jobs are added.
- **Logging:** structured JSON logs (`structlog` in FastAPI), centralized via the hosting platform's log drain or Logtail.

---

## 7. Security

- **Authentication:** JWT access tokens (short-lived, ~15 min) + refresh tokens (httpOnly, secure cookies) — never store tokens in `localStorage` (XSS exposure).
- **Authorization:** every wardrobe/clothing/outfit resource is scoped by `user_id`; row-level ownership checks on every query, not just at the route level.
- **Image upload security:** strict MIME-type + magic-byte validation (not just file extension), file-size caps, re-encoding uploaded images server-side (strips EXIF/GPS metadata and neutralizes any embedded exploit payloads) before storage.
- **API security:** rate limiting (per-user and per-IP) on upload and recommendation endpoints, input validation via Pydantic schemas on every route, CORS locked to known frontend origins.
- **User privacy:** clothing photos are sensitive personal data (can reveal body size/shape, home interior, location via background) — encrypt at rest (S3/R2 server-side encryption), signed/expiring URLs for private image access (never public buckets), explicit user consent flow for any feature that would use photos beyond the stated purpose.
- **Data protection & retention:** account deletion cascades to all images (object storage + DB), minimal-retention policy (temp/failed-upload files purged on a schedule), documented in a privacy policy (`Master.md` references this).

---

## 8. Skills Required

### Beginner
- HTML/CSS/Tailwind basics
- React fundamentals (components, props, state)
- Basic REST API concepts (GET/POST/PUT/DELETE)
- Git basics (clone, commit, branch, PR)
- Reading/writing JSON

### Intermediate
- TypeScript (types, generics for API client)
- Next.js App Router (routing, server/client components, data fetching)
- FastAPI (routers, dependency injection, Pydantic schemas)
- SQLAlchemy ORM + relational schema design
- Working with pretrained CV models via an API (not training your own)
- Docker basics (Dockerfile, docker-compose)
- Authentication flows (JWT, OAuth)

### Advanced
- Fine-tuning a vision classifier (or curating training data for one)
- Vector embeddings + similarity search tuning (pgvector indexing, HNSW/IVFFlat parameters)
- Designing and tuning a multi-factor recommendation scoring function
- Background job orchestration at scale (Celery concurrency, queue design)
- Transitioning a rule-based system to a learned ranking model (feature engineering from user feedback)
- Production ML ops: model versioning, A/B testing recommendation changes, monitoring model drift

### What to use existing APIs/models for (don't build from scratch)
- Background removal (`rembg` / hosted API)
- Base object detection/segmentation (pretrained YOLO/SAM checkpoints)
- Image super-resolution/deblur (pretrained Real-ESRGAN class model via hosted inference)
- Weather data (OpenWeatherMap)
- Base classification backbone (fine-tune a pretrained ViT/CLIP rather than training from scratch)

### What is worth building custom (this is where differentiation lives)
- The deterministic, explainable recommendation scoring engine (`Backend.md` Pipeline 7)
- The confidence-aware attribute pipeline (never trusting a single model blindly)
- The feedback → personalization loop
- The image-enhancement guardrails (when to enhance, when to refuse, how to show the user what changed)

---

**Next document:** see `Design.md` for the full UI/UX specification built on top of this stack.
