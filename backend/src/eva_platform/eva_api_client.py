"""Small Eva admin API client for OpenClaw operator workflows."""

from __future__ import annotations

from typing import Any

import httpx

from src.common.config import settings


class EvaAdminApiClient:
    def __init__(self) -> None:
        self._base_url = (settings.eva_api_base_url or "").rstrip("/")
        self._admin_api_key = (settings.eva_admin_api_key or "").strip()
        self._timeout = max(5.0, float(settings.eva_api_timeout_seconds or 20.0))

    def _headers(self) -> dict[str, str]:
        return {
            "X-Admin-Key": self._admin_api_key,
            "Content-Type": "application/json",
        }

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        if not self._base_url:
            raise RuntimeError("eva_api_base_url is not configured")
        if not self._admin_api_key:
            raise RuntimeError("eva_admin_api_key is not configured")

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.request(
                method.upper(),
                f"{self._base_url}/api/v1{path}",
                headers=self._headers(),
                json=json,
                params=params,
            )
        response.raise_for_status()
        return response.json()


eva_admin_api_client = EvaAdminApiClient()
