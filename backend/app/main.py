from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.api.v1 import api_v1_router
from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.models.base import Base, async_engine

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Initializing Smart Wardrobe backend... [env={settings.ENVIRONMENT}]")
    # Ensure local storage directory exists if using local backend
    if settings.STORAGE_BACKEND == "local":
        Path(settings.STORAGE_LOCAL_DIR).mkdir(parents=True, exist_ok=True)

    # Initialize tables if using SQLite for dev/test mode
    if "sqlite" in settings.DATABASE_URL:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("SQLite database tables verified/created.")

    yield
    logger.info("Shutting down Smart Wardrobe backend...")
    await async_engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount local media storage in local development
if settings.STORAGE_BACKEND == "local":
    local_storage_path = Path(settings.STORAGE_LOCAL_DIR)
    local_storage_path.mkdir(parents=True, exist_ok=True)
    app.mount("/storage", StaticFiles(directory=str(local_storage_path)), name="storage")
elif settings.STORAGE_BACKEND == "vercel_blob":
    from app.api.media import router as private_media_router
    app.include_router(private_media_router)


# Mount static frontend assets
static_path = Path(__file__).resolve().parent / "static"
static_path.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


# Consistent Error Envelope Handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "data": None,
            "error": {
                "code": exc.status_code,
                "message": exc.detail
            }
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "data": None,
            "error": {
                "code": 422,
                "message": "Validation Error",
                "details": jsonable_encoder(exc.errors())
            }
        }
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "data": None,
            "error": {
                "code": 500,
                "message": "Internal Server Error"
            }
        }
    )



@app.get("/", include_in_schema=False)
async def root():
    """Serve Augustine luxury frontend lookbook UI directly at root."""
    index_file = Path(__file__).resolve().parent / "static" / "index.html"
    if index_file.exists():
        if settings.STORAGE_BACKEND == "vercel_blob":
            html = index_file.read_text(encoding="utf-8")
            html = html.replace("</head>", '<meta name="upload-max-bytes" content="3800000"></head>')
            return HTMLResponse(html, headers={"Cache-Control": "no-store"})
        return FileResponse(str(index_file))
    return RedirectResponse(url="/api/v1/docs")


# Health check endpoints
@app.get("/health", tags=["Health"])
async def root_health():
    """Base application health check."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT
    }


@app.get(f"{settings.API_V1_STR}/health", tags=["Health"])
async def api_v1_health():
    """API v1 health check."""
    return {
        "status": "healthy",
        "version": "v1",
        "service": settings.PROJECT_NAME
    }


# Include API v1 router
app.include_router(api_v1_router, prefix=settings.API_V1_STR)
