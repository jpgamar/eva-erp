import logging
import uuid
from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, UploadFile
from sqlalchemy import Boolean, func, or_, select, case, literal
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.common.database import get_db, get_eva_db, get_optional_eva_db
from src.common.config import settings
from src.empresas.models import Empresa, EmpresaHistory, EmpresaInteraction, EmpresaItem, PaymentLink
from src.empresas.schemas import (
    CheckoutLinkRequest,
    CheckoutLinkResponse,
    ConstanciaExtractResponse,
    CreateEvaAccountForEmpresaRequest,
    EmpresaCalendarItemResponse,
    EmpresaCreate,
    EmpresaHistoryResponse,
    EmpresaInteractionCreate,
    EmpresaInteractionResponse,
    EmpresaItemCreate,
    EmpresaItemResponse,
    EmpresaItemUpdate,
    EmpresaListPendingItem,
    EmpresaResponse,
    EmpresaUpdate,
    LinkEvaAccountRequest,
    PortalLinkResponse,
    PreviewCheckoutRequest,
    PreviewCheckoutResponse,
    SubscriptionApplyRequest,
    SubscriptionApplyResponse,
    SubscriptionCancelRequest,
    SubscriptionCancelResponse,
)
from src.eva_platform.eva_billing_client import EvaBillingClient, EvaBillingClientError
from src.eva_platform.models import (
    EvaAccount,
    EvaAgent,
    EvaInstagramChannel,
    EvaMessengerChannel,
    EvaWhatsAppChannel,
)
from src.eva_platform.schemas import EvaAccountCreateRequest, EvaAccountProvisionResponse

router = APIRouter(prefix="/empresas", tags=["empresas"])
logger = logging.getLogger(__name__)

TRACKED_FIELDS = {
    # Original audit set.
    "status",
    "ball_on",
    "summary_note",
    # Pipeline + billing fields that matter for operator history.
    "lifecycle_stage",
    "monthly_amount",
    "billing_interval",
    "payment_day",
    "expected_close_date",
    "eva_account_id",
    "person_type",
    "rfc",
    "razon_social",
    "regimen_fiscal",
    "fiscal_postal_code",
    "cfdi_use",
}

STAGES_REQUIRING_CLOSE_DATE = {"interesado", "demo", "negociacion"}

# Fields whose mutation triggers a re-check of _enforce_business_rules.
# Unrelated edits (billing emails, phone, industry, summary_note, etc.)
# must remain possible on empresas whose current state violates the rule.
BUSINESS_RULE_GATED_FIELDS = frozenset({"lifecycle_stage", "eva_account_id", "expected_close_date"})


def _should_enforce_business_rules(update_data: dict) -> bool:
    """True when the PATCH touches any field that changes rule inputs.

    Scoped so unrelated edits (e.g., billing_recipient_emails) can proceed
    on empresas whose current state would fail the rule (operativo but
    unlinked/inactive sub — the Acabados payment-link case, Apr 2026).
    """
    return any(field in update_data for field in BUSINESS_RULE_GATED_FIELDS)


async def _attempt_auto_match(
    db: AsyncSession,
    eva_db: AsyncSession | None,
    empresa: Empresa,
) -> None:
    """Try to link an Empresa to an Eva account by name (case-insensitive).

    Mutates ``empresa`` in place: sets ``auto_match_attempted=True``
    regardless of result, and sets ``eva_account_id`` only if exactly
    one Eva account name matches. Ambiguous matches (>1) are skipped
    with an INFO log so the user can resolve via manual override.

    Safe to call repeatedly; the ``auto_match_attempted`` flag
    short-circuits subsequent calls. NEVER overwrites an existing
    non-NULL ``eva_account_id``.
    """
    if empresa.auto_match_attempted:
        return
    if empresa.eva_account_id is not None:
        # Already linked manually; mark attempted so we don't try.
        empresa.auto_match_attempted = True
        return
    if eva_db is None:
        # Can't run auto-match without Eva DB access. Don't mark
        # attempted — try again on the next page load (when eva_db
        # may be configured).
        return

    normalized = empresa.name.strip()
    if not normalized:
        empresa.auto_match_attempted = True
        return

    try:
        result = await eva_db.execute(
            select(EvaAccount.id).where(
                func.lower(func.trim(EvaAccount.name)) == normalized.lower(),
                EvaAccount.is_active.is_(True),
            )
        )
        matches = list(result.scalars().all())
    except Exception as exc:
        logger.warning(
            "empresas.auto_match.eva_db_failed empresa=%s name=%r: %s",
            empresa.id,
            normalized,
            exc,
            exc_info=True,
        )
        return  # Don't mark attempted; will retry next page load.

    empresa.auto_match_attempted = True
    if len(matches) == 1:
        candidate_id = matches[0]
        # Guard: the target Eva account may already be linked to a different
        # empresa. The Phase 2 unique partial index enforces this at the DB
        # layer; we mirror the check here so auto-match skips gracefully
        # (no 409 surfaced to the operator) and the operator can dedupe
        # manually.
        existing = await db.execute(
            select(Empresa.id).where(
                Empresa.eva_account_id == candidate_id,
                Empresa.id != empresa.id,
            ).limit(1)
        )
        if existing.scalar_one_or_none():
            logger.info(
                "empresas.auto_match.skip_collision empresa=%s name=%r eva_account_id=%s",
                empresa.id, normalized, candidate_id,
            )
            return
        empresa.eva_account_id = candidate_id
        logger.info(
            "empresas.auto_match.linked empresa=%s name=%r → eva_account_id=%s",
            empresa.id,
            normalized,
            candidate_id,
        )
    elif len(matches) > 1:
        logger.info(
            "empresas.auto_match.ambiguous empresa=%s name=%r matches=%d",
            empresa.id,
            normalized,
            len(matches),
        )


