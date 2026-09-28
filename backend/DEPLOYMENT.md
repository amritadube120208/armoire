# Deployment guide

This repository includes a single-host Docker Compose production starter. It runs FastAPI, a Celery worker, PostgreSQL with pgvector, and Redis. Place it behind a trusted HTTPS reverse proxy or load balancer. The Compose file binds the API to `127.0.0.1` by default and does not publish the database or Redis ports.

For high availability, use managed PostgreSQL/Redis/object storage and a container platform with health-based restarts and rolling releases. Compose is not a multi-host scheduler or a substitute for backups, TLS, monitoring, and incident response.

## Before deployment

You need a Linux Docker host, a domain name, a TLS-terminating reverse proxy, a PostgreSQL-compatible database if not using the included container, a private S3-compatible bucket, and an OpenWeather API key. Configure the proxy to forward HTTPS traffic to the API's local port. Preserve the original `Host` and forwarded protocol headers; restrict access to that port to the local proxy.

Use a password manager or hosting platform's secret manager for production secrets. Do not put a real `.env` file in Git or in a public image.

## Start the Compose production profile

From `backend/`, make a private copy of the template and edit every `REPLACE_...` value. Set the CORS origin to the exact public frontend origin, without a path. The example S3 endpoint is for illustration and must be replaced by the provider's HTTPS endpoint; for AWS S3, leave `S3_ENDPOINT_URL` empty and set the correct AWS region. Database passwords embedded in URLs must be URL-encoded.

```sh
cp .env.production.example .env
# Edit .env with your actual domain, generated secrets, database and storage settings.
docker compose -f docker-compose.prod.yml config
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
```

The API and worker containers reject incomplete production settings at startup. The API runs Alembic migrations before starting Uvicorn, with debug documentation and the public local-media mount disabled. The host port defaults to `127.0.0.1:8000`; set `APP_PORT` if your proxy uses a different local port. Increase `WEB_CONCURRENCY` only after sizing the host and database connection pool.

Check `https://your-domain/health` through the proxy. The health endpoint is a process check, not a full database, Redis, storage, or external-provider readiness check. Monitor those dependencies independently.

## Data, storage and secrets

- Persist and back up the PostgreSQL volume or use managed PostgreSQL. Test restoration before relying on backups. The included Compose database uses the pgvector image.
- Redis is configured with append-only persistence but is used as a cache and task broker; do not treat it as the durable source of user data.
- Keep the S3 bucket private, block public access, enable provider-side encryption, and define a lifecycle policy. The API returns expiring presigned download URLs. Give the app only the object permissions it needs.
- Keep `.env` private and rotate it through the host's secret-management process. Use a newly generated `SECRET_KEY` of at least 32 bytes; never use a value from Git history. A key rotation invalidates existing JWTs.
- Restrict `BACKEND_CORS_ORIGINS` to the exact HTTPS site origin. Browser refresh cookies are `HttpOnly`, `Secure`, and `SameSite=Lax` in production. Keep the UI and API same-origin when possible.
- Provide an OpenWeather key for live recommendations. Without external credentials or service connectivity, related live functionality may be unavailable.
- Add login/signup rate limiting at a trusted edge or application layer before exposing the service broadly. The repository does not currently implement account throttling, password reset, MFA, or email verification.

## Upgrades and rollback

Back up PostgreSQL before deploying a new revision. Review the Alembic migration, deploy the image, and verify the migration and health checks. The initial refresh-session migration makes existing refresh cookies that have no persisted session fail; users will need to sign in again after this upgrade. Rolling back the application image does not automatically reverse database migrations. Only downgrade after reviewing that migration's data impact.

## GitHub checks

The `Backend CI` workflow runs the JavaScript auth-client tests, Python migrations, backend tests, demo-seed check, and Docker image build on every push and on pull requests targeting `main`, `master`, or `develop`. Configure GitHub branch protection to require these checks before merge. This repository does not publish images or deploy automatically; configure those steps and protected deployment secrets in the hosting platform when desired.
