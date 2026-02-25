"""Eva Customers: real accounts (Eva DB) + draft accounts (ERP DB)."""

import logging
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.common.database import get_db, get_eva_db
from src.eva_platform.models import EvaAccount, EvaAccountUser
from src.eva_platform.drafts.models import AccountDraft
from src.eva_platform.schemas import (
    AccountDraftCreate,
    AccountDraftResponse,
    AccountDraftUpdate,
    EvaAccountCreateRequest,
    EvaAccountDetailResponse,
    EvaAccountResponse,
)
from src.eva_platform.supabase_client import (
    SupabaseAdminClient,
    SupabaseAdminError,
    map_supabase_error_to_http,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Real Accounts (Eva DB) ───────────────────────────────

@router.get("/accounts", response_model=list[EvaAccountResponse])
async def list_accounts(
    search: str | None = Query(None),
    partner_id: uuid.UUID | None = Query(None),
    eva_db: AsyncSession = Depends(get_eva_db),
    user: User = Depends(get_current_user),
):
    q = select(EvaAccount).order_by(EvaAccount.created_at.desc())
    if search:
        q = q.where(EvaAccount.name.ilike(f"%{search}%"))
    if partner_id:
        q = q.where(EvaAccount.partner_id == partner_id)
    result = await eva_db.execute(q)
    return result.scalars().all()


@router.get("/accounts/{account_id}", response_model=EvaAccountDetailResponse)
async def get_account(
    account_id: uuid.UUID,
    eva_db: AsyncSession = Depends(get_eva_db),
    user: User = Depends(get_current_user),
):
    result = await eva_db.execute(select(EvaAccount).where(EvaAccount.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.post("/accounts", response_model=EvaAccountDetailResponse, status_code=201)
async def create_account(
    data: EvaAccountCreateRequest,
    eva_db: AsyncSession = Depends(get_eva_db),
    user: User = Depends(get_current_user),
):
    normalized_owner_email = data.owner_email.strip().lower()
    password = data.temporary_password or secrets.token_urlsafe(16)

    # Create Supabase user
    try:
        sb_user = await SupabaseAdminClient.admin_create_user(
            email=normalized_owner_email,
            password=password,
            user_metadata={
                "role": "account",
                "name": data.owner_name,
                "require_password_change": True,
            },
        )
    except SupabaseAdminError as exc:
        status_code, detail = map_supabase_error_to_http(exc)
        raise HTTPException(status_code=status_code, detail=detail) from exc

    sb_user_id = SupabaseAdminClient.extract_user_id(sb_user)

    try:
        # Create account in Eva DB
        now = datetime.now(timezone.utc)
        account = EvaAccount(
            id=uuid.uuid4(),
            name=data.name,
            owner_user_id=str(sb_user_id),
            account_type=data.account_type.upper(),
            partner_id=data.partner_id,
            plan_tier=data.plan_tier.upper(),
            billing_interval=data.billing_cycle.upper(),
            facturapi_org_api_key=data.facturapi_org_api_key,
            timezone="America/Mexico_City",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        eva_db.add(account)
        await eva_db.flush()

        # Create account user (owner)
        account_user = EvaAccountUser(
            id=uuid.uuid4(),
            account_id=account.id,
            user_id=str(sb_user_id),
            email=normalized_owner_email,
            display_name=data.owner_name,
            role="OWNER",
            status="ACTIVE",
            created_at=now,
            updated_at=now,
        )
        eva_db.add(account_user)
    except Exception as exc:
        logger.exception(
            "Provisioning failed after Supabase auth user creation for email=%s sb_user_id=%s",
            normalized_owner_email,
            sb_user_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Account provisioning failed after auth user creation. Please contact support.",
        ) from exc

    return account


# ── Draft Accounts (ERP DB) ─────────────────────────────

@router.get("/drafts", response_model=list[AccountDraftResponse])
async def list_drafts(
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(AccountDraft).order_by(AccountDraft.created_at.desc())
    if status:
        q = q.where(AccountDraft.status == status)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/drafts", response_model=AccountDraftResponse, status_code=201)
async def create_draft(
    data: AccountDraftCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    draft = AccountDraft(
        name=data.name,
        account_type=data.account_type,
        owner_email=data.owner_email,
        owner_name=data.owner_name,
        partner_id=data.partner_id,
        plan_tier=data.plan_tier,
        billing_cycle=data.billing_cycle,
        facturapi_org_api_key=data.facturapi_org_api_key,
        notes=data.notes,
        prospect_id=data.prospect_id,
        created_by=user.id,
    )
    db.add(draft)
    await db.flush()
    await db.refresh(draft)
    return draft


@router.patch("/drafts/{draft_id}", response_model=AccountDraftResponse)
async def update_draft(
    draft_id: uuid.UUID,
    data: AccountDraftUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(AccountDraft).where(AccountDraft.id == draft_id))
    draft = result.scalar_one_or_none()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    if draft.status != "draft":
        raise HTTPException(status_code=400, detail="Only drafts in 'draft' status can be updated")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(draft, field, value)
    db.add(draft)
    return draft


@router.post("/drafts/{draft_id}/approve", response_model=AccountDraftResponse)
async def approve_draft(
    draft_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    eva_db: AsyncSession = Depends(get_eva_db),
    user: User = Depends(get_current_user),
):
    """Approve a draft: provision real account in Eva DB + Supabase user."""
    result = await db.execute(select(AccountDraft).where(AccountDraft.id == draft_id))
    draft = result.scalar_one_or_none()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    if draft.status != "draft":
        raise HTTPException(status_code=400, detail=f"Draft is already '{draft.status}'")

    normalized_owner_email = draft.owner_email.strip().lower()
    password = secrets.token_urlsafe(16)

    # 1. Create Supabase user
    try:
        sb_user = await SupabaseAdminClient.admin_create_user(
            email=normalized_owner_email,
            password=password,
            user_metadata={
                "role": "account",
                "name": draft.owner_name,
                "require_password_change": True,
            },
        )
    except SupabaseAdminError as exc:
        draft.status = "failed"
        db.add(draft)
        status_code, detail = map_supabase_error_to_http(exc)
        raise HTTPException(status_code=status_code, detail=detail) from exc

    sb_user_id = SupabaseAdminClient.extract_user_id(sb_user)

    try:
        # 2. Create Account + AccountUser in Eva DB
        now = datetime.now(timezone.utc)
        account = EvaAccount(
            id=uuid.uuid4(),
            name=draft.name,
            owner_user_id=str(sb_user_id),
            account_type=draft.account_type.upper(),
            partner_id=draft.partner_id,
            plan_tier=draft.plan_tier.upper(),
            billing_interval=draft.billing_cycle.upper(),
            facturapi_org_api_key=draft.facturapi_org_api_key,
            timezone="America/Mexico_City",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        eva_db.add(account)
        await eva_db.flush()

        account_user = EvaAccountUser(
            id=uuid.uuid4(),
            account_id=account.id,
            user_id=str(sb_user_id),
            email=normalized_owner_email,
            display_name=draft.owner_name,
            role="OWNER",
            status="ACTIVE",
            created_at=now,
            updated_at=now,
        )
        eva_db.add(account_user)

        # 3. Update draft in ERP DB
        draft.status = "approved"
        draft.provisioned_account_id = account.id
        draft.approved_by = user.id
        draft.approved_at = now
        db.add(draft)
    except Exception as exc:
        draft.status = "failed"
        db.add(draft)
        logger.exception(
            "Draft approval provisioning failed after Supabase auth user creation for draft_id=%s email=%s sb_user_id=%s",
            draft_id,
            normalized_owner_email,
            sb_user_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Account provisioning failed after auth user creation. Please contact support.",
        ) from exc

    return draft


@router.delete("/drafts/{draft_id}")
async def delete_draft(
    draft_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(AccountDraft).where(AccountDraft.id == draft_id))
    draft = result.scalar_one_or_none()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")
    if draft.status == "approved":
        raise HTTPException(status_code=400, detail="Cannot delete approved drafts")
    await db.delete(draft)
    return {"message": "Draft deleted"}
