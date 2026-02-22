import hmac

from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from fastapi.responses import RedirectResponse
from jose import jwt as jose_jwt, JWTError, ExpiredSignatureError
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.auth.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    SyncPasswordRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserResponse,
)
from src.auth.service import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    sync_password_to_supabase,
    verify_password,
)
from src.common.config import settings
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

    # Sync to Supabase Auth (best-effort)
    await sync_password_to_supabase(current_user.email, data.new_password)

    return {"message": "Password changed successfully"}


@router.post("/sync-password")
async def sync_password_from_eva(
    data: SyncPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Internal endpoint: EvaAI calls this when a super_admin changes their
    password on app.goeva.ai so the ERP stays in sync."""
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer ") or not settings.erp_sso_secret:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unauthorized")

    token = auth.removeprefix("Bearer ")
    if not hmac.compare_digest(token, settings.erp_sso_secret):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unauthorized")

    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    user.password_hash = hash_password(data.new_password)
    db.add(user)
    return {"message": "Password synced"}


@router.get("/sso")
async def sso_login(
    token: str,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Validate a single-use SSO token from EvaAI and create an ERP session."""
    if not settings.erp_sso_secret:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "SSO not configured")

    # 1. Decode and validate JWT
    try:
        payload = jose_jwt.decode(
            token,
            settings.erp_sso_secret,
            algorithms=["HS256"],
            audience="erp-sso",
            options={"require_sub": True, "require_jti": True},
        )
    except ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "SSO token expired")
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid SSO token")

    # Validate issuer
    if payload.get("iss") != "eva-ai":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid SSO token")

    # 2. Enforce single-use via consumed_sso_tokens
    jti = payload.get("jti")
    if not jti:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid SSO token")

    result = await db.execute(
        text(
            "INSERT INTO consumed_sso_tokens (jti, consumed_at) "
            "VALUES (:jti, NOW()) "
            "ON CONFLICT (jti) DO NOTHING "
            "RETURNING jti"
        ),
        {"jti": jti},
    )
    if result.rowcount == 0:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "SSO token already used")

    # 3. Find the ERP user by email
    email = payload.get("sub")
    user_result = await db.execute(select(User).where(User.email == email))
    user = user_result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No active ERP account for this email")

    # 4. Create ERP session
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    is_prod = settings.environment == "production"
    response = RedirectResponse(url="/dashboard", status_code=307)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=is_prod,
        max_age=60 * 15,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="lax",
        secure=is_prod,
        max_age=60 * 60 * 24 * 7,
    )
    # Short-lived cookie for the welcome animation (readable by JS)
    response.set_cookie(
        key="welcome_name",
        value=user.name or "",
        httponly=False,
        samesite="lax",
        secure=is_prod,
        max_age=30,
    )

    await db.commit()
    return response
