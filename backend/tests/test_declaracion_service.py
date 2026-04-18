"""Tests for the monthly declaración calculator.

The golden case here is the F-4 scenario (2026-03, $3,999 subtotal to
SERVIACERO). The numbers Gustavo typed into the SAT portal on 2026-04-18
must exactly match what ``compute_monthly_declaration`` produces — if
they drift, this test catches the regression.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from src.declaracion.service import compute_monthly_declaration
from src.declaracion.tables import (
    RESICO_PF_MONTHLY_BRACKETS,
    resico_pf_rate_for,
)


# ---------- RESICO PF rate table ---------------------------------------------


def test_rate_table_tier_boundaries():
    """Each bracket boundary: just-inside = this tier's rate, just-outside
    = next tier's rate. Off-by-one in this table would leak into every
    declaración."""
    # First bracket: ≤ 25,000 → 1.00%
    assert resico_pf_rate_for(Decimal("0.01")) == Decimal("0.0100")
    assert resico_pf_rate_for(Decimal("25000.00")) == Decimal("0.0100")
    # Second bracket: 25,000.01 – 50,000 → 1.10%
    assert resico_pf_rate_for(Decimal("25000.01")) == Decimal("0.0110")
    assert resico_pf_rate_for(Decimal("50000.00")) == Decimal("0.0110")
    # Third bracket: 50,000.01 – 83,333.33 → 1.50%
    assert resico_pf_rate_for(Decimal("83333.33")) == Decimal("0.0150")
    # Fourth bracket: 83,333.34 – 208,333.33 → 2.00%
    assert resico_pf_rate_for(Decimal("83333.34")) == Decimal("0.0200")
    # Fifth bracket: 208,333.34 – 3,500,000 → 2.50%
    assert resico_pf_rate_for(Decimal("208333.34")) == Decimal("0.0250")
    assert resico_pf_rate_for(Decimal("3500000.00")) == Decimal("0.0250")


def test_rate_above_ceiling_raises():
    """> $3.5M monthly → taxpayer ejected from RESICO."""
    with pytest.raises(ValueError, match="RESICO"):
        resico_pf_rate_for(Decimal("3500000.01"))


# ---------- Monthly declaración end-to-end ----------------------------------


class _FakeDeclaracionDB:
    """In-memory DB that returns pre-baked aggregates.

    Rather than simulate joins + SQL, we skip the SQL and patch the
    service helpers directly. This keeps the test focused on the
    business-rule math (which is where bugs hurt taxpayers).
    """


@pytest.mark.asyncio
async def test_f4_march_2026_golden_case(monkeypatch):
    """The regression fixture for the 2026-04-18 F-4 incident. Declaración
    for March 2026 with exactly one PUE factura to Serviacero must produce
    the numbers Gustavo paid (confirmed against the SAT portal on 2026-04-18):

        Ingresos:         $3,999.00
        ISR tasa:         1.00%
        ISR mensual:      $40 (round(39.99))
        ISR retenido:     $49.99
        ISR a favor:      $9.99
        IVA trasladado:   $639.84
        IVA retenido:     $426.56
        IVA acreditable:  $0 (no gastos uploaded yet)
        IVA a pagar:      $213.28
    """
    from src.declaracion import service as decl_service

    async def _fake_pue(db, *, year, month):
        # subtotal, iva, isr_ret, iva_ret
        return (
            Decimal("3999.00"),
            Decimal("639.84"),
            Decimal("49.99"),
            Decimal("426.56"),
        )

    async def _fake_ppd(db, *, year, month):
        return (Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"))

    async def _fake_acreditable(db, *, year, month):
        return Decimal("0")

    async def _fake_warnings(db, *, year, month):
        return []

    monkeypatch.setattr(decl_service, "_sum_pue_ingresos", _fake_pue)
    monkeypatch.setattr(decl_service, "_sum_ppd_payments", _fake_ppd)
    monkeypatch.setattr(decl_service, "_sum_iva_acreditable", _fake_acreditable)
    monkeypatch.setattr(decl_service, "_collect_warnings", _fake_warnings)

    result = await compute_monthly_declaration(
        db=None, year=2026, month=3, rfc="ZEPG070314VC1"
    )

    assert result.year == 2026
    assert result.month == 3
    # ISR
    assert result.isr.ingresos == Decimal("3999.00")
    assert result.isr.tasa == Decimal("0.0100")
    assert result.isr.impuesto_mensual == Decimal("39.99")
    assert result.isr.isr_retenido_por_pms == Decimal("49.99")
    assert result.isr.impuesto_a_pagar == Decimal("0.00")
    # Saldo a favor = retención − impuesto = 49.99 − 39.99 = 10.00
    assert result.isr.saldo_a_favor == Decimal("10.00")
    # IVA
    assert result.iva.actividades_gravadas_16 == Decimal("3999.00")
    assert result.iva.iva_trasladado == Decimal("639.84")
    assert result.iva.iva_retenido_por_pms == Decimal("426.56")
    assert result.iva.iva_acreditable == Decimal("0.00")
    # Neto IVA = 639.84 − 426.56 − 0 = 213.28
    assert result.iva.impuesto_a_pagar == Decimal("213.28")
    assert result.iva.saldo_a_favor == Decimal("0.00")


@pytest.mark.asyncio
async def test_iva_with_acreditable_reduces_payable(monkeypatch):
    """Sanity: if gastos with CFDI bring IVA acreditable, the impuesto
    to pay shrinks. A refactor that failed to wire acreditable into
    the math would break this."""
    from src.declaracion import service as decl_service

    async def _pue(db, **_kw):
        return (Decimal("10000.00"), Decimal("1600.00"), Decimal("0.00"), Decimal("0.00"))

    async def _ppd(db, **_kw):
        return (Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"))

    async def _acr(db, **_kw):
        return Decimal("200.00")  # 200 pesos of IVA on gastos

    async def _warn(db, **_kw):
        return []

    monkeypatch.setattr(decl_service, "_sum_pue_ingresos", _pue)
    monkeypatch.setattr(decl_service, "_sum_ppd_payments", _ppd)
    monkeypatch.setattr(decl_service, "_sum_iva_acreditable", _acr)
    monkeypatch.setattr(decl_service, "_collect_warnings", _warn)

    result = await compute_monthly_declaration(
        db=None, year=2026, month=4, rfc="ZEPG070314VC1"
    )

    # IVA trasladado 1600 - 0 retenido - 200 acreditable = 1400 a pagar
    assert result.iva.iva_acreditable == Decimal("200.00")
    assert result.iva.impuesto_a_pagar == Decimal("1400.00")


@pytest.mark.asyncio
async def test_acreditable_exceeds_trasladado_gives_saldo_favor(monkeypatch):
    from src.declaracion import service as decl_service

    async def _pue(db, **_kw):
        return (Decimal("1000.00"), Decimal("160.00"), Decimal("0.00"), Decimal("0.00"))

    async def _ppd(db, **_kw):
        return (Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"))

    async def _acr(db, **_kw):
        return Decimal("500.00")  # more IVA acreditable than trasladado

    async def _warn(db, **_kw):
        return []

    monkeypatch.setattr(decl_service, "_sum_pue_ingresos", _pue)
    monkeypatch.setattr(decl_service, "_sum_ppd_payments", _ppd)
    monkeypatch.setattr(decl_service, "_sum_iva_acreditable", _acr)
    monkeypatch.setattr(decl_service, "_collect_warnings", _warn)

    result = await compute_monthly_declaration(
        db=None, year=2026, month=4, rfc="ZEPG070314VC1"
    )

    assert result.iva.impuesto_a_pagar == Decimal("0.00")
    assert result.iva.saldo_a_favor == Decimal("340.00")  # 500 - 160
