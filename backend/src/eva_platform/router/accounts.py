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
from src.eva_platform.pricing_models import AccountPricingProfile
from src.eva_platform.schemas import (
    AccountPricingCoverageResponse,
    AccountPricingResponse,
    AccountPricingUpdateRequest,
    AccountDraftCreate,
    AccountDraftResponse,
    AccountDraftUpdate,
    EvaAccountCreateRequest,
    EvaAccountDetailResponse,
    EvaAccountResponse,
)
from src.eva_platform.provisioning_utils import (
    ensure_owner_user_is_available,
    map_provisioning_write_error,
    normalize_account_type,
    normalize_billing_cycle,
    normalize_plan_tier,
)
from src.eva_platform.supabase_client import (
    SupabaseAdminClient,
    SupabaseAdminError,
    map_supabase_error_to_http,
)

router = APIRouter()
logger = logging.getLogger(__name__)

VALID_BILLING_CURRENCIES = {"MXN", "USD"}
VALID_BILLING_INTERVALS = {"MONTHLY", "ANNUAL"}


def _normalize_billing_currency(value: str | None) -> str:
    currency = str(value or "MXN").upper().strip()
    if currency not in VALID_BILLING_CURRENCIES:
        raise HTTPException(status_code=422, detail="billing_currency must be MXN or USD")
    return currency


def _normalize_billing_interval(value: str | None) -> str:
    raw = str(value or "MONTHLY").upper().strip()
    aliases = {
        "MONTH": "MONTHLY",
        "MONTHLY": "MONTHLY",
        "YEAR": "ANNUAL",
        "YEARLY": "ANNUAL",
        "ANNUAL": "ANNUAL",
    }
    interval = aliases.get(raw)
    if not interval:
        raise HTTPException(status_code=422, detail="billing_interval must be MONTHLY or ANNUAL")
    return interval


def _pricing_complete(profile: AccountPricingProfile | None) -> bool:
    if profile is None:
        return False
    if not profile.is_billable:
        return True
    return (
        profile.billing_amount is not None
        and profile.billing_currency in VALID_BILLING_CURRENCIES
        and profile.billing_interval in VALID_BILLING_INTERVALS
    )


def _build_account_pricing_response(
    account: EvaAccount,
    profile: AccountPricingProfile | None,
) -> AccountPricingResponse:
    billing_currency = profile.billing_currency if profile else _normalize_billing_currency(account.billing_currency)
    billing_interval = profile.billing_interval if profile else _normalize_billing_interval(account.billing_interval)
    is_billable = profile.is_billable if profile else True
    return AccountPricingResponse(
        account_id=account.id,
        account_name=account.name,
        account_is_active=bool(account.is_active),
        billing_amount=profile.billing_amount if profile else None,
        billing_currency=billing_currency,
        billing_interval=billing_interval,
        is_billable=is_billable,
        notes=profile.notes if profile else None,
        pricing_complete=_pricing_complete(profile),
        created_at=profile.created_at if profile else None,
        updated_at=profile.updated_at if profile else None,
    )


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


