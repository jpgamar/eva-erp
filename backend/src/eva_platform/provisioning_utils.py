"""Shared helpers for Eva platform provisioning flows."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.eva_platform.models import EvaAccount, EvaAccountUser


def normalize_plan_tier(raw_value: str) -> str:
    normalized = (raw_value or "").strip().upper()
    # Eva production currently supports STARTER/STANDARD/PRO only.
    if normalized == "CUSTOM":
        normalized = "PRO"
    if normalized not in {"STARTER", "STANDARD", "PRO"}:
        raise HTTPException(
            status_code=400,
            detail="Unsupported plan tier. Allowed values: starter, standard, pro.",
        )
    return normalized


def normalize_billing_cycle(raw_value: str) -> str:
    normalized = (raw_value or "").strip().upper()
    aliases = {
        "MONTHLY": "MONTHLY",
        "ANNUAL": "ANNUAL",
        "ANNUALLY": "ANNUAL",
        "YEARLY": "ANNUAL",
    }
    mapped = aliases.get(normalized, normalized)
    if mapped not in {"MONTHLY", "ANNUAL"}:
        raise HTTPException(
            status_code=400,
            detail="Unsupported billing cycle. Allowed values: monthly, annual.",
        )
    return mapped


def normalize_account_type(raw_value: str) -> str:
    normalized = (raw_value or "").strip().upper()
    if normalized not in {"COMMERCE", "PROPERTY_MANAGEMENT"}:
        raise HTTPException(
            status_code=400,
            detail="Unsupported account type. Allowed values: commerce, property_management.",
        )
    return normalized


def map_provisioning_write_error(exc: Exception, default_message: str) -> HTTPException:
    original = str(getattr(exc, "orig", exc) or exc).lower()

    if "accounts_owner_user_id_key" in original or "account_users_user_id_key" in original:
        return HTTPException(
            status_code=409,
            detail="Owner email is already linked to another account. Use a different owner email.",
        )

    if "account_users_account_email_unique" in original:
        return HTTPException(
            status_code=409,
            detail="Owner email is already linked to this account.",
        )

    if "invalid input value for enum plan_tier" in original:
        return HTTPException(
            status_code=400,
            detail="Unsupported plan tier for provisioning.",
        )

    if "invalid input value for enum billing_interval" in original:
        return HTTPException(
            status_code=400,
            detail="Unsupported billing cycle for provisioning.",
        )

    if "invalid input value for enum account_type" in original:
        return HTTPException(
            status_code=400,
            detail="Unsupported account type for provisioning.",
        )

    if "violates foreign key constraint" in original:
        return HTTPException(
            status_code=400,
            detail="Invalid related reference while provisioning account.",
        )

    if "null value in column" in original and "violates not-null constraint" in original:
        return HTTPException(
            status_code=400,
            detail="Missing required account data for provisioning.",
        )

    condensed = " ".join(original.split())
    if condensed:
        detail = f"{default_message} (reason: {condensed[:220]})"
    else:
        detail = default_message
    return HTTPException(status_code=500, detail=detail)


async def ensure_owner_user_is_available(eva_db: AsyncSession, sb_user_id: str, owner_email: str) -> None:
    """Guarantee the owner auth user is not already bound to an existing account."""
    result = await eva_db.execute(
        select(EvaAccount).where(EvaAccount.owner_user_id == str(sb_user_id)).limit(1)
    )
    existing_account = result.scalar_one_or_none()
    if existing_account:
        raise HTTPException(
            status_code=409,
            detail=f"Owner email {owner_email} is already linked to account '{existing_account.name}'.",
        )

    result = await eva_db.execute(
        select(EvaAccountUser).where(EvaAccountUser.user_id == str(sb_user_id)).limit(1)
    )
    existing_membership = result.scalar_one_or_none()
    if existing_membership:
        account_result = await eva_db.execute(
            select(EvaAccount).where(EvaAccount.id == existing_membership.account_id).limit(1)
        )
        account = account_result.scalar_one_or_none()
        account_name = account.name if account else str(existing_membership.account_id)
        raise HTTPException(
            status_code=409,
            detail=f"Owner email {owner_email} is already linked to account '{account_name}'.",
        )
