"""Unit tests for state_from_zip.

The mapping is deterministic (first 2 digits → state) per SAT's catalog.
We assert:
  - each of the 7 cedular states maps correctly,
  - non-cedular ZIPs return None,
  - malformed/empty inputs return None.
"""

from __future__ import annotations

import pytest

from src.common.mx_postal_codes import state_from_zip


class TestCedularStateMapping:
    # One concrete ZIP per cedular state (real cities).
    @pytest.mark.parametrize(
        "zip_code, expected",
        [
            ("31000", "CHH"),  # Chihuahua capital
            ("32000", "CHH"),  # Juárez
            ("37160", "GTO"),  # Acabados' ZIP in León
            ("37266", "GTO"),  # León downtown
            ("36000", "GTO"),  # Guanajuato capital
            ("38000", "GTO"),  # Celaya
            ("39000", "GRO"),  # Chilpancingo
            ("40000", "GRO"),  # Iguala
            ("63000", "NAY"),  # Tepic
            ("68000", "OAX"),  # Oaxaca capital
            ("70000", "OAX"),  # Juchitán area
            ("77500", "ROO"),  # Cancún
            ("97000", "YUC"),  # Mérida
        ],
    )
    def test_cedular_states(self, zip_code: str, expected: str):
        assert state_from_zip(zip_code) == expected


class TestNonCedularZips:
    @pytest.mark.parametrize(
        "zip_code",
        [
            "06600",  # CDMX
            "20000",  # Aguascalientes
            "44100",  # Jalisco (Guadalajara)
            "64000",  # Nuevo León (Monterrey)
            "86000",  # Tabasco (Villahermosa)
        ],
    )
    def test_non_cedular_returns_none(self, zip_code: str):
        assert state_from_zip(zip_code) is None


class TestMalformedInput:
    @pytest.mark.parametrize("bad", ["", None, "a", "ab", "abcde", "x123"])
    def test_malformed_returns_none(self, bad):
        assert state_from_zip(bad) is None

    def test_whitespace_trimmed(self):
        assert state_from_zip("  37160  ") == "GTO"

    def test_short_zip_returns_none(self):
        # Less than 2 digits.
        assert state_from_zip("3") is None
