"""Partners + Deals: CRUD against Eva production DB."""

import logging
import re
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.common.database import get_eva_db
from src.eva_platform.models import (
    EvaAccount,
    EvaAccountUser,
    EvaPartner,
    EvaPartnerDeal,
    EvaPartnerUser,
)
from src.eva_platform.schemas import (
    DealAccountCreateRequest,
    DealCreateRequest,
    DealLostRequest,
    DealResponse,
    DealUpdateRequest,
    EvaPartnerCreateRequest,
    EvaPartnerDetailResponse,
    EvaPartnerResponse,
    EvaPartnerUpdateRequest,
    EvaAccountResponse,
)
from src.eva_platform.supabase_client import (
    SupabaseAdminClient,
    SupabaseAdminError,
    map_supabase_error_to_http,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", (value or "").lower().strip())
    return normalized.strip("-") or "partner"


# ── Partners ─────────────────────────────────────────────

@router.get("/partners", response_model=list[EvaPartnerResponse])
async def list_partners(
    search: str | None = Query(None),
    type: str | None = Query(None),
    eva_db: AsyncSession = Depends(get_eva_db),
    user: User = Depends(get_current_user),
):
    q = select(EvaPartner).order_by(EvaPartner.created_at.desc())
    if search:
        q = q.where(EvaPartner.name.ilike(f"%{search}%"))
    if type:
        q = q.where(EvaPartner.type == type.upper())
    result = await eva_db.execute(q)
    partners = result.scalars().all()

    # Enrich with counts
    enriched = []
    for p in partners:
        deal_count = (await eva_db.execute(
            select(func.count(EvaPartnerDeal.id)).where(EvaPartnerDeal.partner_id == p.id)
        )).scalar() or 0
        account_count = (await eva_db.execute(
            select(func.count(EvaAccount.id)).where(EvaAccount.partner_id == p.id)
        )).scalar() or 0

        resp = EvaPartnerResponse.model_validate(p)
        resp.deal_count = deal_count
        resp.account_count = account_count
        enriched.append(resp)

    return enriched


@router.post("/partners", response_model=EvaPartnerDetailResponse, status_code=201)
async def create_partner(
    data: EvaPartnerCreateRequest,
    eva_db: AsyncSession = Depends(get_eva_db),
    user: User = Depends(get_current_user),
):
    normalized_owner_email = data.owner_email.strip().lower()
    slug = _slugify(data.name)

    # Ensure unique slug
    existing = await eva_db.execute(select(EvaPartner).where(EvaPartner.slug == slug))
    if existing.scalar_one_or_none():
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"

    now = datetime.now(timezone.utc)
    partner = EvaPartner(
        id=uuid.uuid4(),
        name=data.name,
        slug=slug,
        brand_name=data.brand_name or data.name,
        type=data.type.upper(),
        contact_email=data.contact_email or data.owner_email,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    eva_db.add(partner)
    await eva_db.flush()

    # Create partner owner in Supabase
    password = secrets.token_urlsafe(16)
    try:
        sb_user = await SupabaseAdminClient.admin_create_user(
            email=normalized_owner_email,
            password=password,
            user_metadata={
                "partner_id": str(partner.id),
                "role": "partner",
                "name": data.owner_name,
                "require_password_change": True,
            },
        )
    except SupabaseAdminError as exc:
        status_code, detail = map_supabase_error_to_http(exc)
        raise HTTPException(status_code=status_code, detail=detail) from exc

    sb_user_id = SupabaseAdminClient.extract_user_id(sb_user)
    try:
        partner_user = EvaPartnerUser(
            id=uuid.uuid4(),
            partner_id=partner.id,
            user_id=str(sb_user_id),
            email=normalized_owner_email,
            display_name=data.owner_name,
            role="OWNER",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        eva_db.add(partner_user)
    except Exception as exc:
        logger.exception(
            "Partner provisioning failed after Supabase auth user creation for partner_id=%s email=%s sb_user_id=%s",
            partner.id,
            normalized_owner_email,
            sb_user_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Partner provisioning failed after auth user creation. Please contact support.",
        ) from exc

    return EvaPartnerDetailResponse(
        id=partner.id,
        name=partner.name,
        slug=partner.slug,
        brand_name=partner.brand_name,
        logo_url=partner.logo_url,
        primary_color=partner.primary_color,
        type=partner.type,
        is_active=partner.is_active,
        contact_email=partner.contact_email,
        custom_domain=partner.custom_domain,
        created_at=partner.created_at,
        updated_at=partner.updated_at,
    )


@router.get("/partners/{partner_id}", response_model=EvaPartnerDetailResponse)
async def get_partner(
    partner_id: uuid.UUID,
    eva_db: AsyncSession = Depends(get_eva_db),
    user: User = Depends(get_current_user),
):
    result = await eva_db.execute(select(EvaPartner).where(EvaPartner.id == partner_id))
    partner = result.scalar_one_or_none()
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")

    # Get accounts and deals
    accounts_result = await eva_db.execute(
        select(EvaAccount).where(EvaAccount.partner_id == partner_id)
    )
    deals_result = await eva_db.execute(
        select(EvaPartnerDeal).where(EvaPartnerDeal.partner_id == partner_id)
    )
    accounts = accounts_result.scalars().all()
    deals = deals_result.scalars().all()

    won_deals = sum(1 for d in deals if d.stage == "WON")

    return EvaPartnerDetailResponse(
        id=partner.id,
        name=partner.name,
        slug=partner.slug,
        brand_name=partner.brand_name,
        logo_url=partner.logo_url,
        primary_color=partner.primary_color,
        type=partner.type,
        is_active=partner.is_active,
        contact_email=partner.contact_email,
        custom_domain=partner.custom_domain,
        created_at=partner.created_at,
        updated_at=partner.updated_at,
        deal_count=len(deals),
        won_deals=won_deals,
        account_count=len(accounts),
        accounts=[EvaAccountResponse.model_validate(a) for a in accounts],
        deals=[DealResponse.model_validate(d) for d in deals],
    )


@router.patch("/partners/{partner_id}", response_model=EvaPartnerResponse)
async def update_partner(
    partner_id: uuid.UUID,
    data: EvaPartnerUpdateRequest,
    eva_db: AsyncSession = Depends(get_eva_db),
    user: User = Depends(get_current_user),
):
    result = await eva_db.execute(select(EvaPartner).where(EvaPartner.id == partner_id))
    partner = result.scalar_one_or_none()
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "type" and value:
            value = value.upper()
        setattr(partner, field, value)
    partner.updated_at = datetime.now(timezone.utc)
    eva_db.add(partner)
    return partner


@router.delete("/partners/{partner_id}")
async def deactivate_partner(
    partner_id: uuid.UUID,
    eva_db: AsyncSession = Depends(get_eva_db),
    user: User = Depends(get_current_user),
):
    result = await eva_db.execute(select(EvaPartner).where(EvaPartner.id == partner_id))
    partner = result.scalar_one_or_none()
    if not partner:
        raise HTTPException(status_code=404, detail="Partner not found")
    partner.is_active = False
    partner.updated_at = datetime.now(timezone.utc)
    eva_db.add(partner)
    return {"message": "Partner deactivated"}


# ── Deals ────────────────────────────────────────────────

@router.get("/deals", response_model=list[DealResponse])
async def list_deals(
    partner_id: uuid.UUID | None = Query(None),
    stage: str | None = Query(None),
    eva_db: AsyncSession = Depends(get_eva_db),
    user: User = Depends(get_current_user),
):
    q = select(EvaPartnerDeal).order_by(EvaPartnerDeal.created_at.desc())
    if partner_id:
        q = q.where(EvaPartnerDeal.partner_id == partner_id)
    if stage:
        q = q.where(EvaPartnerDeal.stage == stage.upper())
    result = await eva_db.execute(q)
    return result.scalars().all()


@router.post("/deals", response_model=DealResponse, status_code=201)
async def create_deal(
    data: DealCreateRequest,
    eva_db: AsyncSession = Depends(get_eva_db),
    user: User = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    deal = EvaPartnerDeal(
        id=uuid.uuid4(),
        partner_id=data.partner_id,
        company_name=data.company_name,
        contact_name=data.contact_name,
        contact_email=data.contact_email,
        contact_phone=data.contact_phone,
        stage="TO_CONTACT",
        plan_tier=data.plan_tier,
        billing_cycle=data.billing_cycle,
        notes=data.notes,
        created_at=now,
        updated_at=now,
    )
    eva_db.add(deal)
    await eva_db.flush()
    await eva_db.refresh(deal)
    return deal


@router.patch("/deals/{deal_id}", response_model=DealResponse)
async def update_deal(
    deal_id: uuid.UUID,
    data: DealUpdateRequest,
    eva_db: AsyncSession = Depends(get_eva_db),
    user: User = Depends(get_current_user),
):
    result = await eva_db.execute(select(EvaPartnerDeal).where(EvaPartnerDeal.id == deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "stage" and value:
            value = value.upper()
        setattr(deal, field, value)
    deal.updated_at = datetime.now(timezone.utc)
    eva_db.add(deal)
    return deal


@router.delete("/deals/{deal_id}")
async def delete_deal(
    deal_id: uuid.UUID,
    eva_db: AsyncSession = Depends(get_eva_db),
    user: User = Depends(get_current_user),
):
    result = await eva_db.execute(select(EvaPartnerDeal).where(EvaPartnerDeal.id == deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    await eva_db.delete(deal)
    return {"message": "Deal deleted"}


@router.post("/deals/{deal_id}/won", response_model=DealResponse)
async def mark_deal_won(
    deal_id: uuid.UUID,
    eva_db: AsyncSession = Depends(get_eva_db),
    user: User = Depends(get_current_user),
):
    result = await eva_db.execute(select(EvaPartnerDeal).where(EvaPartnerDeal.id == deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    deal.stage = "WON"
    deal.won_at = datetime.now(timezone.utc)
    deal.updated_at = datetime.now(timezone.utc)
    eva_db.add(deal)
    return deal


@router.post("/deals/{deal_id}/lost", response_model=DealResponse)
async def mark_deal_lost(
    deal_id: uuid.UUID,
    data: DealLostRequest,
    eva_db: AsyncSession = Depends(get_eva_db),
    user: User = Depends(get_current_user),
):
    result = await eva_db.execute(select(EvaPartnerDeal).where(EvaPartnerDeal.id == deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    deal.stage = "LOST"
    deal.lost_at = datetime.now(timezone.utc)
    deal.lost_reason = data.reason
    deal.updated_at = datetime.now(timezone.utc)
    eva_db.add(deal)
    return deal


@router.post("/deals/{deal_id}/create-account", response_model=DealResponse)
async def create_account_from_deal(
    deal_id: uuid.UUID,
    data: DealAccountCreateRequest,
    eva_db: AsyncSession = Depends(get_eva_db),
    user: User = Depends(get_current_user),
):
    """Create a real Eva account from a won deal."""
    result = await eva_db.execute(select(EvaPartnerDeal).where(EvaPartnerDeal.id == deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    if deal.stage != "WON":
        raise HTTPException(status_code=400, detail="Deal must be WON to create account")
    if deal.linked_account_id:
        raise HTTPException(status_code=400, detail="Deal already has a linked account")

    normalized_owner_email = data.owner_email.strip().lower()
    password = data.temporary_password or secrets.token_urlsafe(16)

    # Create Supabase user
    try:
        sb_user = await SupabaseAdminClient.admin_create_user(
            email=normalized_owner_email,
            password=password,
            user_metadata={
                "role": "account",
                "name": data.name,
                "require_password_change": True,
            },
        )
    except SupabaseAdminError as exc:
        status_code, detail = map_supabase_error_to_http(exc)
        raise HTTPException(status_code=status_code, detail=detail) from exc

    sb_user_id = SupabaseAdminClient.extract_user_id(sb_user)

    try:
        now = datetime.now(timezone.utc)
        account = EvaAccount(
            id=uuid.uuid4(),
            name=data.name,
            owner_user_id=str(sb_user_id),
            account_type="COMMERCE",
            partner_id=deal.partner_id,
            plan_tier=data.plan_tier.upper(),
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
            display_name=data.name,
            role="OWNER",
            status="ACTIVE",
            created_at=now,
            updated_at=now,
        )
        eva_db.add(account_user)

        deal.linked_account_id = account.id
        deal.updated_at = now
        eva_db.add(deal)
    except Exception as exc:
        logger.exception(
            "Deal account provisioning failed after Supabase auth user creation for deal_id=%s email=%s sb_user_id=%s",
            deal_id,
            normalized_owner_email,
            sb_user_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Account provisioning failed after auth user creation. Please contact support.",
        ) from exc

    return deal
