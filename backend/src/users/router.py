import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import require_admin
from src.auth.models import User
from src.auth.schemas import UserResponse
from src.auth.service import hash_password
from src.common.database import get_db
from src.users.schemas import InviteUserRequest, UpdateUserRequest

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserResponse])
async def list_users(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).order_by(User.created_at))
    return result.scalars().all()


@router.post("/invite", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def invite_user(
    data: InviteUserRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    # Check if email already exists
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    # Generate temporary password
    temp_password = secrets.token_urlsafe(12)

    user = User(
        email=data.email,
        name=data.name,
        password_hash=hash_password(temp_password),
        role=data.role,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    # In a real app you'd email this. For now just return it.
    # The frontend should show the temp password to the admin.
    return user


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    data: UpdateUserRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if data.role is not None:
        user.role = data.role
    if data.is_active is not None:
        user.is_active = data.is_active

    db.add(user)
    return user


@router.delete("/{user_id}")
async def deactivate_user(
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.id == admin.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate yourself")

    user.is_active = False
    db.add(user)
    return {"message": f"User {user.name} deactivated"}
