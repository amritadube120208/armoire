from typing import Optional
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.core.config import settings
from app.models.base import get_async_db
from app.models.user import User
from app.schemas.auth import LoginRequest, SignupRequest, TokenResponse, UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="refresh_token", value=token, httponly=True,
        secure=settings.ENVIRONMENT not in {"development", "test"},
        samesite="lax", path="/",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key="refresh_token", path="/",
        secure=settings.ENVIRONMENT not in {"development", "test"},
        httponly=True, samesite="lax",
    )


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    req: SignupRequest,
    response: Response,
    session: AsyncSession = Depends(get_async_db)
):
    """
    Registers new user per Backend.md Pipeline 1.
    Sets httpOnly refresh token cookie and returns access token.
    """
    auth_service = AuthService(session)
    user, access_token, refresh_token = await auth_service.register(req)

    _set_refresh_cookie(response, refresh_token)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    req: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_async_db)
):
    """
    Authenticates user, issues access token and httpOnly refresh cookie.
    """
    auth_service = AuthService(session)
    user, access_token, refresh_token = await auth_service.authenticate(req)

    _set_refresh_cookie(response, refresh_token)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    response: Response,
    token_str: Optional[str] = Cookie(None, alias="refresh_token"),
    session: AsyncSession = Depends(get_async_db)
):
    """
    Issues a new access token and rotated refresh token using the httpOnly cookie.
    """
    if not token_str:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh cookie is missing.")
    auth_service = AuthService(session)
    try:
        new_access_token, new_refresh_token = await auth_service.refresh_tokens(token_str)
    except HTTPException:
        _clear_refresh_cookie(response)
        raise
    _set_refresh_cookie(response, new_refresh_token)

    return TokenResponse(
        access_token=new_access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    response: Response,
    current_user: User = Depends(get_current_user),
    refresh_token: Optional[str] = Cookie(None, alias="refresh_token"),
    session: AsyncSession = Depends(get_async_db),
):
    """
    Clears refresh token cookie and ends session.
    """
    await AuthService(session).revoke_refresh_token(refresh_token, current_user.id)
    _clear_refresh_cookie(response)
    return {"message": "Successfully logged out."}
