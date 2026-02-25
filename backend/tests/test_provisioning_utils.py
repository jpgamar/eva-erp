import pytest
from fastapi import HTTPException

from src.eva_platform.provisioning_utils import (
    map_provisioning_write_error,
    normalize_account_type,
    normalize_billing_cycle,
    normalize_deal_stage,
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


def test_normalize_account_type_accepts_known_values():
    assert normalize_account_type("commerce") == "COMMERCE"
    assert normalize_account_type("PROPERTY_MANAGEMENT") == "PROPERTY_MANAGEMENT"


def test_normalize_account_type_rejects_unknown_value():
    with pytest.raises(HTTPException) as exc:
        normalize_account_type("other")
    assert exc.value.status_code == 400


def test_normalize_deal_stage_accepts_known_values():
    assert normalize_deal_stage("TO_CONTACT") == "to_contact"
    assert normalize_deal_stage("won") == "won"


def test_normalize_deal_stage_rejects_unknown_value():
    with pytest.raises(HTTPException) as exc:
        normalize_deal_stage("closed")
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
    assert "reason:" in mapped.detail


def test_map_provisioning_write_error_account_type_enum_to_400():
    exc = _FakeDatabaseError("invalid input value for enum account_type")
    mapped = map_provisioning_write_error(exc, "fallback")
    assert mapped.status_code == 400


def test_map_provisioning_write_error_not_null_to_400():
    exc = _FakeDatabaseError('null value in column "foo" violates not-null constraint')
    mapped = map_provisioning_write_error(exc, "fallback")
    assert mapped.status_code == 400


def test_map_provisioning_write_error_subscription_type_mismatch_to_400():
    exc = _FakeDatabaseError(
        'column "subscription_status" is of type subscription_status but expression is of type character varying'
    )
    mapped = map_provisioning_write_error(exc, "fallback")
    assert mapped.status_code == 400
    assert "subscription status" in mapped.detail.lower()


def test_map_provisioning_write_error_partner_deal_stage_type_mismatch_to_400():
    exc = _FakeDatabaseError(
        'column "stage" is of type partner_deal_stage but expression is of type character varying'
    )
    mapped = map_provisioning_write_error(exc, "fallback")
    assert mapped.status_code == 400
    assert "deal stage" in mapped.detail.lower()
