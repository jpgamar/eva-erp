"""Channel health endpoints — read Eva production channel state.

Used by the Empresas page in Eva ERP to render a per-card health dot
plus a details modal showing which channels are broken on a linked
Eva account.

This file is read-only against Eva production: it never UPDATEs or
INSERTs through the ``eva_db`` session. The mirror models
(``EvaMessengerChannel``, ``EvaInstagramChannel``, ``EvaAgent``) live
on ``EvaBase`` so Alembic in this repo never targets them.

Plan: docs/domains/integrations/instagram/plan-silent-channel-health.md
"""

from __future__ import annotations

import logging
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.common.database import get_optional_eva_db
from src.empresas.schemas import (
    AccountChannelHealthResponse,
    ChannelHealthEntry,
    EvaAccountForLink,
)
from src.eva_platform.models import (
    EvaAccount,
    EvaAgent,
    EvaInstagramChannel,
    EvaMessengerChannel,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _extract_reason(cached_status_data: dict | None) -> str | None:
    if not isinstance(cached_status_data, dict):
        return None
    reason = cached_status_data.get("health_status_reason")
    if isinstance(reason, str) and reason.strip():
        return reason.strip()[:500]
    return None


@router.get(
    "/accounts/{account_id}/channels/health",
    response_model=AccountChannelHealthResponse,
)
async def get_account_channel_health(
    account_id: uuid.UUID,
    user: User = Depends(get_current_user),
    eva_db: AsyncSession | None = Depends(get_optional_eva_db),
) -> AccountChannelHealthResponse:
    """Return all Messenger + Instagram channels for an Eva account.

    Channels are joined via ``agents.account_id == account_id`` and
    filtered to ``is_active = TRUE``. Returns BOTH healthy and
    unhealthy channels so the modal in Eva ERP can show the full
    inventory, not just the broken ones.

    If ``eva_db`` is not configured, returns 503 — the caller should
    fall back to a "status unknown" indicator. If ``eva_db`` is
    configured but the query raises, also returns 503.
    """
    if eva_db is None:
        raise HTTPException(
            status_code=503,
            detail="Eva production database is not configured (set EVA_DATABASE_URL)",
        )

    try:
        msg_result = await eva_db.execute(
            select(EvaMessengerChannel)
            .join(EvaAgent, EvaAgent.id == EvaMessengerChannel.agent_id)
            .where(
                EvaAgent.account_id == account_id,
                EvaMessengerChannel.is_active.is_(True),
            )
        )
        messenger_rows = list(msg_result.scalars().all())

        ig_result = await eva_db.execute(
            select(EvaInstagramChannel)
            .join(EvaAgent, EvaAgent.id == EvaInstagramChannel.agent_id)
            .where(
                EvaAgent.account_id == account_id,
                EvaInstagramChannel.is_active.is_(True),
            )
        )
        instagram_rows = list(ig_result.scalars().all())
    except Exception as exc:
        logger.warning(
            "eva_platform.channel_health: query failed for account %s: %s",
            account_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=503,
            detail="Could not query Eva production database for channel health",
        )

    messenger_entries: List[ChannelHealthEntry] = [
        ChannelHealthEntry(
            id=row.id,
            channel_type="messenger",
            display_name=row.page_name,
            is_healthy=row.is_healthy,
            health_status_reason=_extract_reason(row.cached_status_data),
            last_status_check=row.last_status_check,
        )
        for row in messenger_rows
    ]
    instagram_entries: List[ChannelHealthEntry] = [
        ChannelHealthEntry(
            id=row.id,
            channel_type="instagram",
            display_name=(
                f"@{row.ig_username}" if row.ig_username else row.page_name
            ),
            is_healthy=row.is_healthy,
            health_status_reason=_extract_reason(row.cached_status_data),
            last_status_check=row.last_status_check,
        )
        for row in instagram_rows
    ]
    return AccountChannelHealthResponse(
        account_id=account_id,
        messenger=messenger_entries,
        instagram=instagram_entries,
    )


@router.get(
    "/accounts/list-for-link",
    response_model=List[EvaAccountForLink],
)
async def list_eva_accounts_for_link(
    user: User = Depends(get_current_user),
    eva_db: AsyncSession | None = Depends(get_optional_eva_db),
) -> List[EvaAccountForLink]:
    """List all active Eva accounts for the Empresa edit-modal dropdown.

    Returns ``id`` and ``name`` only, sorted alphabetically. Used by
    the frontend to populate the "Cuenta de Eva vinculada" select.

    Returns an empty list if ``eva_db`` is not configured (the
    frontend will show a "Could not load accounts" placeholder).
    """
    if eva_db is None:
        return []
    try:
        result = await eva_db.execute(
            select(EvaAccount.id, EvaAccount.name)
            .where(EvaAccount.is_active.is_(True))
            .order_by(EvaAccount.name)
        )
        return [EvaAccountForLink(id=row.id, name=row.name) for row in result.all()]
    except Exception as exc:
        logger.warning(
            "eva_platform.channel_health: list_for_link query failed: %s",
            exc,
            exc_info=True,
        )
        return []
