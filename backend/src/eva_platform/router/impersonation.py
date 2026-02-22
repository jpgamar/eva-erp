"""Impersonation: generate magic link for Eva account owners."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, String
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.common.database import get_eva_db
from src.eva_platform.models import EvaAccount, EvaAccountUser
from src.eva_platform.schemas import ImpersonationResponse
from src.eva_platform.supabase_client import SupabaseAdminClient, SupabaseAdminError

router = APIRouter()


@router.post("/impersonate/account/{account_id}", response_model=ImpersonationResponse)
async def impersonate_account(
    account_id: uuid.UUID,
    eva_db: AsyncSession = Depends(get_eva_db),
    user: User = Depends(get_current_user),
):
    """Generate a magic link to impersonate an account owner."""
    # Find account
    result = await eva_db.execute(select(EvaAccount).where(EvaAccount.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Find owner user — try both case variants for the role
    result = await eva_db.execute(
        select(EvaAccountUser).where(
            EvaAccountUser.account_id == account_id,
            EvaAccountUser.role.cast(String).in_(["OWNER", "owner"]),
        )
    )
    owner = result.scalar_one_or_none()

    # Fallback: look up by account.owner_user_id
    if not owner and account.owner_user_id:
        result = await eva_db.execute(
            select(EvaAccountUser).where(
                EvaAccountUser.account_id == account_id,
                EvaAccountUser.user_id == account.owner_user_id,
            )
        )
        owner = result.scalar_one_or_none()

    # Last resort: pick the first user on this account
    if not owner:
        result = await eva_db.execute(
            select(EvaAccountUser).where(
                EvaAccountUser.account_id == account_id,
            ).limit(1)
        )
        owner = result.scalar_one_or_none()

    if not owner:
        raise HTTPException(status_code=404, detail="No users found for this account")

    # Generate magic link
    try:
        magic_link = await SupabaseAdminClient.admin_generate_link(
            email=owner.email,
            link_type="magiclink",
        )
    except SupabaseAdminError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not magic_link:
        raise HTTPException(status_code=500, detail="Failed to generate magic link")

    return ImpersonationResponse(
        magic_link_url=magic_link,
        account_id=account.id,
        account_name=account.name,
    )
