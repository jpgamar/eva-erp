"""Pydantic schemas for the declaración module."""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class DeclaracionWarning(BaseModel):
    """Something the operator should fix before filing."""
    severity: str  # 'blocker' | 'warning' | 'info'
    code: str      # machine-readable (e.g. 'pending_payment_complement')
    message: str   # human-readable


class IsrResicoPf(BaseModel):
    """ISR simplificado de confianza, Personas Físicas."""
    ingresos: Decimal
    tasa: Decimal
    impuesto_mensual: Decimal
    isr_retenido_por_pms: Decimal
    impuesto_a_pagar: Decimal    # negative value = saldo a favor
    saldo_a_favor: Decimal       # ≥ 0


class DeclaracionAlert(BaseModel):
    """An actionable item surfaced on the dashboard."""
    severity: str   # 'blocker' | 'warning' | 'info'
    code: str
    message: str
    deep_link: str | None = None  # frontend route to resolve it


class DeclaracionAlertsResponse(BaseModel):
    today: str  # ISO date so clients can detect stale caches
    alerts: list[DeclaracionAlert]


class IvaSimplificado(BaseModel):
    """IVA simplificado de confianza."""
    actividades_gravadas_16: Decimal
    iva_trasladado: Decimal
    iva_retenido_por_pms: Decimal
    iva_acreditable: Decimal
    impuesto_a_pagar: Decimal    # negative = saldo a favor
    saldo_a_favor: Decimal


class DeclaracionResponse(BaseModel):
    year: int
    month: int
    rfc: str
    isr: IsrResicoPf
    iva: IvaSimplificado
    warnings: list[DeclaracionWarning]
