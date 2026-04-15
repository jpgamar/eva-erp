"""Unit tests for Phase 2 empresa pipeline schema + business rules."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from src.empresas.router import _enforce_business_rules
from src.empresas.schemas import (
    EmpresaCreate,
    EmpresaInteractionCreate,
    EmpresaListResponse,
    EmpresaResponse,
    EmpresaUpdate,
)


class TestEmpresaSchemaRoundTrip:
    """New fields accepted on create/update and surfaced on response."""

    def test_create_accepts_lifecycle_and_prospect_fields(self):
        payload = EmpresaCreate(
            name="Acabados",
            lifecycle_stage="prospecto",
            billing_interval="monthly",
            monthly_amount=Decimal("1500.00"),
            payment_day=15,
            expected_close_date=date(2026, 5, 1),
            website="https://acabados.mx",
            contact_name="Ana",
            contact_email="ana@acabados.mx",
            source="referral",
            estimated_plan="standard",
            estimated_mrr_currency="MXN",
            estimated_mrr_usd=Decimal("90.00"),
            prospect_notes="Pilot",
            tags=["implementacion"],
        )
        dumped = payload.model_dump()
        assert dumped["lifecycle_stage"] == "prospecto"
        assert dumped["billing_interval"] == "monthly"
        assert dumped["payment_day"] == 15
        assert dumped["tags"] == ["implementacion"]
        assert dumped["estimated_mrr_usd"] == Decimal("90.00")

    def test_update_accepts_all_billing_fields(self):
        payload = EmpresaUpdate(
            lifecycle_stage="operativo",
            monthly_amount=Decimal("3999.00"),
            billing_interval="annual",
            payment_day=5,
            expected_close_date=date(2026, 6, 1),
            cancellation_scheduled_at=None,
            constancia_object_key="constancias/abc.pdf",
        )
        assert payload.lifecycle_stage == "operativo"
        assert payload.billing_interval == "annual"

    def test_update_partial_mode_skips_unset(self):
        payload = EmpresaUpdate(lifecycle_stage="demo")
        dumped = payload.model_dump(exclude_unset=True)
        assert dumped == {"lifecycle_stage": "demo"}

    def test_list_response_includes_lifecycle_and_version(self):
        response = EmpresaListResponse(
            id="11111111-1111-1111-1111-111111111111",
            name="Test",
            logo_url=None,
            status="operativo",
            lifecycle_stage="operativo",
            ball_on=None,
            summary_note=None,
            monthly_amount=Decimal("3999.00"),
            billing_interval="monthly",
            payment_day=5,
            last_paid_date=None,
            expected_close_date=None,
            grandfathered=False,
            version=3,
        )
        assert response.lifecycle_stage == "operativo"
        assert response.version == 3


class TestBusinessRules:
    def test_operativo_requires_linked_active_subscription(self):
        with pytest.raises(HTTPException) as exc:
            _enforce_business_rules(
                lifecycle_stage="operativo",
                eva_account_id=None,
                subscription_status=None,
                expected_close_date=None,
            )
        assert exc.value.status_code == 409
        assert exc.value.detail["reason"] == "OperativoRequiresActiveSubscription"

    def test_operativo_allowed_with_active_subscription(self):
        _enforce_business_rules(
            lifecycle_stage="operativo",
            eva_account_id="11111111-1111-1111-1111-111111111111",
            subscription_status="active",
            expected_close_date=None,
        )  # No exception.

    def test_operativo_grandfathered_row_exempt(self):
        # Legacy row (migration backfill) — even without active sub, allowed.
        _enforce_business_rules(
            lifecycle_stage="operativo",
            eva_account_id=None,
            subscription_status=None,
            expected_close_date=None,
            grandfathered=True,
        )

    def test_stages_requiring_close_date_reject_missing_date(self):
        for stage in ("interesado", "demo", "negociacion"):
            with pytest.raises(HTTPException) as exc:
                _enforce_business_rules(
                    lifecycle_stage=stage,
                    eva_account_id=None,
                    subscription_status=None,
                    expected_close_date=None,
                )
            assert exc.value.status_code == 400
            assert exc.value.detail["reason"] == "ExpectedCloseDateRequired"

    def test_stage_requiring_close_date_accepts_when_present(self):
        _enforce_business_rules(
            lifecycle_stage="demo",
            eva_account_id=None,
            subscription_status=None,
            expected_close_date=date(2026, 5, 1),
        )

    def test_prospecto_stage_has_no_close_date_requirement(self):
        _enforce_business_rules(
            lifecycle_stage="prospecto",
            eva_account_id=None,
            subscription_status=None,
            expected_close_date=None,
        )


class TestEmpresaInteractionSchema:
    def test_create_accepts_minimum_fields(self):
        payload = EmpresaInteractionCreate(
            type="call",
            summary="Intro call",
            date=date(2026, 4, 10),
        )
        assert payload.type == "call"
