"""Eva Customers: real accounts (Eva DB) + draft accounts (ERP DB)."""

import logging
import re
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.common.database import get_db, get_eva_db
from src.eva_platform.onboarding import build_account_onboarding
from src.eva_platform.models import EvaAccount, EvaAccountUser
from src.eva_platform.drafts.models import AccountDraft
from src.eva_platform.pricing_models import AccountPricingProfile
from src.eva_platform.schemas import (
    AccountPricingCoverageResponse,
    AccountPricingResponse,
    AccountPricingUpdateRequest,
    AccountDraftCreate,
    AccountDraftProvisionResponse,
    AccountDraftResponse,
    AccountDraftUpdate,
    EvaAccountCreateRequest,
    EvaAccountDetailResponse,
    EvaAccountProvisionResponse,
    EvaAccountResponse,
)
from src.eva_platform.provisioning_utils import (
    ensure_owner_user_is_available,
    map_provisioning_write_error,
    normalize_account_type,
    normalize_billing_cycle,
    normalize_plan_tier,
    resolve_product_label,
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


def _map_permanent_delete_error(exc: Exception) -> HTTPException:
    """Map DB integrity failures for permanent delete into actionable API errors."""
    original = str(getattr(exc, "orig", exc))
    lowered = original.lower()
    if "cannot delete the last won stage in a pipeline" in lowered:
        return HTTPException(
            status_code=409,
            detail=(
                "Cannot permanently delete account because it owns the last won stage "
                "in at least one pipeline. Reassign or remove that stage first."
            ),
        )
    if "foreign key constraint" in lowered:
        table_matches = re.findall(r'on table "([^"]+)"', original, flags=re.IGNORECASE)
        table_name = table_matches[-1] if table_matches else None
        detail = "Cannot permanently delete account because related records still exist"
        if table_name:
            detail = f"{detail} (blocking table: {table_name})"
        return HTTPException(status_code=409, detail=detail)
    return HTTPException(status_code=500, detail="Failed to permanently delete account")


def _is_last_won_stage_delete_error(exc: Exception) -> bool:
    original = str(getattr(exc, "orig", exc))
    return "cannot delete the last won stage in a pipeline" in original.lower()


async def _cleanup_pipeline_stage_account_refs(
    eva_db: AsyncSession,
    account_id: uuid.UUID,
) -> bool:
    """Detach pipeline/stage references so permanent account delete can proceed."""
    refs_result = await eva_db.execute(
        text(
            """
            SELECT
                format('%I.%I', n.nspname, c.relname) AS qualified_table,
                quote_ident(a.attname) AS quoted_column,
                NOT a.attnotnull AS is_nullable
            FROM pg_constraint con
            JOIN pg_class c ON c.oid = con.conrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN unnest(con.conkey) WITH ORDINALITY AS k(attnum, ordinality) ON true
            JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = k.attnum
            JOIN pg_class refc ON refc.oid = con.confrelid
            JOIN pg_namespace refn ON refn.oid = refc.relnamespace
            WHERE con.contype = 'f'
              AND refn.nspname = 'public'
              AND refc.relname = 'accounts'
              AND n.nspname NOT IN ('pg_catalog', 'information_schema')
              AND (
                c.relname ILIKE '%pipeline%'
                OR c.relname ILIKE '%stage%'
                OR a.attname ILIKE '%pipeline%'
                OR a.attname ILIKE '%stage%'
              )
            ORDER BY n.nspname, c.relname, k.ordinality
            """
        )
    )
    refs = refs_result.all()
    if not refs:
        return False

    fallback_account_id = None
    if any(not row.is_nullable for row in refs):
        fallback_result = await eva_db.execute(
            text(
                """
                SELECT id
                FROM accounts
                WHERE id <> :account_id
                ORDER BY is_active DESC, created_at ASC
                LIMIT 1
                """
            ),
            {"account_id": account_id},
        )
        fallback_account_id = fallback_result.scalar_one_or_none()
        if fallback_account_id is None:
            return False

    changed_rows = 0
    for row in refs:
        table_name = row.qualified_table
        column_name = row.quoted_column
        if row.is_nullable:
            stmt = text(
                f"UPDATE {table_name} SET {column_name} = NULL "
                f"WHERE {column_name} = :account_id"
            )
            result = await eva_db.execute(stmt, {"account_id": account_id})
        else:
            stmt = text(
                f"UPDATE {table_name} SET {column_name} = :fallback_account_id "
                f"WHERE {column_name} = :account_id"
            )
            result = await eva_db.execute(
                stmt,
                {
                    "account_id": account_id,
                    "fallback_account_id": fallback_account_id,
                },
            )
        if result.rowcount:
            changed_rows += int(result.rowcount)

    return changed_rows > 0


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


@router.post("/accounts", response_model=EvaAccountProvisionResponse, status_code=201)
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

    try:
        onboarding = await build_account_onboarding(
            owner_email=normalized_owner_email,
            owner_name=data.owner_name,
            product_label=resolve_product_label(normalized_account_type),
            send_setup_email=data.send_setup_email,
        )
    except SupabaseAdminError as exc:
        status_code, detail = map_supabase_error_to_http(exc)
        raise HTTPException(status_code=status_code, detail=detail) from exc

    return EvaAccountProvisionResponse(
        account=EvaAccountDetailResponse.model_validate(account),
        onboarding=onboarding,
    )


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


@router.post("/drafts/{draft_id}/approve", response_model=AccountDraftProvisionResponse)
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

    try:
        onboarding = await build_account_onboarding(
            owner_email=normalized_owner_email,
            owner_name=draft.owner_name,
            product_label=resolve_product_label(normalized_account_type),
            send_setup_email=True,
        )
    except SupabaseAdminError as exc:
        status_code, detail = map_supabase_error_to_http(exc)
        raise HTTPException(status_code=status_code, detail=detail) from exc

    if draft.provisioned_account_id is None:
        raise HTTPException(status_code=500, detail="Account provisioning succeeded but no account id was returned.")

    return AccountDraftProvisionResponse(
        draft=AccountDraftResponse.model_validate(draft),
        account_id=draft.provisioned_account_id,
        onboarding=onboarding,
    )


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
    # Delete associated account_users first.
    try:
        await eva_db.execute(
            EvaAccountUser.__table__.delete().where(EvaAccountUser.account_id == account_id)
        )
        await eva_db.delete(account)
        # Force constraint checks here so we can map DB errors to a clear API response.
        await eva_db.flush()
    except SQLAlchemyError as exc:
        if _is_last_won_stage_delete_error(exc):
            await eva_db.rollback()
            cleaned = await _cleanup_pipeline_stage_account_refs(eva_db, account_id)
            if cleaned:
                retry_result = await eva_db.execute(select(EvaAccount).where(EvaAccount.id == account_id))
                retry_account = retry_result.scalar_one_or_none()
                if retry_account and not retry_account.is_active:
                    try:
                        await eva_db.execute(
                            EvaAccountUser.__table__.delete().where(EvaAccountUser.account_id == account_id)
                        )
                        await eva_db.delete(retry_account)
                        await eva_db.flush()
                        return {"message": f"Account '{retry_account.name}' permanently deleted"}
                    except SQLAlchemyError as retry_exc:
                        raise _map_permanent_delete_error(retry_exc) from retry_exc
        raise _map_permanent_delete_error(exc) from exc
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
