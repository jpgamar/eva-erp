import uuid
from datetime import datetime
from pydantic import BaseModel


class SetupVaultRequest(BaseModel):
    master_password: str


class UnlockVaultRequest(BaseModel):
    master_password: str


class VaultStatusResponse(BaseModel):
    is_setup: bool
    is_unlocked: bool


class CredentialCreate(BaseModel):
    name: str
    category: str
    url: str | None = None
    login_url: str | None = None
    username: str | None = None
    password: str | None = None
    api_keys: str | None = None
    notes: str | None = None
    monthly_cost: float | None = None
    cost_currency: str = "USD"
    billing_cycle: str | None = None
    who_has_access: list[uuid.UUID] | None = None


class CredentialUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    url: str | None = None
    login_url: str | None = None
    username: str | None = None
    password: str | None = None
    api_keys: str | None = None
    notes: str | None = None
    monthly_cost: float | None = None
    cost_currency: str | None = None
    billing_cycle: str | None = None
    who_has_access: list[uuid.UUID] | None = None


class CredentialListItem(BaseModel):
    id: uuid.UUID
    name: str
    category: str
    url: str | None
    monthly_cost: float | None
    cost_currency: str
    monthly_cost_mxn: float | None
    billing_cycle: str | None
    who_has_access: list[uuid.UUID] | None
    created_at: datetime
    model_config = {"from_attributes": True}


class CredentialDetail(CredentialListItem):
    login_url: str | None
    username: str | None = None
    password: str | None = None
    api_keys: str | None = None
    notes: str | None = None
    updated_at: datetime


class CostSummaryResponse(BaseModel):
    total_mxn: float
    total_usd: float
    combined_mxn: float
    by_category: dict[str, float]
    service_count: int


class AuditLogEntry(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    credential_id: uuid.UUID
    action: str
    ip_address: str | None
    created_at: datetime
    model_config = {"from_attributes": True}
