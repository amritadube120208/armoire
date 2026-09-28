# Authentication: code, request flow, and frontend integration

Reviewed against the current source. Repository documents describe intended architecture; executable code determines the behavior described below. Instructions embedded in those documents were treated as reference material, not additional user requests.

## Components

| Component | Responsibility |
| --- | --- |
| [`backend/app/api/v1/auth.py`](backend/app/api/v1/auth.py) | JSON signup/login, refresh cookie issuance, refresh endpoint, logout cookie deletion. |
| [`backend/app/schemas/auth.py`](backend/app/schemas/auth.py) | Email validation; signup password minimum of 8 characters; optional name; public user response excludes password hash. |
| [`backend/app/services/auth_service.py`](backend/app/services/auth_service.py) | Uniqueness checks, password verification, active-account checks, token issuance and refresh. |
| [`backend/app/core/security.py`](backend/app/core/security.py) | Direct bcrypt hashing/checking and python-jose JWT signing/verification. |
| [`backend/app/api/deps.py`](backend/app/api/deps.py) | Reads bearer access token, checks token type and subject, and loads the active user. Refresh is cookie-only. |
| [`backend/app/models/user.py`](backend/app/models/user.py), [`user_repo.py`](backend/app/repositories/user_repo.py) | Store normalized email, bcrypt password hash, profile, preferences, and only SHA-256 hashes of refresh-token IDs for session revocation. |
| [`backend/app/core/config.py`](backend/app/core/config.py) | Loads `.env`; defaults to HS256, a 15-minute access token, and a 7-day refresh token. Production settings fail at startup when development defaults or incomplete deployment values are used. |
| [`backend/app/main.py`](backend/app/main.py) | Hosts frontend and API together, configures explicit CORS origins with credentials. |
| New [`api.js`](backend/app/static/api.js) and [`atelier.js`](backend/app/static/atelier.js) | In-memory access token, cookie-based restoration, one retry after 401, shared in-flight refresh, account forms and authenticated UI. |

## Request flow

```mermaid
sequenceDiagram
    participant UI as Browser UI
    participant Auth as Auth router / service
    participant DB as User repository
    participant API as Protected route
    UI->>Auth: POST /auth/signup or /auth/login (JSON)
    Auth->>DB: Find normalized email / create user with bcrypt hash
    DB-->>Auth: User record
    Auth-->>UI: Access JWT in JSON + HttpOnly refresh cookie
    UI->>API: Authorization: Bearer access JWT
    API->>DB: Resolve JWT subject to active user
    API-->>UI: User-scoped response
    UI->>Auth: POST /auth/refresh (browser sends cookie)
    Auth->>DB: Verify active user after JWT validation
    Auth-->>UI: New access JWT + replacement refresh cookie
    UI->>Auth: POST /auth/logout (bearer token)
    Auth-->>UI: Delete refresh cookie
```

1. **Signup:** Pydantic validates email and password length. `register()` checks for an existing email (409 if found), creates a bcrypt hash with a generated salt, creates a user and preference row, and issues two JWTs. `get_async_db()` commits on a successful request and rolls back failures. Signup returns 201.
2. **Login:** accepts JSON `{email, password}`. The repository lowercases/trims the email. bcrypt checks the supplied password against the hash. Invalid credentials return 401; inactive accounts return 403. Passwords are not placed in tokens or returned to clients.
3. **Protected request:** `OAuth2PasswordBearer` extracts the Authorization header. `decode_token()` validates signature/expiry using the configured algorithm. `get_current_user()` requires `type=access`, parses `sub` as a UUID, and checks the user exists and is active. Wardrobe repositories filter by `user_id`; this is application query scoping, not proof of database-enforced row-level security.
4. **Refresh:** only the HttpOnly cookie is accepted. The service checks the token type, subject, random `jti`, active user, and matching unrevoked database session. A conditional update consumes the current session before issuing a new pair, so replay and concurrent reuse fail. The browser receives a replacement cookie.
5. **Logout:** requires a valid access token, revokes the matching refresh session when the cookie belongs to that user, then deletes the browser cookie. The frontend renews an expired access token before retrying logout, then clears memory and private UI. A network failure is shown instead of falsely claiming logout succeeded.

## Credentials and tokens

