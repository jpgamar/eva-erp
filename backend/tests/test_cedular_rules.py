"""Unit tests for the cedular rules matrix + resolve_cedular."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.eva_billing.cedular import (
    CEDULAR_RULES,
    CedularRule,
    cedular_rate,
    resolve_cedular,
)


class TestRulesMatrix:
    def test_gto_is_verified_for_resico(self):
        """Acabados scenario: 2% RESICO rate verified via Art. 37-D LHEG."""
        rule = CEDULAR_RULES["GTO"]
        assert rule.rate_resico_pf == Decimal("0.02")
        assert rule.legal_article == "Art. 37-D LHEG"
        assert rule.facturapi_type == "Cedular GTO"

    @pytest.mark.parametrize("state", ["CHH", "GRO", "NAY", "OAX", "ROO", "YUC"])
    def test_other_cedular_states_pending_resico_verification(self, state: str):
        """Other states are in the matrix but RESICO rate isn't verified yet → no-op."""
        rule = CEDULAR_RULES[state]
        assert rule.rate_resico_pf is None
        # But the general-PF rate IS known per each state's Ley de Hacienda.
        assert rule.rate_general_pf is not None


class TestResolveCedular:
    def test_gto_resico_returns_rule(self):
        rule = resolve_cedular("37160", "resico_pf")
        assert rule is not None
        assert rule.state_code == "GTO"

    def test_gto_general_returns_rule(self):
        # General PF (non-RESICO) gets the full 5% GTO cedular.
        rule = resolve_cedular("37160", "general_pf")
        assert rule is not None
        assert rule.state_code == "GTO"

    def test_non_cedular_state_returns_none(self):
        assert resolve_cedular("06600", "resico_pf") is None  # CDMX
        assert resolve_cedular("64000", "resico_pf") is None  # NL

    def test_invalid_zip_returns_none(self):
        assert resolve_cedular(None, "resico_pf") is None
        assert resolve_cedular("abc", "resico_pf") is None
        assert resolve_cedular("", "resico_pf") is None

    def test_unknown_regime_returns_none(self):
        assert resolve_cedular("37160", "persona_moral") is None

    def test_state_with_unverified_resico_rate_returns_none(self):
        # Oaxaca has general_pf=5% but resico_pf is None (pending verification).
        # Calling with RESICO should return None (no retention applied).
        result = resolve_cedular("68000", "resico_pf")
        assert result is None

    def test_state_with_unverified_resico_returns_rule_for_general(self):
        # Same ZIP, but general_pf regime → we do have the rate.
        result = resolve_cedular("68000", "general_pf")
        assert result is not None
        assert result.state_code == "OAX"


class TestCedularRate:
    def test_resico_lookup(self):
        rule = CEDULAR_RULES["GTO"]
        assert cedular_rate(rule, "resico_pf") == Decimal("0.02")

    def test_general_lookup(self):
        rule = CEDULAR_RULES["GTO"]
        assert cedular_rate(rule, "general_pf") == Decimal("0.05")

    def test_unknown_regime_returns_none(self):
        rule = CEDULAR_RULES["GTO"]
        assert cedular_rate(rule, "unknown") is None

    def test_unverified_resico_returns_none(self):
        rule = CEDULAR_RULES["CHH"]
        assert cedular_rate(rule, "resico_pf") is None
