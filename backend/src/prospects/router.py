import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.common.database import get_db
from src.customers.models import Customer
from src.eva_platform.drafts.models import AccountDraft
from src.eva_platform.schemas import AccountDraftCreate, AccountDraftResponse
from src.prospects.models import Prospect, ProspectInteraction
from src.prospects.schemas import (
    InteractionCreate, InteractionResponse, ProspectCreate,
    ProspectResponse, ProspectSummary, ProspectUpdate,
)

router = APIRouter(prefix="/prospects", tags=["prospects"])


@router.get("", response_model=list[ProspectResponse])
async def list_prospects(
    status: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(Prospect).order_by(Prospect.updated_at.desc())
    if status:
        q = q.where(Prospect.status == status)
    if search:
        q = q.where(Prospect.company_name.ilike(f"%{search}%"))
    result = await db.execute(q)
    return result.scalars().all()


@router.post("", response_model=ProspectResponse, status_code=201)
async def create_prospect(
    data: ProspectCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    estimated_mrr_usd = None
    if data.estimated_mrr is not None:
        from src.finances.router import _get_mxn_to_usd, _to_usd
        rate = await _get_mxn_to_usd(db)
        estimated_mrr_usd = _to_usd(data.estimated_mrr, data.estimated_mrr_currency, rate)

    prospect = Prospect(
        **data.model_dump(exclude={"estimated_mrr_currency"}),
        estimated_mrr_usd=estimated_mrr_usd,
        created_by=user.id,
    )
    db.add(prospect)
    await db.flush()
    await db.refresh(prospect)
    return prospect


@router.get("/summary", response_model=ProspectSummary)
async def prospect_summary(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Prospect))
    prospects = result.scalars().all()
    by_status: dict[str, int] = {}
    pipeline_usd = 0.0
    for p in prospects:
        by_status[p.status] = by_status.get(p.status, 0) + 1
        if p.status not in ("won", "lost") and p.estimated_mrr_usd:
            pipeline_usd += float(p.estimated_mrr_usd)
    return ProspectSummary(total=len(prospects), by_status=by_status, total_estimated_pipeline_usd=pipeline_usd)


@router.get("/due-followups", response_model=list[ProspectResponse])
async def due_followups(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    today = date.today()
    result = await db.execute(
        select(Prospect).where(Prospect.next_follow_up <= today).order_by(Prospect.next_follow_up)
    )
    return result.scalars().all()


@router.get("/{prospect_id}", response_model=ProspectResponse)
async def get_prospect(
    prospect_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Prospect).where(Prospect.id == prospect_id))
    prospect = result.scalar_one_or_none()
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    return prospect


@router.patch("/{prospect_id}", response_model=ProspectResponse)
async def update_prospect(
    prospect_id: uuid.UUID,
    data: ProspectUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Prospect).where(Prospect.id == prospect_id))
    prospect = result.scalar_one_or_none()
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(prospect, field, value)
    db.add(prospect)
    return prospect


@router.delete("/{prospect_id}")
async def delete_prospect(
    prospect_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Prospect).where(Prospect.id == prospect_id))
    prospect = result.scalar_one_or_none()
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    await db.delete(prospect)
    return {"message": "Prospect deleted"}


@router.post("/{prospect_id}/interactions", response_model=InteractionResponse, status_code=201)
async def add_interaction(
    prospect_id: uuid.UUID,
    data: InteractionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    interaction = ProspectInteraction(
        prospect_id=prospect_id, type=data.type, summary=data.summary,
        date=data.date, created_by=user.id,
    )
    db.add(interaction)
    await db.flush()
    await db.refresh(interaction)
    return interaction


@router.get("/{prospect_id}/interactions", response_model=list[InteractionResponse])
async def list_interactions(
    prospect_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ProspectInteraction)
        .where(ProspectInteraction.prospect_id == prospect_id)
        .order_by(ProspectInteraction.date.desc())
    )
    return result.scalars().all()


@router.post("/{prospect_id}/convert", response_model=ProspectResponse)
async def convert_to_customer(
    prospect_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Prospect).where(Prospect.id == prospect_id))
    prospect = result.scalar_one_or_none()
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    if prospect.converted_to_customer_id:
        raise HTTPException(status_code=400, detail="Already converted")

    customer = Customer(
        company_name=prospect.company_name,
        contact_name=prospect.contact_name,
        contact_email=prospect.contact_email,
        contact_phone=prospect.contact_phone,
        industry=prospect.industry,
        website=prospect.website,
        plan_tier=prospect.estimated_plan,
        mrr=prospect.estimated_mrr,
        mrr_currency=prospect.estimated_mrr_currency,
        mrr_usd=prospect.estimated_mrr_usd,
        arr=prospect.estimated_mrr * 12 if prospect.estimated_mrr else None,
        signup_date=date.today(),
        status="active",
        referral_source=prospect.referred_by,
        prospect_id=prospect.id,
        created_by=user.id,
    )
    db.add(customer)
    await db.flush()

    prospect.status = "won"
    prospect.converted_to_customer_id = customer.id
    db.add(prospect)
    return prospect


@router.post("/{prospect_id}/create-draft", response_model=AccountDraftResponse, status_code=201)
async def create_draft_from_prospect(
    prospect_id: uuid.UUID,
    data: AccountDraftCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create an account draft linked to a won prospect."""
    result = await db.execute(select(Prospect).where(Prospect.id == prospect_id))
    prospect = result.scalar_one_or_none()
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    if prospect.status != "won":
        raise HTTPException(status_code=400, detail="Prospect must be in 'won' status")
    if prospect.converted_to_draft_id:
        raise HTTPException(status_code=400, detail="Prospect already has a draft")

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
        prospect_id=prospect.id,
        created_by=user.id,
    )
    db.add(draft)
    await db.flush()

    prospect.converted_to_draft_id = draft.id
    db.add(prospect)
    await db.refresh(draft)
    return draft
