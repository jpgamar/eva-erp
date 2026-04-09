"""Tests for custom deal billing — IVA paths, preview, retention logic."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.eva_billing.service import (
    IVA_RATE,
    ISR_RETENTION_RATE,
    IVA_RETENTION_RATE,
    PERSONA_MORAL_REGIMENES,
    _compute_quote,
    is_fiscal_complete,
    resolve_retention_applicable,
)


# ── resolve_retention_applicable ─────────────────────────────────────


class TestResolveRetentionApplicable:
    def test_persona_moral_returns_true(self):
        assert resolve_retention_applicable("persona_moral", None) is True

    def test_persona_fisica_returns_false(self):
        assert resolve_retention_applicable("persona_fisica", None) is False

    def test_persona_moral_with_regimen_still_true(self):
        assert resolve_retention_applicable("persona_moral", "601") is True

    def test_persona_fisica_with_regimen_still_false(self):
        assert resolve_retention_applicable("persona_fisica", "601") is False

    @pytest.mark.parametrize("regimen", sorted(PERSONA_MORAL_REGIMENES))
    def test_no_person_type_moral_regimen_returns_true(self, regimen):
        assert resolve_retention_applicable(None, regimen) is True

    def test_no_person_type_fisica_regimen_returns_false(self):
        # 612 = Personas Fisicas con Actividades Empresariales
        assert resolve_retention_applicable(None, "612") is False

    def test_both_none_returns_none(self):
        assert resolve_retention_applicable(None, None) is None


# ── is_fiscal_complete ─────────────────────────────────────────────


class TestIsFiscalComplete:
    def test_all_fields_present(self):
        assert is_fiscal_complete(
            rfc="RFC123456T89",
            razon_social="Demo SA",
            regimen_fiscal="601",
            fiscal_postal_code="37266",
            cfdi_use="G03",
            person_type="persona_moral",
        ) is True

    def test_missing_rfc(self):
        assert is_fiscal_complete(
            rfc=None,
            razon_social="Demo SA",
            regimen_fiscal="601",
            fiscal_postal_code="37266",
            cfdi_use="G03",
            person_type="persona_moral",
        ) is False

    def test_missing_postal_code(self):
        assert is_fiscal_complete(
            rfc="RFC123",
            razon_social="Demo SA",
            regimen_fiscal="601",
            fiscal_postal_code=None,
            cfdi_use="G03",
            person_type="persona_moral",
        ) is False

    def test_no_person_type_but_detectable_regimen(self):
        # persona_moral regimen can fill in for missing person_type
        assert is_fiscal_complete(
            rfc="RFC123",
            razon_social="Demo SA",
            regimen_fiscal="601",
            fiscal_postal_code="37266",
            cfdi_use="G03",
            person_type=None,
        ) is True

    def test_no_person_type_non_moral_regimen(self):
        # Can't detect person_type from a non-moral regimen
        assert is_fiscal_complete(
            rfc="RFC123",
            razon_social="Demo SA",
            regimen_fiscal="612",
            fiscal_postal_code="37266",
            cfdi_use="G03",
            person_type=None,
        ) is False


# ── Preview/quote computation ────────────────────────────────────────


class TestComputeQuote:
    def test_persona_moral_quote(self):
        """$2,000 base → IVA $320 - ISR $25 - IVA Ret $213.33 = $2,081.67"""
        quote = _compute_quote(200_000, retention_applicable=True)
        assert quote.base_subtotal_minor == 200_000
        assert quote.iva_minor == 32_000
        assert quote.isr_retention_minor == 2_500
        assert quote.iva_retention_minor == 21_333
        assert quote.payable_total_minor == 208_167
        assert quote.retention_applicable is True

    def test_persona_fisica_quote(self):
        """$2,000 base → IVA $320 = $2,320 (no retentions)"""
        quote = _compute_quote(200_000, retention_applicable=False)
        assert quote.base_subtotal_minor == 200_000
        assert quote.iva_minor == 32_000
        assert quote.isr_retention_minor == 0
        assert quote.iva_retention_minor == 0
        assert quote.payable_total_minor == 232_000
        assert quote.retention_applicable is False

    def test_lucky_intelligence_amount(self):
        """Verified: $3,999 base → total $4,162.29 for persona moral."""
        quote = _compute_quote(399_900, retention_applicable=True)
        assert quote.payable_total_minor == 416_229


# ── Preview checkout (billing_service.preview_checkout) ──────────────


class TestPreviewCheckout:
    def _make_empresa(self, **kwargs):
        """Create a minimal Empresa-like object for testing."""
        from unittest.mock import MagicMock

        emp = MagicMock()
        emp.person_type = kwargs.get("person_type", "persona_moral")
        emp.regimen_fiscal = kwargs.get("regimen_fiscal", "601")
        emp.rfc = kwargs.get("rfc", "RFC123456T89")
        emp.razon_social = kwargs.get("razon_social", "Demo SA de CV")
        emp.fiscal_postal_code = kwargs.get("fiscal_postal_code", "37266")
        emp.cfdi_use = kwargs.get("cfdi_use", "G03")
        emp.name = kwargs.get("name", "Test Empresa")
        return emp

    def test_persona_moral_preview(self):
        from src.empresas.billing_service import preview_checkout

        emp = self._make_empresa(person_type="persona_moral")
        result = preview_checkout(emp, amount_mxn=Decimal("2000"))
        assert result["retention_applicable"] is True
        assert result["base_subtotal_minor"] == 200_000
        assert result["iva_minor"] == 32_000
        assert result["isr_retention_minor"] == 2_500
        assert result["iva_retention_minor"] == 21_333
        assert result["payable_total_minor"] == 208_167
        assert result["stripe_charges_tax"] is False

    def test_persona_fisica_preview(self):
        from src.empresas.billing_service import preview_checkout

        emp = self._make_empresa(person_type="persona_fisica")
        result = preview_checkout(emp, amount_mxn=Decimal("2000"))
        assert result["retention_applicable"] is False
        assert result["base_subtotal_minor"] == 200_000
        assert result["stripe_charges_tax"] is True

    def test_unknown_person_type_raises(self):
        from src.empresas.billing_service import preview_checkout

        emp = self._make_empresa(person_type=None, regimen_fiscal=None)
        with pytest.raises(ValueError, match="tipo de persona"):
            preview_checkout(emp, amount_mxn=Decimal("2000"))

    def test_persona_moral_missing_fiscal_raises(self):
        from src.empresas.billing_service import preview_checkout

        emp = self._make_empresa(person_type="persona_moral", rfc=None)
        with pytest.raises(ValueError, match="informacion fiscal"):
            preview_checkout(emp, amount_mxn=Decimal("2000"))

    def test_zero_amount_raises(self):
        from src.empresas.billing_service import preview_checkout

        emp = self._make_empresa(person_type="persona_moral")
        with pytest.raises(ValueError, match="greater than zero"):
            preview_checkout(emp, amount_mxn=Decimal("0"))
