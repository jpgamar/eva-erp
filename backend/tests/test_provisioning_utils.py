import pytest
from fastapi import HTTPException

from src.eva_platform.provisioning_utils import (
    map_provisioning_write_error,
    normalize_billing_cycle,
    normalize_plan_tier,
)


def test_normalize_plan_tier_maps_custom_to_pro():
    assert normalize_plan_tier("custom") == "PRO"
    assert normalize_plan_tier("starter") == "STARTER"


def test_normalize_plan_tier_rejects_unknown_value():
    with pytest.raises(HTTPException) as exc:
        normalize_plan_tier("enterprise")
    assert exc.value.status_code == 400


def test_normalize_billing_cycle_maps_yearly_to_annual():
    assert normalize_billing_cycle("yearly") == "ANNUAL"
    assert normalize_billing_cycle("monthly") == "MONTHLY"


def test_normalize_billing_cycle_rejects_unknown_value():
    with pytest.raises(HTTPException) as exc:
        normalize_billing_cycle("weekly")
    assert exc.value.status_code == 400


class _FakeDatabaseError(Exception):
    def __init__(self, message: str):
        self.orig = Exception(message)


def test_map_provisioning_write_error_unique_owner_constraint_to_409():
    exc = _FakeDatabaseError('duplicate key value violates unique constraint "accounts_owner_user_id_key"')
    mapped = map_provisioning_write_error(exc, "fallback")
    assert mapped.status_code == 409


def test_map_provisioning_write_error_billing_enum_to_400():
    exc = _FakeDatabaseError("invalid input value for enum billing_interval")
    mapped = map_provisioning_write_error(exc, "fallback")
    assert mapped.status_code == 400


def test_map_provisioning_write_error_unknown_to_500():
    exc = _FakeDatabaseError("some unknown db issue")
    mapped = map_provisioning_write_error(exc, "fallback")
    assert mapped.status_code == 500
