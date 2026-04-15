from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx

from src.common.config import settings


class EvaBillingClientError(RuntimeError):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class EvaBillingClient:
    def __init__(self, *, base_url: str | None = None, secret: str | None = None) -> None:
        self._base_url = (base_url or settings.eva_api_base_url or "").rstrip("/")
        self._secret = (secret or settings.eva_billing_bridge_secret or "").strip()

    def _ensure_configured(self) -> None:
        if not self._base_url:
            raise EvaBillingClientError(503, "Eva billing API base URL is not configured")
        if not self._secret:
            raise EvaBillingClientError(503, "Eva billing bridge secret is not configured")

    def _headers(self, raw_body: bytes, *, idempotency_key: str | None = None) -> dict[str, str]:
        self._ensure_configured()
        timestamp = str(int(datetime.now(timezone.utc).timestamp()))
        message = f"{timestamp}.{raw_body.decode('utf-8')}".encode("utf-8")
        signature = hmac.new(self._secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "X-Eva-Billing-Timestamp": timestamp,
            "X-Eva-Billing-Signature": signature,
        }
        if idempotency_key:
            headers["X-Eva-Billing-Idempotency-Key"] = idempotency_key
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        raw_body = b""
        kwargs: dict[str, Any] = {"headers": self._headers(raw_body, idempotency_key=idempotency_key)}
        if payload is not None:
            raw_body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
            kwargs = {"headers": self._headers(raw_body, idempotency_key=idempotency_key), "content": raw_body}

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.request(
                method,
                f"{self._base_url}{path}",
                **kwargs,
            )
        if response.status_code >= 400:
            detail = response.text
            try:
                body = response.json()
                if isinstance(body, dict):
                    maybe_detail = body.get("detail")
                    if isinstance(maybe_detail, str) and maybe_detail.strip():
                        detail = maybe_detail
            except Exception:
                pass
            raise EvaBillingClientError(response.status_code, detail)
        return response.json()

    async def get_status(self, account_id: UUID) -> dict[str, Any]:
        return await self._request("GET", f"/api/v1/internal/erp-billing/accounts/{account_id}/status")

    async def create_checkout_link(
        self,
        *,
        account_id: UUID,
        plan_tier: str | None = None,
        billing_interval: str | None = None,
        billing_subscription_cfdi_enabled: bool | None = None,
    ) -> dict[str, Any]:
        payload = {
            "account_id": str(account_id),
            "plan_tier": plan_tier,
            "billing_interval": billing_interval,
            "billing_subscription_cfdi_enabled": billing_subscription_cfdi_enabled,
        }
        return await self._request(
            "POST",
            f"/api/v1/internal/erp-billing/accounts/{account_id}/checkout-link",
            payload=payload,
        )

    async def retry_document(self, *, account_id: UUID, document_id: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/api/v1/internal/erp-billing/accounts/{account_id}/documents/{document_id}/retry",
            payload={},
        )

    # ------------------------------------------------------------------
    # Phase 4: ERP-driven subscription management.
    # ------------------------------------------------------------------

    async def set_fiscal_profile(
        self,
        *,
        account_id: UUID,
        billing_legal_name: str,
        billing_tax_id: str,
        billing_tax_regime: str,
        billing_postal_code: str,
        billing_cfdi_use: str,
        billing_person_type: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "billing_legal_name": billing_legal_name,
            "billing_tax_id": billing_tax_id,
            "billing_tax_regime": billing_tax_regime,
            "billing_postal_code": billing_postal_code,
            "billing_cfdi_use": billing_cfdi_use,
            "billing_person_type": billing_person_type,
        }
        return await self._request(
            "POST",
            f"/api/v1/internal/erp-billing/accounts/{account_id}/fiscal-profile",
            payload=payload,
            idempotency_key=idempotency_key,
        )

    async def preview_subscription(
        self,
        *,
        account_id: UUID,
        plan_tier: str,
        billing_interval: str,
        base_subtotal_minor: int,
        erp_description: str | None = None,
        empresa_id: UUID | str | None = None,
        proration_behavior: str = "always_invoice",
    ) -> dict[str, Any]:
        payload = {
            "plan_tier": plan_tier,
            "billing_interval": billing_interval,
            "base_subtotal_minor": int(base_subtotal_minor),
            "erp_description": erp_description,
            "empresa_id": str(empresa_id) if empresa_id else None,
            "proration_behavior": proration_behavior,
            "dry_run": True,
        }
        return await self._request(
            "POST",
            f"/api/v1/internal/erp-billing/accounts/{account_id}/subscription/preview",
            payload=payload,
        )

    async def reprice_subscription(
        self,
        *,
        account_id: UUID,
        plan_tier: str,
        billing_interval: str,
        base_subtotal_minor: int,
        erp_description: str | None = None,
        empresa_id: UUID | str | None = None,
        proration_behavior: str = "always_invoice",
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "plan_tier": plan_tier,
            "billing_interval": billing_interval,
            "base_subtotal_minor": int(base_subtotal_minor),
            "erp_description": erp_description,
            "empresa_id": str(empresa_id) if empresa_id else None,
            "proration_behavior": proration_behavior,
            "dry_run": False,
        }
        return await self._request(
            "POST",
            f"/api/v1/internal/erp-billing/accounts/{account_id}/subscription",
            payload=payload,
            idempotency_key=idempotency_key,
        )

    async def cancel_subscription(
        self,
        *,
        account_id: UUID,
        at_period_end: bool = True,
        cancel_reason: str | None = None,
        empresa_id: UUID | str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "at_period_end": at_period_end,
            "cancel_reason": cancel_reason,
            "empresa_id": str(empresa_id) if empresa_id else None,
        }
        return await self._request(
            "POST",
            f"/api/v1/internal/erp-billing/accounts/{account_id}/subscription/cancel",
            payload=payload,
            idempotency_key=idempotency_key,
        )