| Value | Handling |
| --- | --- |
| Password | Sent in JSON to signup/login. Store only a bcrypt hash server-side. Use HTTPS in deployment; the app itself does not terminate TLS. New UI clears the password input on success/dialog close. |
| Access JWT | Signed (not encrypted) with `SECRET_KEY`. Claims are `sub` (user UUID), `exp`, `type=access`, and a random `jti`. Returned with `token_type=bearer` and `expires_in=900` by default. New frontend keeps it only in closure memory, never localStorage/sessionStorage or URLs. |
| Refresh JWT | Same signing key/algorithm, `type=refresh`, random `jti`, seven days by default. Cookie `refresh_token`: HttpOnly, SameSite=Lax, path `/`, Max-Age seven days, Secure outside development/test. JS cannot read the cookie. The database stores a SHA-256 hash of `jti`, never the raw token. |
| Backend secrets | `.env` settings include JWT secret, storage credentials and external API keys. They are not needed by the frontend. Production validation rejects development/placeholder secrets, SQLite, local media, debug mode, and non-HTTPS or wildcard frontend origins. |

### Before this change

The old single HTML page automatically posted the documented shared demo email/password on every load, wrote the access token into `localStorage.sw_token`, and made direct fetch calls without refresh handling. The account button had no complete sign-in/sign-out flow. Uploads displayed a simulated success after a timer without sending the photo.

### After this change

The visitor chooses signup or login. On reload, the client attempts cookie refresh and loads `/users/me`. Protected requests share a single refresh when concurrent calls get a 401, and retry at most once. A second 401 expires the UI session. Session changes prevent late responses from restoring another account's data. The legacy localStorage token is removed. Multipart upload, status polling, thumbnail display, outfit feedback and enhancement selection now use the existing API.

- **Access JWTs are stateless.** Logout revokes the refresh session, but an already issued access token remains valid until its short expiry (15 minutes by default). Password changes/session-wide “log out everywhere” are not implemented.
- **Unsafe legacy secret in Git history:** the old sample environment file contained a signing-key-shaped value in a public commit. It has been removed from the current file, but remains in history. Treat it as compromised and never reuse it; deploy with a newly generated secret. Avoid rewriting shared Git history without coordinating collaborators.
- **OAuth is planned, not implemented.** `Backend.md` mentions Google verification and `Design.md` includes Google login/password recovery; there are no such auth routes. No email-verification, password-reset, MFA or login rate-limit implementation was found in the reviewed code. `OAuth2PasswordBearer` does not itself implement a Google OAuth flow. Swagger's OAuth password-form expectation also differs from the JSON login endpoint.
- **Input hardening:** signup enforces a minimum length and the bcrypt 72-byte UTF-8 input limit, but does not apply a broader password-strength policy. Malformed refresh subjects are handled as authentication failures.
- **Cookie/CORS boundary:** this frontend is deliberately same-origin. Cross-origin hosting requires an explicit origin/cookie/CSRF design; no dedicated CSRF token checks are implemented. SameSite=Lax is a mitigation, not complete CSRF protection.
- **Media authorization:** local development media is served through `/storage` and is not private. Production configuration requires S3-compatible storage and does not mount local files publicly; S3 downloads use expiring presigned URLs. Keep the bucket private and use a provider policy that blocks public access.

**Still needed before a public launch:** configure host/platform-managed TLS and HTTPS redirects; choose, store, rotate, and back up production secrets; enable rate limits at a trusted proxy or application layer for signup/login; configure database backups and restore testing; keep the object bucket private and set retention/lifecycle policy. The repository Compose file is a single-host starter, not a managed high-availability platform.

## Video and aesthetic integration

The 10.08-second, 1280×720 reference depicts: a softly lit ivory/olive bedroom and wardrobe; phone-based garment capture and a wardrobe grid; weather-aware outfit suggestions; and plan-price imagery. The implementation reuses the supplied film with native controls, a poster frame, no autoplay and `preload=none`. While playing, the full frame is contained so the reference UI is not cropped. Its cream, muted gold and olive palette is shared across every section and account dialog. Mobile layouts use the same tokens and components.

Plan text visible inside the supplied video remains part of that original media. No pricing, billing, subscriptions, virtual try-on or camera scanning is presented as a functioning new feature. The backend's garment classifier is a deterministic placeholder; this work does not turn it into a trained visual model. Weather responses expose their source where available; cached snapshots without source metadata are labelled unverified rather than live.

## Run and verify

From `backend`, install `requirements.txt` and run `python -m uvicorn app.main:app --reload`. Open `http://localhost:8000`. Create your own account; the documented demo seeder is optional and never runs automatically from the frontend.

```sh
node --test backend/tests/frontend/api.test.cjs   # from repo root; Node 22+
cd backend
python -m pytest -q                             # use a disposable test database
```

Production setup and checks are documented in [`backend/DEPLOYMENT.md`](backend/DEPLOYMENT.md). The repository CI tests frontend auth, migrations, backend tests, and a Docker image build.