async def _compute_health_for_empresas(
    eva_db: AsyncSession | None,
    empresa_account_ids: dict[uuid.UUID, uuid.UUID | None],
) -> dict[uuid.UUID, dict]:
    """Return a dict mapping empresa_id → health dict.

    Each value is a dict shaped like ``EmpresaHealth`` with:
        - status: "healthy" | "unhealthy" | "unknown" | "not_linked"
        - unhealthy_count: int
        - linked_account_name: str | None
        - messenger: {present, healthy, count}
        - instagram: {present, healthy, count}
        - whatsapp: {present, healthy, count}
    """
    empty_channel = {"present": False, "healthy": False, "count": 0}

    def _empty_health(status: str) -> dict:
        return {
            "status": status,
            "unhealthy_count": 0,
            "linked_account_name": None,
            "messenger": dict(empty_channel),
            "instagram": dict(empty_channel),
            "whatsapp": dict(empty_channel),
        }

    out: dict[uuid.UUID, dict] = {}

    # Partition: not_linked vs linked
    linked_account_ids: set[uuid.UUID] = set()
    for emp_id, acc_id in empresa_account_ids.items():
        if acc_id is None:
            out[emp_id] = _empty_health("not_linked")
        else:
            linked_account_ids.add(acc_id)

    if not linked_account_ids:
        return out

    if eva_db is None:
        # Can't query Eva — every linked empresa is "unknown".
        for emp_id, acc_id in empresa_account_ids.items():
            if acc_id is not None:
                out[emp_id] = _empty_health("unknown")
        return out

    try:
        # Resolve account names so the frontend can show
        # "Eva: Lucky Intelligence" without a follow-up request.
        accounts_result = await eva_db.execute(
            select(EvaAccount.id, EvaAccount.name).where(
                EvaAccount.id.in_(linked_account_ids)
            )
        )
        account_names: dict[uuid.UUID, str] = {
            row.id: row.name for row in accounts_result.all()
        }

        msg_result = await eva_db.execute(
            select(EvaMessengerChannel.is_healthy, EvaAgent.account_id)
            .join(EvaAgent, EvaAgent.id == EvaMessengerChannel.agent_id)
            .where(
                EvaAgent.account_id.in_(linked_account_ids),
                EvaMessengerChannel.is_active.is_(True),
            )
        )
        msg_rows = list(msg_result.all())

        ig_result = await eva_db.execute(
            select(EvaInstagramChannel.is_healthy, EvaAgent.account_id)
            .join(EvaAgent, EvaAgent.id == EvaInstagramChannel.agent_id)
            .where(
                EvaAgent.account_id.in_(linked_account_ids),
                EvaInstagramChannel.is_active.is_(True),
            )
        )
        ig_rows = list(ig_result.all())

        # WhatsApp uses ``is_message_ready`` (the WhatsApp equivalent
        # of ``is_healthy``). NULL ``is_active`` is treated as inactive
        # because the upstream column has no NOT NULL constraint.
        wa_result = await eva_db.execute(
            select(
                EvaWhatsAppChannel.is_message_ready,
                EvaAgent.account_id,
            )
            .join(EvaAgent, EvaAgent.id == EvaWhatsAppChannel.agent_id)
            .where(
                EvaAgent.account_id.in_(linked_account_ids),
                EvaWhatsAppChannel.is_active.is_(True),
            )
        )
        wa_rows = list(wa_result.all())
    except Exception as exc:
        logger.warning(
            "empresas.health.eva_db_failed: %s",
            exc,
            exc_info=True,
        )
        for emp_id, acc_id in empresa_account_ids.items():
            if acc_id is not None:
                out[emp_id] = _empty_health("unknown")
        return out

    # Aggregate per account_id, per channel type.
    def _empty_bucket() -> dict[str, int]:
        return {
            "messenger_total": 0,
            "messenger_unhealthy": 0,
            "instagram_total": 0,
            "instagram_unhealthy": 0,
            "whatsapp_total": 0,
            "whatsapp_unhealthy": 0,
        }

    per_account: dict[uuid.UUID, dict[str, int]] = {
        acc: _empty_bucket() for acc in linked_account_ids
    }
    for is_healthy, account_id in msg_rows:
        bucket = per_account.setdefault(account_id, _empty_bucket())
        bucket["messenger_total"] += 1
        if not is_healthy:
            bucket["messenger_unhealthy"] += 1
    for is_healthy, account_id in ig_rows:
        bucket = per_account.setdefault(account_id, _empty_bucket())
        bucket["instagram_total"] += 1
        if not is_healthy:
            bucket["instagram_unhealthy"] += 1
    for is_message_ready, account_id in wa_rows:
        bucket = per_account.setdefault(account_id, _empty_bucket())
        bucket["whatsapp_total"] += 1
        if not is_message_ready:
            bucket["whatsapp_unhealthy"] += 1

    for emp_id, acc_id in empresa_account_ids.items():
        if acc_id is None:
            continue
        bucket = per_account[acc_id]
        msg_total = bucket["messenger_total"]
        msg_bad = bucket["messenger_unhealthy"]
        ig_total = bucket["instagram_total"]
        ig_bad = bucket["instagram_unhealthy"]
        wa_total = bucket["whatsapp_total"]
        wa_bad = bucket["whatsapp_unhealthy"]
        unhealthy_count = msg_bad + ig_bad + wa_bad
        if msg_total + ig_total + wa_total == 0:
            # No active channels at all → still "healthy" (nothing to break)
            status = "healthy"
        elif unhealthy_count > 0:
            status = "unhealthy"
        else:
            status = "healthy"
        out[emp_id] = {
            "status": status,
            "unhealthy_count": unhealthy_count,
            "linked_account_name": account_names.get(acc_id),
            "messenger": {
                "present": msg_total > 0,
                "healthy": msg_total > 0 and msg_bad == 0,
                "count": msg_total,
            },
            "instagram": {
                "present": ig_total > 0,
                "healthy": ig_total > 0 and ig_bad == 0,
                "count": ig_total,
            },
            "whatsapp": {
                "present": wa_total > 0,
                "healthy": wa_total > 0 and wa_bad == 0,
                "count": wa_total,
            },
        }
    return out


def _sync_empresa_from_eva_account(empresa: Empresa, account: EvaAccount) -> None:
    """Copy safe account/billing cache fields onto the ERP empresa row."""
    empresa.eva_account_id = account.id
    empresa.auto_match_attempted = True
    empresa.stripe_customer_id = getattr(account, "stripe_customer_id", None)
    empresa.stripe_subscription_id = getattr(account, "stripe_subscription_id", None)
    subscription_status = getattr(account, "subscription_status", None)
    empresa.subscription_status = str(subscription_status).lower() if subscription_status else None
    empresa.current_period_end = getattr(account, "current_period_end", None)
    billing_interval = getattr(account, "billing_interval", None)
    empresa.billing_interval = str(billing_interval).lower() if billing_interval else "monthly"


def _record_eva_account_link(
    db: AsyncSession,
    empresa: Empresa,
    account: EvaAccount,
    changed_by: uuid.UUID | None,
) -> None:
    """Mutate the empresa to point at ``account`` and append history."""
    old_account_id = empresa.eva_account_id
    _sync_empresa_from_eva_account(empresa, account)
    if old_account_id != account.id:
        empresa.version = (empresa.version or 0) + 1
        db.add(
            EmpresaHistory(
                empresa_id=empresa.id,
                field_changed="eva_account_id",
                old_value=str(old_account_id) if old_account_id else None,
                new_value=str(account.id),
                changed_by=changed_by,
            )
        )


async def _ensure_account_not_already_linked(
    db: AsyncSession,
    account_id: uuid.UUID,
    excluding_empresa_id: uuid.UUID | None,
) -> None:
    """Raise 409 if another empresa already points at ``account_id``."""
    q = select(Empresa.id).where(Empresa.eva_account_id == account_id)
    if excluding_empresa_id is not None:
        q = q.where(Empresa.id != excluding_empresa_id)
    duplicate = await db.execute(q.limit(1))
    if duplicate.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail={
                "reason": "already_linked",
                "message": "Esta cuenta de Eva ya esta vinculada a otra empresa.",
            },
        )


