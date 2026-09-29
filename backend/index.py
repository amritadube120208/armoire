"""Vercel FastAPI entrypoint. Persistent services are configured by Vercel env."""

import os

os.environ.setdefault("ENVIRONMENT", "production")
os.environ.setdefault("DEBUG", "false")
os.environ.setdefault("STORAGE_BACKEND", "vercel_blob")
os.environ.setdefault("STORAGE_LOCAL_DIR", "/tmp/armoire-storage")

if not os.environ.get("SECRET_KEY"):
    raise RuntimeError("Configure SECRET_KEY in the Vercel project environment before deployment.")

from app.main import app  # noqa: E402
