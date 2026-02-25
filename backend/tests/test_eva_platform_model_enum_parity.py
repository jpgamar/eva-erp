from sqlalchemy.sql.sqltypes import Enum as SQLEnumType

from src.eva_platform.models import EvaAccount, EvaPartnerDeal, EvaPartnerDomain


def _assert_enum_column(model, column_name: str, enum_name: str) -> None:
    column_type = model.__table__.c[column_name].type
    assert isinstance(column_type, SQLEnumType)
    assert column_type.name == enum_name


def test_account_billing_columns_are_enum_typed():
    _assert_enum_column(EvaAccount, "account_type", "account_type")
    _assert_enum_column(EvaAccount, "subscription_status", "subscription_status")
    _assert_enum_column(EvaAccount, "plan_tier", "plan_tier")
    _assert_enum_column(EvaAccount, "billing_interval", "billing_interval")
    _assert_enum_column(EvaAccount, "billing_person_type", "billing_person_type")


def test_partner_domain_and_deal_status_columns_are_enum_typed():
    _assert_enum_column(EvaPartnerDomain, "status", "partner_domain_status")
    _assert_enum_column(EvaPartnerDeal, "stage", "partner_deal_stage")
