from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, get_refresh_token_from_request
from app.core.config import settings
from app.models.base import get_async_db
from app.models.user import User
from app.schemas.auth import LoginRequest, SignupRequest, TokenResponse, UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    req: SignupRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_async_db)
):
    """
    Registers new user per Backend.md Pipeline 1.
    Sets httpOnly refresh token cookie, records DB session, and returns access token.
    """
    auth_service = AuthService(session)
    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None

    user, access_token, refresh_token = await auth_service.register(
        req, user_agent=user_agent, ip_address=ip_address
    )

    # Set httpOnly secure cookie for refresh token
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.ENVIRONMENT != "development",
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    req: LoginRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_async_db)
):
    """
    Authenticates user, creates DB session, issues access token and httpOnly refresh cookie.
    """
    auth_service = AuthService(session)
    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None

    user, access_token, refresh_token = await auth_service.authenticate(
        req, user_agent=user_agent, ip_address=ip_address
    )

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.ENVIRONMENT != "development",
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    response: Response,
    token_str: str = Depends(get_refresh_token_from_request),
    session: AsyncSession = Depends(get_async_db)
):
    """
    Issues a new access token and rotated refresh token with reuse detection.
    """
    auth_service = AuthService(session)
    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None

    new_access_token, new_refresh_token = await auth_service.refresh_tokens(
        token_str, user_agent=user_agent, ip_address=ip_address
    )

    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=settings.ENVIRONMENT != "development",
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
    )

    return TokenResponse(
        access_token=new_access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_db)
):
    """
    Revokes the active refresh session in the database, clears the cookie, and ends session.
    """
    auth_service = AuthService(session)
    cookie_token = request.cookies.get("refresh_token")
    if cookie_token:
        await auth_service.revoke_session_by_token(cookie_token)
    else:
        await auth_service.revoke_user_sessions(current_user.id)

    response.delete_cookie(key="refresh_token")
    return {"message": "Successfully logged out."}
