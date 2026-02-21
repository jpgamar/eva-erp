import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, LargeBinary, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.common.database import Base


class VaultConfig(Base):
    __tablename__ = "vault_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True)
    master_password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    salt: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Credential(Base):
    __tablename__ = "credentials"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    login_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    username_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    password_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    api_keys_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    notes_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    monthly_cost: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    cost_currency: Mapped[str] = mapped_column(String(3), default="USD")
    monthly_cost_usd: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    billing_cycle: Mapped[str | None] = mapped_column(String(20), nullable=True)
    who_has_access: Mapped[list | None] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class VaultAuditLog(Base):
    __tablename__ = "vault_audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    credential_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("credentials.id"))
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