async def _load_empresa_for_link(
    db: AsyncSession,
    empresa_id: uuid.UUID,
    expected_version: int | None,
) -> Empresa:
    """Load empresa with row lock + optimistic-version check for link/create flows."""
    result = await db.execute(
        select(Empresa)
        .where(Empresa.id == empresa_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    empresa = result.scalar_one_or_none()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa not found")
    if expected_version is not None and expected_version != empresa.version:
        raise HTTPException(
            status_code=409,
            detail={
                "reason": "OptimisticLockMismatch",
                "message": "Another user changed this empresa — reload.",
                "server_version": empresa.version,
            },
        )
    return empresa


async def _validate_link_preconditions(
    db: AsyncSession,
    empresa: Empresa,
    new_account_id: uuid.UUID | None,
) -> None:
    """Reject link attempts that would violate uniqueness or business rules.

    Runs BEFORE any external side effects (Supabase user create, Stripe
    setup, etc) so callers like create-account-for-empresa can fail
    fast on already-linked or already-operativo empresas without
    creating orphaned auth users.
    """
    if empresa.eva_account_id and (new_account_id is None or empresa.eva_account_id != new_account_id):
        raise HTTPException(
            status_code=409,
            detail={
                "reason": "empresa_already_linked",
                "message": "Esta empresa ya esta vinculada a otra cuenta de Eva.",
            },
        )
    if new_account_id is not None:
        await _ensure_account_not_already_linked(db, new_account_id, excluding_empresa_id=empresa.id)


async def link_empresa_to_eva_account(
    db: AsyncSession,
    eva_db: AsyncSession,
    empresa_id: uuid.UUID,
    account_id: uuid.UUID,
    changed_by: uuid.UUID | None = None,
    expected_version: int | None = None,
) -> Empresa:
    """Link an ERP empresa to an Eva account; refresh local billing cache."""
    empresa = await _load_empresa_for_link(db, empresa_id, expected_version)
    await _validate_link_preconditions(db, empresa, account_id)

    account_result = await eva_db.execute(select(EvaAccount).where(EvaAccount.id == account_id))
    account = account_result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Eva account not found")
    if not getattr(account, "is_active", True):
        raise HTTPException(
            status_code=409,
            detail={
                "reason": "account_inactive",
                "message": "No se puede vincular una cuenta de Eva inactiva.",
            },
        )

    _record_eva_account_link(db, empresa, account, changed_by)
    _enforce_business_rules(
        lifecycle_stage=empresa.lifecycle_stage,
        eva_account_id=empresa.eva_account_id,
        subscription_status=empresa.subscription_status,
        expected_close_date=empresa.expected_close_date,
        grandfathered=empresa.grandfathered,
        check_operativo=True,
        check_close_date=False,
    )
    db.add(empresa)
    await db.flush()
    await db.refresh(empresa, attribute_names=["items"])
    return empresa


@router.get("")
async def list_empresas(
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    eva_db: AsyncSession | None = Depends(get_optional_eva_db),
):
    q = (
        select(
            Empresa.id,
            Empresa.name,
            Empresa.logo_url,
            Empresa.status,
            Empresa.ball_on,
            Empresa.summary_note,
            Empresa.monthly_amount,
            Empresa.payment_day,
            Empresa.last_paid_date,
            Empresa.eva_account_id,
            Empresa.auto_match_attempted,
            Empresa.subscription_status,
            Empresa.current_period_end,
            Empresa.person_type,
            Empresa.rfc,
            func.count(EmpresaItem.id).label("item_count"),
            func.count(case((EmpresaItem.done == False, EmpresaItem.id))).label("pending_count"),
        )
        .outerjoin(EmpresaItem, EmpresaItem.empresa_id == Empresa.id)
        .group_by(Empresa.id)
        .order_by(Empresa.name)
    )
    if search:
        q = q.where(Empresa.name.ilike(f"%{search}%"))
    result = await db.execute(q)
    rows = result.all()

    # Fetch pending items for all empresas in one query
    empresa_ids = [r.id for r in rows]
    pending_items_map: dict[uuid.UUID, list[dict]] = {eid: [] for eid in empresa_ids}
    next_action_map: dict[uuid.UUID, dict | None] = {eid: None for eid in empresa_ids}
    overdue_count_map: dict[uuid.UUID, int] = {eid: 0 for eid in empresa_ids}

    if empresa_ids:
        # Schedulable date for ordering: earliest of (start_at, due_at,
        # reminder_at). Items without any date sink to the bottom.
        schedule_at = func.coalesce(EmpresaItem.start_at, EmpresaItem.due_at, EmpresaItem.reminder_at)
        items_q = (
            select(
                EmpresaItem.id,
                EmpresaItem.empresa_id,
                EmpresaItem.title,
                EmpresaItem.kind,
                EmpresaItem.due_at,
                EmpresaItem.start_at,
                EmpresaItem.completed_at,
                schedule_at.label("schedule_at"),
            )
            .where(
                EmpresaItem.empresa_id.in_(empresa_ids),
                EmpresaItem.done == False,
                EmpresaItem.kind != "note",
            )
            .order_by(schedule_at.asc().nulls_last(), EmpresaItem.created_at.asc())
        )
        items_result = await db.execute(items_q)
        now = datetime.now(timezone.utc)
        for item in items_result.all():
            payload = {
                "id": str(item.id),
                "title": item.title,
                "kind": item.kind or "todo",
                "due_at": item.due_at.isoformat() if item.due_at else None,
                "start_at": item.start_at.isoformat() if item.start_at else None,
                "completed_at": item.completed_at.isoformat() if item.completed_at else None,
            }
            pending_items_map[item.empresa_id].append(payload)
            # First (earliest scheduled) item is the next action.
            if next_action_map[item.empresa_id] is None and item.schedule_at is not None:
                next_action_map[item.empresa_id] = payload
            if item.due_at is not None and item.due_at < now:
                overdue_count_map[item.empresa_id] += 1
        # Fallback: if no item had a schedule_at, the first undated item
        # becomes the next action so the card can still hint at "do this
        # next" instead of going blank.
        for emp_id, items in pending_items_map.items():
            if next_action_map[emp_id] is None and items:
                next_action_map[emp_id] = items[0]

    # Lazy auto-match: for any empresa whose ``auto_match_attempted``
    # flag is False, try to link it to an Eva account by name. Only
    # runs when ``eva_db`` is configured AND the empresa hasn't been
    # checked yet — so it's a one-time backfill spread across page
    # loads, not a per-request cost.
    needs_auto_match = [
        row for row in rows if not row.auto_match_attempted
    ]
    if needs_auto_match and eva_db is not None:
        # We need to load the actual ORM objects to mutate them. Cheap
        # because the count is small (only un-attempted empresas).
        for_load_ids = [row.id for row in needs_auto_match]
        load_result = await db.execute(
            select(Empresa).where(Empresa.id.in_(for_load_ids))
        )
        empresas_to_match = {emp.id: emp for emp in load_result.scalars().all()}
        for emp in empresas_to_match.values():
            await _attempt_auto_match(db, eva_db, emp)
        await db.flush()
        # Refresh the row data we'll return so eva_account_id reflects
        # any new links.
        refreshed_account_ids = {emp.id: emp.eva_account_id for emp in empresas_to_match.values()}
    else:
        refreshed_account_ids = {}

    # Build the empresa→eva_account_id map for the health computation
    # (using refreshed values where applicable).
    empresa_account_ids: dict[uuid.UUID, uuid.UUID | None] = {}
    for r in rows:
        empresa_account_ids[r.id] = refreshed_account_ids.get(r.id, r.eva_account_id)

    health_map = await _compute_health_for_empresas(eva_db, empresa_account_ids)

    return [
        {
            "id": r.id,
            "name": r.name,
            "logo_url": r.logo_url,
            "status": r.status,
            "ball_on": r.ball_on,
            "summary_note": r.summary_note,
            "monthly_amount": float(r.monthly_amount) if r.monthly_amount is not None else None,
            "payment_day": r.payment_day,
            "last_paid_date": r.last_paid_date.isoformat() if r.last_paid_date else None,
            "eva_account_id": str(empresa_account_ids[r.id]) if empresa_account_ids[r.id] else None,
            "auto_match_attempted": r.auto_match_attempted or (r.id in refreshed_account_ids),
            "subscription_status": r.subscription_status,
            "current_period_end": r.current_period_end.isoformat() if r.current_period_end else None,
            "person_type": r.person_type,
            "rfc": r.rfc,
            "item_count": r.item_count,
            "pending_count": r.pending_count,
            "pending_items": pending_items_map.get(r.id, []),
            "next_action": next_action_map.get(r.id),
            "overdue_count": overdue_count_map.get(r.id, 0),
            "health": health_map.get(
                r.id,
                {
                    "status": "not_linked",
                    "unhealthy_count": 0,
                    "linked_account_name": None,
                    "messenger": {"present": False, "healthy": False, "count": 0},
                    "instagram": {"present": False, "healthy": False, "count": 0},
                    "whatsapp": {"present": False, "healthy": False, "count": 0},
                },
            ),
        }
        for r in rows
    ]


def _enforce_business_rules(
    *,
    lifecycle_stage: str | None,
    eva_account_id: uuid.UUID | None,
    subscription_status: str | None,
    expected_close_date,
    grandfathered: bool = False,
    check_operativo: bool = True,
    check_close_date: bool = True,
) -> None:
    """Raise HTTPException if the proposed state violates business rules.

    - ``operativo`` requires a linked Eva account with an active subscription
      (grandfathered rows are exempt).
    - Pipeline stages interesado/demo/negociacion require ``expected_close_date``.

    Callers may disable individual checks when the PATCH isn't actually
    mutating the inputs for that rule — e.g., an operator editing only
    ``expected_close_date`` on an already-operativo empresa shouldn't be
    blocked by the operativo invariant (they're not changing the stage).
    """
    if check_operativo and lifecycle_stage == "operativo" and not grandfathered:
        if eva_account_id is None or subscription_status != "active":
            raise HTTPException(
                status_code=409,
                detail={
                    "reason": "OperativoRequiresActiveSubscription",
                    "message": "Operativo requires linked Eva account with active subscription.",
                },
            )
    if check_close_date and lifecycle_stage in STAGES_REQUIRING_CLOSE_DATE and not expected_close_date:
        raise HTTPException(
            status_code=400,
            detail={
                "reason": "ExpectedCloseDateRequired",
                "message": "Stages interesado/demo/negociacion require expected_close_date.",
            },
        )


# ── Calendar (must be registered BEFORE /{empresa_id}) ──────────────


def _coerce_range_end(end: date | datetime) -> datetime:
    """Return an inclusive upper bound covering the entire ``end`` day."""
    if isinstance(end, datetime):
        return end if end.tzinfo else end.replace(tzinfo=timezone.utc)
    return datetime.combine(end, time.max, tzinfo=timezone.utc)


def _coerce_range_start(start: date | datetime) -> datetime:
    if isinstance(start, datetime):
        return start if start.tzinfo else start.replace(tzinfo=timezone.utc)
    return datetime.combine(start, time.min, tzinfo=timezone.utc)


@router.get("/calendar", response_model=list[EmpresaCalendarItemResponse])
async def empresa_calendar(
    range_from: datetime | None = Query(default=None, alias="from"),
    range_to: datetime | None = Query(default=None, alias="to"),
    empresa_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Calendar events for follow-ups across all empresas.

    Sources:
    - ``empresa_items`` rows whose ``kind`` is ``event`` or ``todo``
      (todos with a due date show as deadlines on the calendar).
    - Existing ``meetings`` rows linked via ``empresa_id`` (so historical
      visits/calls are preserved when the Meetings page goes away).
    - Recent ``empresa_interactions`` so prior outreach surfaces in the
      timeline view.
    """
    start_at = _coerce_range_start(range_from) if range_from else None
    end_at = _coerce_range_end(range_to) if range_to else None
    if start_at and end_at and end_at < start_at:
        raise HTTPException(status_code=400, detail="`to` must be >= `from`.")

    item_q = (
        select(EmpresaItem, Empresa.name.label("empresa_name"))
        .join(Empresa, Empresa.id == EmpresaItem.empresa_id)
        .where(EmpresaItem.kind.in_(["event", "todo", "outreach"]))
        .order_by(
            func.coalesce(EmpresaItem.start_at, EmpresaItem.due_at, EmpresaItem.reminder_at).asc().nulls_last(),
            EmpresaItem.created_at.asc(),
        )
    )
    if empresa_id is not None:
        item_q = item_q.where(EmpresaItem.empresa_id == empresa_id)
    if start_at is not None:
        item_q = item_q.where(
            or_(
                EmpresaItem.start_at >= start_at,
                EmpresaItem.due_at >= start_at,
                EmpresaItem.reminder_at >= start_at,
                EmpresaItem.end_at >= start_at,
            )
        )
    if end_at is not None:
        item_q = item_q.where(
            or_(
                EmpresaItem.start_at <= end_at,
                EmpresaItem.due_at <= end_at,
                EmpresaItem.reminder_at <= end_at,
            )
        )
    item_rows = await db.execute(item_q)

    out: list[EmpresaCalendarItemResponse] = []
    for item, empresa_name in item_rows.all():
        out.append(
            EmpresaCalendarItemResponse(
                id=item.id,
                empresa_id=item.empresa_id,
                empresa_name=empresa_name,
                source="item",
                kind=item.kind or "todo",
                title=item.title,
                description=item.description,
                start_at=item.start_at,
                end_at=item.end_at,
                due_at=item.due_at,
                reminder_at=item.reminder_at,
                contact_method=item.contact_method,
                completed_at=item.completed_at,
                assigned_to=item.assigned_to,
            )
        )

    # Existing meetings linked to empresas — surface them so historical
    # visits/calls keep showing up after we retire the Meetings page.
    # We use a raw text query here to avoid pulling in the whole
    # meetings ORM module (which is being unmounted from /api).
    from sqlalchemy import text as _text

    meeting_sql = """
        SELECT m.id, m.title, m.date, m.duration_minutes, m.notes_markdown,
               m.empresa_id, e.name AS empresa_name
        FROM meetings m
        JOIN empresas e ON e.id = m.empresa_id
        WHERE m.empresa_id IS NOT NULL
        {empresa_filter}
        {start_filter}
        {end_filter}
        ORDER BY m.date ASC
    """
    params: dict[str, object] = {}
    empresa_filter = ""
    start_filter = ""
    end_filter = ""
    if empresa_id is not None:
        empresa_filter = "AND m.empresa_id = :empresa_id"
        params["empresa_id"] = empresa_id
    if start_at is not None:
        start_filter = "AND m.date >= :start_at"
        params["start_at"] = start_at
    if end_at is not None:
        end_filter = "AND m.date <= :end_at"
        params["end_at"] = end_at
    try:
        meeting_rows = await db.execute(
            _text(meeting_sql.format(empresa_filter=empresa_filter, start_filter=start_filter, end_filter=end_filter)),
            params,
        )
        for row in meeting_rows.all():
            duration = row.duration_minutes or 0
            from datetime import timedelta

            end_at_meeting = row.date + timedelta(minutes=duration) if row.date and duration else None
            out.append(
                EmpresaCalendarItemResponse(
                    id=row.id,
                    empresa_id=row.empresa_id,
                    empresa_name=row.empresa_name,
                    source="meeting",
                    kind="event",
                    title=row.title,
                    description=row.notes_markdown,
                    start_at=row.date,
                    end_at=end_at_meeting,
                    due_at=None,
                    reminder_at=None,
                    contact_method="meeting",
                    completed_at=None,
                    assigned_to=None,
                )
            )
    except Exception as exc:
        # If the meetings table is gone or read fails, log and continue:
        # the items query is the source of truth for new behavior, and
        # we don't want a meetings outage to break the calendar.
        logger.warning("empresa_calendar.meetings_query_failed: %s", exc, exc_info=True)

    interaction_q = (
        select(EmpresaInteraction, Empresa.name.label("empresa_name"))
        .join(Empresa, Empresa.id == EmpresaInteraction.empresa_id)
    )
    if empresa_id is not None:
        interaction_q = interaction_q.where(EmpresaInteraction.empresa_id == empresa_id)
    if start_at is not None:
        interaction_q = interaction_q.where(EmpresaInteraction.date >= start_at.date())
    if end_at is not None:
        interaction_q = interaction_q.where(EmpresaInteraction.date <= end_at.date())
    interaction_rows = await db.execute(interaction_q.order_by(EmpresaInteraction.date.desc()).limit(500))
    for interaction, empresa_name in interaction_rows.all():
        ts = datetime.combine(interaction.date, time.min, tzinfo=timezone.utc)
        out.append(
            EmpresaCalendarItemResponse(
                id=interaction.id,
                empresa_id=interaction.empresa_id,
                empresa_name=empresa_name,
                source="interaction",
                kind="outreach",
                title=interaction.summary[:120] if interaction.summary else "(sin resumen)",
                description=interaction.summary,
                start_at=ts,
                end_at=None,
                due_at=None,
                reminder_at=None,
                contact_method=interaction.type,
                completed_at=ts,
                assigned_to=None,
            )
        )

    out.sort(
        key=lambda r: (
            r.start_at or r.due_at or r.reminder_at or datetime(1970, 1, 1, tzinfo=timezone.utc),
            r.title,
        )
    )
    return out


@router.post("", response_model=EmpresaResponse, status_code=201)
async def create_empresa(
    data: EmpresaCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _enforce_business_rules(
        lifecycle_stage=data.lifecycle_stage,
        eva_account_id=data.eva_account_id,
        subscription_status=None,
        expected_close_date=data.expected_close_date,
        grandfathered=False,
    )
    empresa = Empresa(**data.model_dump(), created_by=user.id)
    db.add(empresa)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        if "empresas_eva_account_id_uniq" in str(exc.orig):
            raise HTTPException(
                status_code=409,
                detail={"reason": "already_linked", "message": "Esta cuenta de Eva ya esta vinculada a otra empresa."},
            ) from exc
        raise
    await db.refresh(empresa, attribute_names=["items"])
    return empresa


@router.get("/{empresa_id}", response_model=EmpresaResponse)
async def get_empresa(
    empresa_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Empresa).where(Empresa.id == empresa_id).options(selectinload(Empresa.items))
    )
    empresa = result.scalar_one_or_none()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa not found")
    return empresa


_BILLING_FIELDS_REQUIRING_STRIPE = {"monthly_amount", "billing_interval", "payment_day"}


@router.patch("/{empresa_id}", response_model=EmpresaResponse)
async def update_empresa(
    empresa_id: uuid.UUID,
    data: EmpresaUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    if_match: str | None = Header(default=None, alias="If-Match"),
):
    result = await db.execute(
        select(Empresa).where(Empresa.id == empresa_id).options(selectinload(Empresa.items))
    )
    empresa = result.scalar_one_or_none()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa not found")

    update_data = data.model_dump(exclude_unset=True)

    # Optimistic lock — PATCH must supply If-Match: <version> unless the payload
    # is empty (no-op). Mismatch returns 409 so the client can refetch.
    if update_data:
        if if_match is None:
            raise HTTPException(
                status_code=400,
                detail={"reason": "MissingIfMatchHeader", "message": "If-Match header required on PATCH."},
            )
        try:
            client_version = int(if_match.strip().strip('"'))
        except ValueError:
            raise HTTPException(status_code=400, detail="If-Match header must be an integer version.")
        if client_version != empresa.version:
            raise HTTPException(
                status_code=409,
                detail={
                    "reason": "OptimisticLockMismatch",
                    "message": "Another user changed this empresa — reload.",
                    "server_version": empresa.version,
                },
            )

    # Billing-field changes when linked must go through /subscription/apply
    # so Stripe stays in sync. Non-linked empresas can edit freely.
    touches_billing = _BILLING_FIELDS_REQUIRING_STRIPE & update_data.keys()
    if touches_billing and empresa.eva_account_id is not None:
        raise HTTPException(
            status_code=400,
            detail={
                "reason": "UseSubscriptionApplyEndpoint",
                "message": "Billing field changes on linked empresas must use /subscription/apply.",
            },
        )

    # Business-rule validation on post-merge state, scoped per-rule.
    # - Operativo invariant fires only when stage or link is being mutated
    #   (editing close_date on an already-operativo empresa does not trigger).
    # - Close-date invariant fires only when stage or close_date is being
    #   mutated (editing link alone on a demo empresa with missing close_date
    #   does not retroactively 400).
    stage_changing = "lifecycle_stage" in update_data
    link_changing = "eva_account_id" in update_data
    close_changing = "expected_close_date" in update_data
    if stage_changing or link_changing or close_changing:
        proposed_stage = update_data.get("lifecycle_stage", empresa.lifecycle_stage)
        proposed_eva_account_id = update_data.get("eva_account_id", empresa.eva_account_id)
        proposed_close_date = update_data.get("expected_close_date", empresa.expected_close_date)
        _enforce_business_rules(
            lifecycle_stage=proposed_stage,
            eva_account_id=proposed_eva_account_id,
            subscription_status=empresa.subscription_status,
            expected_close_date=proposed_close_date,
            grandfathered=empresa.grandfathered,
            check_operativo=stage_changing or link_changing,
            check_close_date=stage_changing or close_changing,
        )

    # Record history for tracked fields.
    for field in TRACKED_FIELDS:
        if field in update_data:
            old_value = getattr(empresa, field)
            new_value = update_data[field]
            if old_value != new_value:
                history = EmpresaHistory(
                    empresa_id=empresa.id,
                    field_changed=field,
                    old_value=str(old_value) if old_value is not None else None,
                    new_value=str(new_value) if new_value is not None else None,
                    changed_by=user.id,
                )
                db.add(history)

    # Capture the pre-update ZIP so we can detect a cedular-relevant change.
    old_zip = empresa.fiscal_postal_code

    for field, value in update_data.items():
        setattr(empresa, field, value)

    # Increment version if anything actually changed (even non-tracked fields).
    if update_data:
        empresa.version = (empresa.version or 0) + 1

    db.add(empresa)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        if "empresas_eva_account_id_uniq" in str(exc.orig):
            raise HTTPException(
                status_code=409,
                detail={"reason": "already_linked", "message": "Esta cuenta de Eva ya esta vinculada a otra empresa."},
            ) from exc
        raise

    # Auto-reprice the Stripe sub when ZIP changes flip the cedular rule
    # (gated on settings.enable_cedular_auto_reprice — off by default).
    if "fiscal_postal_code" in update_data:
        from src.empresas.billing_service import maybe_reprice_subscription_for_zip_change

        try:
            await maybe_reprice_subscription_for_zip_change(
                empresa,
                old_zip=old_zip,
                new_zip=empresa.fiscal_postal_code,
            )
        except Exception:  # pragma: no cover - defensive
            # Never block the PATCH on Stripe issues; just log.
            import logging
            logging.getLogger(__name__).exception(
                "cedular_auto_reprice failed for empresa %s", empresa.id
            )

    return empresa


@router.delete("/{empresa_id}", status_code=204)
async def delete_empresa(
    empresa_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Empresa).where(Empresa.id == empresa_id))
    empresa = result.scalar_one_or_none()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa not found")
    # Block DELETE when the linked subscription is still active. Orphaning
    # the sub would break webhook empresa_id resolution and leave CFDIs
    # stamping against a non-existent empresa. Operator must cancel first
    # via the Inactivo drag (which calls /subscription/cancel).
    if empresa.subscription_status == "active":
        raise HTTPException(
            status_code=409,
            detail={
                "reason": "ActiveSubscription",
                "message": "Cancela la suscripcion antes de eliminar.",
            },
        )
    await db.delete(empresa)


# ── History ────────────────────────────────────────────────────────


@router.get("/{empresa_id}/history")
async def get_empresa_history(
    empresa_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Verify empresa exists
    result = await db.execute(select(Empresa.id).where(Empresa.id == empresa_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Empresa not found")

    q = (
        select(
            EmpresaHistory.id,
            EmpresaHistory.field_changed,
            EmpresaHistory.old_value,
            EmpresaHistory.new_value,
            EmpresaHistory.changed_by,
            EmpresaHistory.changed_at,
            User.name.label("changed_by_name"),
        )
        .outerjoin(User, User.id == EmpresaHistory.changed_by)
        .where(EmpresaHistory.empresa_id == empresa_id)
        .order_by(EmpresaHistory.changed_at.desc())
    )
    result = await db.execute(q)
    rows = result.all()
    return [
        {
            "id": r.id,
            "field_changed": r.field_changed,
            "old_value": r.old_value,
            "new_value": r.new_value,
            "changed_by": r.changed_by,
            "changed_by_name": r.changed_by_name,
            "changed_at": r.changed_at,
        }
        for r in rows
    ]


# ── Items ──────────────────────────────────────────────────────────


_EVENT_KINDS_REQUIRING_DATE = {"event"}


def _validate_item_window(payload: dict) -> None:
    """Reject events without a start window and end-before-start ranges."""
    kind = payload.get("kind")
    if kind in _EVENT_KINDS_REQUIRING_DATE:
        if payload.get("start_at") is None and payload.get("due_at") is None:
            raise HTTPException(
                status_code=400,
                detail={
                    "reason": "EventDateRequired",
                    "message": "Eventos requieren start_at o due_at.",
                },
            )
    start_at = payload.get("start_at")
    end_at = payload.get("end_at")
    if start_at and end_at and end_at < start_at:
        raise HTTPException(
            status_code=400,
            detail={
                "reason": "InvalidDateWindow",
                "message": "end_at debe ser >= start_at.",
            },
        )


@router.post("/{empresa_id}/items", response_model=EmpresaItemResponse, status_code=201)
async def create_item(
    empresa_id: uuid.UUID,
    data: EmpresaItemCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Empresa.id).where(Empresa.id == empresa_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Empresa not found")

    payload = data.model_dump()
    _validate_item_window(payload)

    item = EmpresaItem(
        empresa_id=empresa_id,
        created_by=user.id,
        **payload,
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item


@router.patch("/items/{item_id}", response_model=EmpresaItemResponse)
async def update_item(
    item_id: uuid.UUID,
    data: EmpresaItemUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(EmpresaItem).where(EmpresaItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    update_data = data.model_dump(exclude_unset=True)
    # Re-validate the merged window so partial PATCHes don't sneak past
    # the create-time guard.
    merged = {
        "kind": update_data.get("kind", item.kind),
        "start_at": update_data.get("start_at", item.start_at),
        "due_at": update_data.get("due_at", item.due_at),
        "end_at": update_data.get("end_at", item.end_at),
    }
    _validate_item_window(merged)

    if "done" in update_data:
        new_done = bool(update_data["done"])
        if new_done and not item.done:
            item.completed_at = datetime.now(timezone.utc)
        elif not new_done:
            item.completed_at = None

    for field, value in update_data.items():
        setattr(item, field, value)

    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item


@router.patch("/items/{item_id}/toggle", response_model=EmpresaItemResponse)
async def toggle_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(EmpresaItem).where(EmpresaItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    item.done = not item.done
    item.completed_at = datetime.now(timezone.utc) if item.done else None
    db.add(item)
    await db.flush()
    await db.refresh(item)
    return item


@router.delete("/items/{item_id}", status_code=204)
async def delete_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(EmpresaItem).where(EmpresaItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    await db.delete(item)


# ── Interactions (legacy + new outreach surface) ────────────────────


@router.get("/{empresa_id}/interactions", response_model=list[EmpresaInteractionResponse])
async def list_empresa_interactions(
    empresa_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    exists = await db.execute(select(Empresa.id).where(Empresa.id == empresa_id))
    if not exists.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Empresa not found")
    rows = await db.execute(
        select(EmpresaInteraction)
        .where(EmpresaInteraction.empresa_id == empresa_id)
        .order_by(EmpresaInteraction.date.desc(), EmpresaInteraction.created_at.desc())
    )
    return list(rows.scalars().all())


@router.post("/{empresa_id}/interactions", response_model=EmpresaInteractionResponse, status_code=201)
async def create_empresa_interaction(
    empresa_id: uuid.UUID,
    data: EmpresaInteractionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    exists = await db.execute(select(Empresa.id).where(Empresa.id == empresa_id))
    if not exists.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Empresa not found")
    interaction = EmpresaInteraction(
        empresa_id=empresa_id,
        type=data.type,
        summary=data.summary,
        date=data.date,
        created_by=user.id,
    )
    db.add(interaction)
    await db.flush()
    await db.refresh(interaction)
    return interaction


# ── Eva account link / create from empresa ──────────────────────────


@router.post("/{empresa_id}/link-eva-account", response_model=EmpresaResponse)
async def link_eva_account_endpoint(
    empresa_id: uuid.UUID,
    payload: LinkEvaAccountRequest,
    db: AsyncSession = Depends(get_db),
    eva_db: AsyncSession = Depends(get_eva_db),
    user: User = Depends(get_current_user),
    if_match: str | None = Header(default=None, alias="If-Match"),
):
    expected_version: int | None = None
    if if_match is not None:
        try:
            expected_version = int(if_match.strip().strip('"'))
        except ValueError:
            raise HTTPException(status_code=400, detail="If-Match header must be an integer version.")
    return await link_empresa_to_eva_account(
        db=db,
        eva_db=eva_db,
        empresa_id=empresa_id,
        account_id=payload.eva_account_id,
        changed_by=user.id,
        expected_version=expected_version,
    )


@router.delete("/{empresa_id}/link-eva-account", response_model=EmpresaResponse)
async def unlink_eva_account_endpoint(
    empresa_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    if_match: str | None = Header(default=None, alias="If-Match"),
):
    expected_version: int | None = None
    if if_match is not None:
        try:
            expected_version = int(if_match.strip().strip('"'))
        except ValueError:
            raise HTTPException(status_code=400, detail="If-Match header must be an integer version.")
    empresa = await _load_empresa_for_link(db, empresa_id, expected_version)
    if empresa.eva_account_id is None:
        return empresa
    if empresa.lifecycle_stage == "operativo" and not empresa.grandfathered:
        raise HTTPException(
            status_code=409,
            detail={
                "reason": "OperativoCannotUnlink",
                "message": "Mueve la empresa fuera de 'operativo' antes de desvincular la cuenta de Eva.",
            },
        )
    old_account_id = empresa.eva_account_id
    empresa.eva_account_id = None
    empresa.subscription_status = None
    empresa.current_period_end = None
    empresa.stripe_customer_id = None
    empresa.stripe_subscription_id = None
    empresa.version = (empresa.version or 0) + 1
    db.add(
        EmpresaHistory(
            empresa_id=empresa.id,
            field_changed="eva_account_id",
            old_value=str(old_account_id),
            new_value=None,
            changed_by=user.id,
        )
    )
    db.add(empresa)
    await db.flush()
    await db.refresh(empresa, attribute_names=["items"])
    return empresa


@router.post("/{empresa_id}/eva-account", response_model=EvaAccountProvisionResponse, status_code=201)
async def create_eva_account_for_empresa(
    empresa_id: uuid.UUID,
    payload: CreateEvaAccountForEmpresaRequest,
    db: AsyncSession = Depends(get_db),
    eva_db: AsyncSession = Depends(get_eva_db),
    user: User = Depends(get_current_user),
):
    """Create a fresh Eva account from a company card.

    Pre-validates the empresa link state BEFORE invoking Supabase. If
    the empresa is already linked, or if creating a fresh account would
    violate the operativo invariant (operativo empresas must have an
    active subscription, which a brand-new account doesn't yet), we
    409 here so we never create an orphaned auth user.
    """
    empresa = await _load_empresa_for_link(db, empresa_id, expected_version=None)
    await _validate_link_preconditions(db, empresa, new_account_id=None)
    # Fresh account has no subscription yet; if the empresa is already
    # operativo (and not grandfathered), the link would immediately
    # violate the active-subscription rule. Refuse before Supabase.
    if empresa.lifecycle_stage == "operativo" and not empresa.grandfathered:
        raise HTTPException(
            status_code=409,
            detail={
                "reason": "OperativoRequiresExistingSubscription",
                "message": (
                    "La empresa esta en 'operativo' pero la nueva cuenta de Eva "
                    "todavia no tiene suscripcion. Vincula una cuenta existente "
                    "o cambia la fase antes de crear una nueva."
                ),
            },
        )

    create_request = EvaAccountCreateRequest(
        name=payload.name or empresa.name,
        owner_email=payload.owner_email,
        owner_name=payload.owner_name or empresa.contact_name or "",
        account_type=payload.account_type,
        partner_id=payload.partner_id,
        plan_tier=payload.plan_tier,
        billing_cycle=payload.billing_cycle,
        facturapi_org_api_key=payload.facturapi_org_api_key,
        temporary_password=payload.temporary_password,
        send_setup_email=payload.send_setup_email,
        empresa_id=empresa_id,
    )

    # Defer to the existing accounts router so all provisioning logic
    # (Supabase user, EvaAccount + AccountUser rows, onboarding email)
    # stays single-source. The accounts route handles linking when
    # ``empresa_id`` is set.
    from src.eva_platform.router.accounts import create_account as create_account_handler

    return await create_account_handler(create_request, eva_db=eva_db, user=user, db=db)


# ── Billing endpoints ───────────────────────────────────────────────


@router.post("/{empresa_id}/preview-checkout", response_model=PreviewCheckoutResponse)
async def preview_checkout_endpoint(
    empresa_id: uuid.UUID,
    payload: PreviewCheckoutRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    empresa = await db.get(Empresa, empresa_id)
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa not found")

    from src.empresas.billing_service import preview_checkout

    try:
        quote = preview_checkout(empresa, amount_mxn=payload.amount_mxn)
        return PreviewCheckoutResponse(**quote)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{empresa_id}/checkout-link", response_model=CheckoutLinkResponse)
async def create_checkout_link(
    empresa_id: uuid.UUID,
    payload: CheckoutLinkRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    import secrets

    empresa = await db.get(Empresa, empresa_id)
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa not found")
    if empresa.stripe_subscription_id and empresa.subscription_status == "active":
        raise HTTPException(status_code=409, detail="Empresa already has an active subscription")

    from src.empresas.billing_service import preview_checkout

    try:
        quote = preview_checkout(empresa, amount_mxn=payload.amount_mxn)

        # Create PaymentLink record with short token
        token = secrets.token_urlsafe(16)  # ~22 chars, 128-bit entropy
        link = PaymentLink(
            token=token,
            empresa_id=empresa.id,
            amount_minor=int(payload.amount_mxn * 100),
            currency="MXN",
            description=payload.description or f"Servicio EvaAI — {empresa.name}",
            interval=payload.interval,
            plan_tier=payload.plan_tier,
            recipient_email=payload.recipient_email,
            retention_applicable=quote["retention_applicable"],
            created_by=user.id,
        )
        db.add(link)
        await db.flush()

        branded_url = f"{settings.eva_app_base_url.rstrip('/')}/pay/{token}"
        await db.commit()

        return CheckoutLinkResponse(
            checkout_url=branded_url,
            quote=PreviewCheckoutResponse(**quote),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{empresa_id}/portal-link", response_model=PortalLinkResponse)
async def create_portal_link(
    empresa_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    empresa = await db.get(Empresa, empresa_id)
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa not found")
    if not empresa.stripe_customer_id:
        raise HTTPException(status_code=409, detail="Empresa does not have a Stripe customer")

    from src.empresas.billing_service import create_portal_session

    try:
        url = await create_portal_session(empresa)
        return PortalLinkResponse(portal_url=url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ── Phase 4: subscription proxy endpoints ────────────────────────────


def _require_pipeline_flag() -> None:
    if not settings.feature_erp_empresas_pipeline:
        raise HTTPException(status_code=503, detail="FeatureNotEnabled")


async def _load_empresa_with_eva_link(db: AsyncSession, empresa_id: uuid.UUID) -> Empresa:
    empresa = await db.get(Empresa, empresa_id)
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa not found")
    if not empresa.eva_account_id:
        raise HTTPException(
            status_code=409,
            detail={
                "reason": "EmpresaNotLinkedToEvaAccount",
                "message": "Link the empresa to an Eva account before managing the subscription.",
            },
        )
    return empresa


def _apply_eva_response_to_empresa(empresa: Empresa, payload: dict) -> None:
    if payload.get("subscription_id"):
        empresa.stripe_subscription_id = payload["subscription_id"]
    period_end = payload.get("current_period_end")
    if isinstance(period_end, (int, float)):
        from datetime import datetime, timezone
        empresa.current_period_end = datetime.fromtimestamp(int(period_end), tz=timezone.utc)
    empresa.subscription_status = "active"


@router.post("/{empresa_id}/subscription/preview", response_model=SubscriptionApplyResponse)
async def preview_subscription(
    empresa_id: uuid.UUID,
    data: SubscriptionApplyRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Dry-run reprice — forwards to Eva and returns proration preview."""
    _require_pipeline_flag()
    empresa = await _load_empresa_with_eva_link(db, empresa_id)
    client = EvaBillingClient()
    try:
        preview = await client.preview_subscription(
            account_id=empresa.eva_account_id,
            plan_tier=data.plan_tier,
            billing_interval=data.billing_interval,
            base_subtotal_minor=data.base_subtotal_minor,
            erp_description=data.erp_description,
            empresa_id=empresa.id,
            proration_behavior=data.proration_behavior,
        )
    except EvaBillingClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return SubscriptionApplyResponse(
        subscription_id=preview.get("subscription_id"),
        price_id=preview.get("price_id"),
        product_id=preview.get("product_id"),
        base_subtotal_minor=preview.get("base_subtotal_minor", data.base_subtotal_minor),
        payable_total_minor=preview.get("payable_total_minor", data.base_subtotal_minor),
        retention_applicable=preview.get("retention_applicable", False),
        person_type=preview.get("person_type"),
        current_period_end=preview.get("current_period_end"),
        preview=preview.get("preview_invoice"),
    )


@router.post("/{empresa_id}/subscription/apply", response_model=SubscriptionApplyResponse)
async def apply_subscription(
    empresa_id: uuid.UUID,
    data: SubscriptionApplyRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="X-Empresa-Idempotency-Key"),
):
    """Apply reprice via Eva, then sync local empresa billing cache.

    NOT cross-system atomic: if the Eva call succeeds but the local commit
    fails (network blip), the next preview call will show Eva's actual state
    and the hourly reconcile_empresa_billing_cache beat sweeps drift.
    """
    _require_pipeline_flag()
    empresa = await _load_empresa_with_eva_link(db, empresa_id)

    client = EvaBillingClient()
    try:
        result = await client.reprice_subscription(
            account_id=empresa.eva_account_id,
            plan_tier=data.plan_tier,
            billing_interval=data.billing_interval,
            base_subtotal_minor=data.base_subtotal_minor,
            erp_description=data.erp_description,
            empresa_id=empresa.id,
            proration_behavior=data.proration_behavior,
            idempotency_key=idempotency_key,
        )
    except EvaBillingClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    # Sync local empresa billing cache post-apply.
    empresa.monthly_amount = data.base_subtotal_minor / 100
    empresa.billing_interval = data.billing_interval
    _apply_eva_response_to_empresa(empresa, result)
    db.add(empresa)
    try:
        await db.flush()
    except Exception:
        # Eva already applied the change — don't retry the Stripe mutation.
        # The reconcile beat will pick this up; log and surface.
        logger.exception("empresas.apply.local_commit_failed empresa=%s", empresa.id)

    return SubscriptionApplyResponse(
        subscription_id=result.get("subscription_id"),
        price_id=result.get("price_id"),
        product_id=result.get("product_id"),
        base_subtotal_minor=result.get("base_subtotal_minor", data.base_subtotal_minor),
        payable_total_minor=result.get("payable_total_minor", data.base_subtotal_minor),
        retention_applicable=result.get("retention_applicable", False),
        person_type=result.get("person_type"),
        current_period_end=result.get("current_period_end"),
    )


@router.post("/{empresa_id}/subscription/cancel", response_model=SubscriptionCancelResponse)
async def cancel_subscription(
    empresa_id: uuid.UUID,
    data: SubscriptionCancelRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="X-Empresa-Idempotency-Key"),
):
    _require_pipeline_flag()
    empresa = await _load_empresa_with_eva_link(db, empresa_id)

    client = EvaBillingClient()
    try:
        result = await client.cancel_subscription(
            account_id=empresa.eva_account_id,
            at_period_end=data.at_period_end,
            cancel_reason=data.cancel_reason,
            empresa_id=empresa.id,
            idempotency_key=idempotency_key,
        )
    except EvaBillingClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    scheduled_at = result.get("cancellation_scheduled_at")
    if data.at_period_end and isinstance(scheduled_at, (int, float)):
        from datetime import datetime, timezone
        empresa.cancellation_scheduled_at = datetime.fromtimestamp(int(scheduled_at), tz=timezone.utc)
    else:
        empresa.cancellation_scheduled_at = None
    empresa.subscription_status = result.get("subscription_status", empresa.subscription_status)
    db.add(empresa)
    await db.flush()

    return SubscriptionCancelResponse(**result)


@router.post("/{empresa_id}/extract-constancia", response_model=ConstanciaExtractResponse)
async def extract_constancia(
    empresa_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    empresa = await db.get(Empresa, empresa_id)
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa not found")

    content_type = file.content_type or "application/octet-stream"
    if content_type not in ("application/pdf", "image/png", "image/jpeg", "image/jpg", "image/webp"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF o imagenes (PNG, JPG)")

    file_bytes = await file.read()
    if len(file_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="El archivo no puede ser mayor a 10 MB")

    from src.empresas.constancia_service import extract_from_file

    result = await extract_from_file(file_bytes, content_type)
    return ConstanciaExtractResponse(**result)
