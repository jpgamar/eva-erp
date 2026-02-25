"""Impersonation: generate magic link for Eva account owners."""

import uuid
from typing import Iterable

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.common.database import get_eva_db
from src.eva_platform.models import EvaAccount, EvaAccountUser
from src.eva_platform.schemas import ImpersonationResponse
from src.eva_platform.supabase_client import SupabaseAdminClient, SupabaseAdminError

router = APIRouter()


def _normalize_role(role: str | None) -> str:
    return (role or "").strip().upper()


def _normalize_status(status: str | None) -> str:
    return (status or "").strip().upper()


def _build_owner_candidates(account: EvaAccount, users: Iterable[EvaAccountUser]) -> list[EvaAccountUser]:
    """Return ranked owner candidates from best to worst."""
    account_owner_user_id = (account.owner_user_id or "").strip()
    ranked: list[tuple[int, int, EvaAccountUser]] = []

    for idx, candidate in enumerate(users):
        email = (candidate.email or "").strip()
        if not email:
            continue

        matches_owner_user_id = bool(account_owner_user_id) and candidate.user_id == account_owner_user_id
        is_owner_role = _normalize_role(candidate.role) == "OWNER"
        is_active = _normalize_status(candidate.status) == "ACTIVE"

        if matches_owner_user_id and is_active:
            rank = 0
        elif is_owner_role and is_active:
            rank = 1
        elif matches_owner_user_id:
            rank = 2
        elif is_owner_role:
            rank = 3
        else:
            continue

        ranked.append((rank, idx, candidate))

    ranked.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in ranked]


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

    # Pull all account users in stable order, then pick deterministic owner candidates.
    result = await eva_db.execute(
        select(EvaAccountUser).where(
            EvaAccountUser.account_id == account_id,
        )
        .order_by(
            EvaAccountUser.created_at.asc(),
            EvaAccountUser.id.asc(),
        )
    )
    users = list(result.scalars().all())
    candidates = _build_owner_candidates(account, users)
    if not candidates:
        raise HTTPException(status_code=404, detail="No owner user found for this account")

    magic_link = ""
    last_error: str | None = None
    for candidate in candidates:
        try:
            magic_link = await SupabaseAdminClient.admin_generate_link(
                email=candidate.email,
                link_type="magiclink",
            )
        except SupabaseAdminError as exc:
            last_error = str(exc)
            continue
        if magic_link:
            break

    if not magic_link and last_error:
        raise HTTPException(status_code=400, detail=last_error)
    if not magic_link:
        raise HTTPException(status_code=500, detail="Failed to generate magic link")

    return ImpersonationResponse(
        magic_link_url=magic_link,
        account_id=account.id,
        account_name=account.name,
    )
