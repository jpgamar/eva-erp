"""RFC format validator on EmpresaCreate / EmpresaUpdate.

Regression: 2026-04-13 — F&M Accesorios was onboarded with `FAC2530067F3`
(month digits 30 don't exist), which Facturapi correctly rejected weeks
later when their first invoice ran. The validator catches this at write time.
"""

from __future__ import annotations

import pytest

from src.empresas.schemas import EmpresaCreate, EmpresaUpdate, _validate_mexican_rfc


class TestValidateRFC:
    def test_accepts_valid_persona_moral(self):
        assert _validate_mexican_rfc("FAC2503067F3") == "FAC2503067F3"

    def test_accepts_valid_persona_fisica(self):
        assert _validate_mexican_rfc("VECJ880326XX0") == "VECJ880326XX0"

    def test_normalizes_lowercase_input(self):
        assert _validate_mexican_rfc("fac2503067f3") == "FAC2503067F3"

    def test_strips_whitespace(self):
        assert _validate_mexican_rfc("  FAC2503067F3  ") == "FAC2503067F3"

    def test_rejects_the_fmaccesorios_typo(self):
        with pytest.raises(ValueError, match="mes '30'"):
            _validate_mexican_rfc("FAC2530067F3")

    def test_rejects_invalid_day(self):
        with pytest.raises(ValueError, match="día '32'"):
            _validate_mexican_rfc("FAC250332ABC")

    def test_rejects_too_short(self):
        with pytest.raises(ValueError, match="12 caracteres"):
            _validate_mexican_rfc("FAC25030")

    def test_rejects_garbage(self):
        with pytest.raises(ValueError, match="12 caracteres"):
            _validate_mexican_rfc("not-an-rfc")


class TestEmpresaCreateRFC:
    def test_blank_rfc_is_allowed(self):
        empresa = EmpresaCreate(name="X", rfc="")
        assert empresa.rfc is None

    def test_none_rfc_is_allowed(self):
        empresa = EmpresaCreate(name="X")
        assert empresa.rfc is None

    def test_valid_rfc_is_normalized(self):
        empresa = EmpresaCreate(name="X", rfc="fac2503067f3")
        assert empresa.rfc == "FAC2503067F3"

    def test_invalid_rfc_raises_on_create(self):
        with pytest.raises(ValueError):
            EmpresaCreate(name="X", rfc="FAC2530067F3")


class TestEmpresaUpdateRFC:
    def test_blank_rfc_is_allowed(self):
        empresa = EmpresaUpdate(rfc="")
        assert empresa.rfc is None

    def test_invalid_rfc_raises_on_update(self):
        with pytest.raises(ValueError):
            EmpresaUpdate(rfc="FAC2530067F3")
