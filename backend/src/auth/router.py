from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.auth.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserResponse,
)
from src.auth.service import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from src.common.database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account deactivated")

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    is_prod = settings.environment == "production"
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=is_prod,
        max_age=60 * 15,  # 15 minutes
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="lax",
        secure=is_prod,
        max_age=60 * 60 * 24 * 7,  # 7 days
    )

    return TokenResponse(access_token=access_token, name=user.name)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")

    payload = decode_token(token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    import uuid

    user_id = uuid.UUID(payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id, User.is_active == True))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    access_token = create_access_token(user.id)

    is_prod = settings.environment == "production"
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=is_prod,
        max_age=60 * 15,
    )

    return TokenResponse(access_token=access_token)


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"message": "Logged out"}


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_profile(
    data: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if data.name is not None:
        current_user.name = data.name
    if data.avatar_url is not None:
        current_user.avatar_url = data.avatar_url
    db.add(current_user)
    return current_user


@router.post("/change-password")
async def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    current_user.password_hash = hash_password(data.new_password)
    db.add(current_user)
    return {"message": "Password changed successfully"}
