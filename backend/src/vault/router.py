import os
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from passlib.context import CryptContext
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.common.database import get_db
from src.common.encryption import decrypt_field, derive_key, encrypt_field
from src.vault.models import Credential, VaultAuditLog, VaultConfig
from src.vault.schemas import (
    AuditLogEntry,
    CostSummaryResponse,
    CredentialCreate,
    CredentialDetail,
    CredentialListItem,
    CredentialUpdate,
    SetupVaultRequest,
    UnlockVaultRequest,
    VaultStatusResponse,
)

router = APIRouter(prefix="/vault", tags=["vault"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# In-memory vault sessions: {user_id: {"key": bytes, "expires": datetime}}
_vault_sessions: dict[str, dict] = {}
VAULT_TTL_MINUTES = 30


def _get_vault_key(user_id: uuid.UUID) -> bytes | None:
    session = _vault_sessions.get(str(user_id))
    if not session:
        return None
    if datetime.now(timezone.utc) > session["expires"]:
        del _vault_sessions[str(user_id)]
        return None
    # Refresh TTL on access
    session["expires"] = datetime.now(timezone.utc) + timedelta(minutes=VAULT_TTL_MINUTES)
    return session["key"]


@router.post("/setup")
async def setup_vault(
    data: SetupVaultRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(VaultConfig).where(VaultConfig.user_id == current_user.id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Vault already set up")

    salt = os.urandom(32)
    config = VaultConfig(
        user_id=current_user.id,
        master_password_hash=pwd_context.hash(data.master_password),
        salt=salt,
    )
    db.add(config)

    # Auto-unlock after setup
    key = derive_key(data.master_password, salt)
    _vault_sessions[str(current_user.id)] = {
        "key": key,
        "expires": datetime.now(timezone.utc) + timedelta(minutes=VAULT_TTL_MINUTES),
    }
    return {"message": "Vault created and unlocked"}


@router.post("/unlock")
async def unlock_vault(
    data: UnlockVaultRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(VaultConfig).where(VaultConfig.user_id == current_user.id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Vault not set up")

    if not pwd_context.verify(data.master_password, config.master_password_hash):
        raise HTTPException(status_code=401, detail="Invalid master password")

    key = derive_key(data.master_password, config.salt)
    _vault_sessions[str(current_user.id)] = {
        "key": key,
        "expires": datetime.now(timezone.utc) + timedelta(minutes=VAULT_TTL_MINUTES),
    }
    return {"message": "Vault unlocked"}


@router.post("/lock")
async def lock_vault(current_user: User = Depends(get_current_user)):
    _vault_sessions.pop(str(current_user.id), None)
    return {"message": "Vault locked"}


@router.get("/status", response_model=VaultStatusResponse)
async def vault_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(VaultConfig).where(VaultConfig.user_id == current_user.id))
    is_setup = result.scalar_one_or_none() is not None
    is_unlocked = _get_vault_key(current_user.id) is not None
    return VaultStatusResponse(is_setup=is_setup, is_unlocked=is_unlocked)


@router.get("/credentials", response_model=list[CredentialListItem])
async def list_credentials(
    category: str | None = None,
    search: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Credential).where(Credential.is_deleted == False)
    if category:
        query = query.where(Credential.category == category)
    if search:
        query = query.where(Credential.name.ilike(f"%{search}%"))
    query = query.order_by(Credential.name)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/credentials", response_model=CredentialListItem, status_code=201)
async def create_credential(
    data: CredentialCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    key = _get_vault_key(current_user.id)
    if not key:
        raise HTTPException(status_code=403, detail="Vault is locked")

    # Convert to USD equivalent
    cost_usd = None
    if data.monthly_cost is not None:
        cost_usd = data.monthly_cost if data.cost_currency == "USD" else data.monthly_cost / 20

    cred = Credential(
        name=data.name,
        category=data.category,
        url=data.url,
        login_url=data.login_url,
        username_encrypted=encrypt_field(data.username or "", key) or None,
        password_encrypted=encrypt_field(data.password or "", key) or None,
        api_keys_encrypted=encrypt_field(data.api_keys or "", key) or None,
        notes_encrypted=encrypt_field(data.notes or "", key) or None,
        monthly_cost=data.monthly_cost,
        cost_currency=data.cost_currency,
        monthly_cost_usd=cost_usd,
        billing_cycle=data.billing_cycle,
        who_has_access=data.who_has_access,
        created_by=current_user.id,
    )
    db.add(cred)
    await db.flush()

    # Audit log
    db.add(VaultAuditLog(user_id=current_user.id, credential_id=cred.id, action="create"))
    return cred


@router.get("/credentials/{credential_id}", response_model=CredentialDetail)
async def get_credential(
    credential_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    key = _get_vault_key(current_user.id)
    if not key:
        raise HTTPException(status_code=403, detail="Vault is locked")

    result = await db.execute(
        select(Credential).where(Credential.id == credential_id, Credential.is_deleted == False)
    )
    cred = result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")

    # Audit log
    ip = request.client.host if request.client else None
    db.add(VaultAuditLog(user_id=current_user.id, credential_id=cred.id, action="view", ip_address=ip))

    return CredentialDetail(
        id=cred.id,
        name=cred.name,
        category=cred.category,
        url=cred.url,
        login_url=cred.login_url,
        username=decrypt_field(cred.username_encrypted, key) if cred.username_encrypted else None,
        password=decrypt_field(cred.password_encrypted, key) if cred.password_encrypted else None,
        api_keys=decrypt_field(cred.api_keys_encrypted, key) if cred.api_keys_encrypted else None,
        notes=decrypt_field(cred.notes_encrypted, key) if cred.notes_encrypted else None,
        monthly_cost=float(cred.monthly_cost) if cred.monthly_cost else None,
        cost_currency=cred.cost_currency,
        monthly_cost_usd=float(cred.monthly_cost_usd) if cred.monthly_cost_usd else None,
        billing_cycle=cred.billing_cycle,
        who_has_access=cred.who_has_access,
        created_at=cred.created_at,
        updated_at=cred.updated_at,
    )


@router.patch("/credentials/{credential_id}", response_model=CredentialListItem)
async def update_credential(
    credential_id: uuid.UUID,
    data: CredentialUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    key = _get_vault_key(current_user.id)
    if not key:
        raise HTTPException(status_code=403, detail="Vault is locked")

    result = await db.execute(
        select(Credential).where(Credential.id == credential_id, Credential.is_deleted == False)
    )
    cred = result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")

    if data.name is not None: cred.name = data.name
    if data.category is not None: cred.category = data.category
    if data.url is not None: cred.url = data.url
    if data.login_url is not None: cred.login_url = data.login_url
    if data.username is not None: cred.username_encrypted = encrypt_field(data.username, key) or None
    if data.password is not None: cred.password_encrypted = encrypt_field(data.password, key) or None
    if data.api_keys is not None: cred.api_keys_encrypted = encrypt_field(data.api_keys, key) or None
    if data.notes is not None: cred.notes_encrypted = encrypt_field(data.notes, key) or None
    if data.monthly_cost is not None: cred.monthly_cost = data.monthly_cost
    if data.cost_currency is not None: cred.cost_currency = data.cost_currency
    if data.billing_cycle is not None: cred.billing_cycle = data.billing_cycle
    if data.who_has_access is not None: cred.who_has_access = data.who_has_access

    # Recalculate USD equivalent
    if cred.monthly_cost is not None:
        cred.monthly_cost_usd = float(cred.monthly_cost) if cred.cost_currency == "USD" else float(cred.monthly_cost) / 20

    db.add(cred)
    db.add(VaultAuditLog(user_id=current_user.id, credential_id=cred.id, action="edit"))
    return cred


@router.delete("/credentials/{credential_id}")
async def delete_credential(
    credential_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Credential).where(Credential.id == credential_id, Credential.is_deleted == False)
    )
    cred = result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")

    cred.is_deleted = True
    db.add(cred)
    db.add(VaultAuditLog(user_id=current_user.id, credential_id=cred.id, action="delete"))
    return {"message": "Credential deleted"}


@router.get("/cost-summary", response_model=CostSummaryResponse)
async def cost_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Credential).where(Credential.is_deleted == False, Credential.monthly_cost.isnot(None))
    )
    creds = result.scalars().all()

    total_usd = sum(float(c.monthly_cost) for c in creds if c.cost_currency == "USD")
    total_mxn = sum(float(c.monthly_cost) for c in creds if c.cost_currency == "MXN")
    combined_usd = sum(float(c.monthly_cost_usd or 0) for c in creds)

    by_category: dict[str, float] = {}
    for c in creds:
        cat = c.category
        by_category[cat] = by_category.get(cat, 0) + float(c.monthly_cost_usd or 0)

    return CostSummaryResponse(
        total_usd=total_usd,
        total_mxn=total_mxn,
        combined_usd=combined_usd,
        by_category=by_category,
        service_count=len(creds),
    )


@router.get("/audit-log", response_model=list[AuditLogEntry])
async def audit_log(
    credential_id: uuid.UUID | None = None,
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(VaultAuditLog).order_by(VaultAuditLog.created_at.desc()).limit(limit)
    if credential_id:
        query = query.where(VaultAuditLog.credential_id == credential_id)
    result = await db.execute(query)
    return result.scalars().all()
