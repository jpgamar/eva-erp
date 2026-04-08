import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Boolean, func, select, case, literal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.common.database import get_db, get_optional_eva_db
from src.empresas.models import Empresa, EmpresaHistory, EmpresaItem
from src.empresas.schemas import (
    EmpresaCreate,
    EmpresaHistoryResponse,
    EmpresaItemCreate,
    EmpresaItemResponse,
    EmpresaItemUpdate,
    EmpresaResponse,
    EmpresaUpdate,
)
from src.eva_platform.models import (
    EvaAccount,
    EvaAgent,
    EvaInstagramChannel,
    EvaMessengerChannel,
    EvaWhatsAppChannel,
)

router = APIRouter(prefix="/empresas", tags=["empresas"])
logger = logging.getLogger(__name__)

TRACKED_FIELDS = {"status", "ball_on", "summary_note"}


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
        empresa.eva_account_id = matches[0]
        logger.info(
            "empresas.auto_match.linked empresa=%s name=%r → eva_account_id=%s",
            empresa.id,
            normalized,
            matches[0],
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

    if empresa_ids:
        items_q = (
            select(EmpresaItem.id, EmpresaItem.empresa_id, EmpresaItem.title)
            .where(EmpresaItem.empresa_id.in_(empresa_ids), EmpresaItem.done == False)
            .order_by(EmpresaItem.created_at.asc())
        )
        items_result = await db.execute(items_q)
        for item in items_result.all():
            pending_items_map[item.empresa_id].append({"id": str(item.id), "title": item.title})

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
            "item_count": r.item_count,
            "pending_count": r.pending_count,
            "pending_items": pending_items_map.get(r.id, []),
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


@router.post("", response_model=EmpresaResponse, status_code=201)
async def create_empresa(
    data: EmpresaCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    empresa = Empresa(**data.model_dump(), created_by=user.id)
    db.add(empresa)
    await db.flush()
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


@router.patch("/{empresa_id}", response_model=EmpresaResponse)
async def update_empresa(
    empresa_id: uuid.UUID,
    data: EmpresaUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Empresa).where(Empresa.id == empresa_id).options(selectinload(Empresa.items))
    )
    empresa = result.scalar_one_or_none()
    if not empresa:
        raise HTTPException(status_code=404, detail="Empresa not found")

    update_data = data.model_dump(exclude_unset=True)

    # Record history for tracked fields
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

    for field, value in update_data.items():
        setattr(empresa, field, value)

    db.add(empresa)
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

    item = EmpresaItem(
        empresa_id=empresa_id,
        title=data.title,
        created_by=user.id,
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

    for field, value in data.model_dump(exclude_unset=True).items():
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