@router.get("/account-pricing", response_model=list[AccountPricingResponse])
async def list_account_pricing(
    search: str | None = Query(None),
    eva_db: AsyncSession = Depends(get_eva_db),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = (
        select(EvaAccount)
        .where(EvaAccount.is_active == True)
        .order_by(EvaAccount.created_at.desc())
    )
    if search:
        q = q.where(EvaAccount.name.ilike(f"%{search}%"))
    account_rows = await eva_db.execute(q)
    accounts = account_rows.scalars().all()
    if not accounts:
        return []

    account_ids = [account.id for account in accounts]
    pricing_rows = await db.execute(
        select(AccountPricingProfile).where(AccountPricingProfile.account_id.in_(account_ids))
    )
    pricing_by_account = {row.account_id: row for row in pricing_rows.scalars().all()}
    return [_build_account_pricing_response(account, pricing_by_account.get(account.id)) for account in accounts]


@router.get("/account-pricing/coverage", response_model=AccountPricingCoverageResponse)
async def get_account_pricing_coverage(
    eva_db: AsyncSession = Depends(get_eva_db),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    accounts_result = await eva_db.execute(
        select(EvaAccount.id).where(EvaAccount.is_active == True)
    )
    account_ids = [row[0] for row in accounts_result.all()]
    if not account_ids:
        return AccountPricingCoverageResponse(
            active_accounts=0,
            billable_accounts=0,
            configured_accounts=0,
            missing_accounts=0,
            coverage_pct=100.0,
        )

    pricing_rows = await db.execute(
        select(AccountPricingProfile).where(AccountPricingProfile.account_id.in_(account_ids))
    )
    pricing_by_account = {row.account_id: row for row in pricing_rows.scalars().all()}

    billable_accounts = 0
    configured_accounts = 0
    for account_id in account_ids:
        profile = pricing_by_account.get(account_id)
        is_billable = profile.is_billable if profile is not None else True
        if not is_billable:
            continue
        billable_accounts += 1
        if _pricing_complete(profile):
            configured_accounts += 1

    missing_accounts = max(billable_accounts - configured_accounts, 0)
    coverage_pct = (
        round(float(configured_accounts / billable_accounts * 100), 2)
        if billable_accounts > 0
        else 100.0
    )

    return AccountPricingCoverageResponse(
        active_accounts=len(account_ids),
        billable_accounts=billable_accounts,
        configured_accounts=configured_accounts,
        missing_accounts=missing_accounts,
        coverage_pct=coverage_pct,
    )


@router.patch("/account-pricing/{account_id}", response_model=AccountPricingResponse)
async def upsert_account_pricing(
    account_id: uuid.UUID,
    data: AccountPricingUpdateRequest,
    eva_db: AsyncSession = Depends(get_eva_db),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    account_result = await eva_db.execute(select(EvaAccount).where(EvaAccount.id == account_id))
    account = account_result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    payload = data.model_dump(exclude_unset=True)
    if not payload:
        raise HTTPException(status_code=422, detail="No pricing fields provided")

    profile_result = await db.execute(
        select(AccountPricingProfile).where(AccountPricingProfile.account_id == account_id)
    )
    profile = profile_result.scalar_one_or_none()
    if not profile:
        profile = AccountPricingProfile(
            account_id=account_id,
            billing_currency=_normalize_billing_currency(account.billing_currency),
            billing_interval=_normalize_billing_interval(account.billing_interval),
            is_billable=True,
        )

    if "billing_amount" in payload:
        profile.billing_amount = payload["billing_amount"]
    if "billing_currency" in payload:
        profile.billing_currency = _normalize_billing_currency(payload["billing_currency"])
    if "billing_interval" in payload:
        profile.billing_interval = _normalize_billing_interval(payload["billing_interval"])
    if "is_billable" in payload and payload["is_billable"] is not None:
        profile.is_billable = bool(payload["is_billable"])
    if "notes" in payload:
        profile.notes = payload["notes"]
    profile.updated_by = user.id

    db.add(profile)
    await db.flush()
    await db.refresh(profile)
    return _build_account_pricing_response(account, profile)


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
    normalized_account_type = normalize_account_type(data.account_type)
    normalized_plan_tier = normalize_plan_tier(data.plan_tier)
    normalized_billing_interval = normalize_billing_cycle(data.billing_cycle)
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
    await ensure_owner_user_is_available(eva_db, str(sb_user_id), normalized_owner_email)

    try:
        # Create account in Eva DB
        now = datetime.now(timezone.utc)
        account = EvaAccount(
            id=uuid.uuid4(),
            name=data.name,
            owner_user_id=str(sb_user_id),
            account_type=normalized_account_type,
            partner_id=data.partner_id,
            plan_tier=normalized_plan_tier,
            billing_interval=normalized_billing_interval,
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
        raise map_provisioning_write_error(
            exc,
            "Account provisioning failed after auth user creation. Please contact support.",
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
        billing_amount=data.billing_amount,
        billing_currency=_normalize_billing_currency(data.billing_currency),
        is_billable=data.is_billable,
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
        if field == "billing_currency":
            value = _normalize_billing_currency(value)
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
    normalized_account_type = normalize_account_type(draft.account_type)
    normalized_plan_tier = normalize_plan_tier(draft.plan_tier)
    normalized_billing_interval = normalize_billing_cycle(draft.billing_cycle)
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
    await ensure_owner_user_is_available(eva_db, str(sb_user_id), normalized_owner_email)

    try:
        # 2. Create Account + AccountUser in Eva DB
        now = datetime.now(timezone.utc)
        account = EvaAccount(
            id=uuid.uuid4(),
            name=draft.name,
            owner_user_id=str(sb_user_id),
            account_type=normalized_account_type,
            partner_id=draft.partner_id,
            plan_tier=normalized_plan_tier,
            billing_interval=normalized_billing_interval,
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

        # 3. Persist pricing profile in ERP DB
        db.add(
            AccountPricingProfile(
                account_id=account.id,
                billing_amount=draft.billing_amount,
                billing_currency=_normalize_billing_currency(draft.billing_currency),
                billing_interval=_normalize_billing_interval(draft.billing_cycle),
                is_billable=draft.is_billable,
                notes=draft.notes,
                updated_by=user.id,
            )
        )

        # 4. Update draft in ERP DB
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
        raise map_provisioning_write_error(
            exc,
            "Account provisioning failed after auth user creation. Please contact support.",
        ) from exc

    return draft


@router.delete("/accounts/{account_id}")
async def deactivate_account(
    account_id: uuid.UUID,
    eva_db: AsyncSession = Depends(get_eva_db),
    user: User = Depends(get_current_user),
):
    """Soft-delete: set is_active = False."""
    result = await eva_db.execute(select(EvaAccount).where(EvaAccount.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if not account.is_active:
        raise HTTPException(status_code=400, detail="Account is already inactive")
    account.is_active = False
    account.updated_at = datetime.now(timezone.utc)
    eva_db.add(account)
    return {"message": f"Account '{account.name}' deactivated"}


@router.delete("/accounts/{account_id}/permanent")
async def permanently_delete_account(
    account_id: uuid.UUID,
    eva_db: AsyncSession = Depends(get_eva_db),
    user: User = Depends(get_current_user),
):
    """Hard-delete: remove account and its users from the database."""
    result = await eva_db.execute(select(EvaAccount).where(EvaAccount.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if account.is_active:
        raise HTTPException(status_code=400, detail="Deactivate the account before deleting permanently")
    # Delete associated account_users first
    await eva_db.execute(
        EvaAccountUser.__table__.delete().where(EvaAccountUser.account_id == account_id)
    )
    await eva_db.delete(account)
    return {"message": f"Account '{account.name}' permanently deleted"}


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
