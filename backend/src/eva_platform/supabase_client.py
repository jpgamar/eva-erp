"""Lightweight httpx client for Supabase Admin API.

Only implements the two operations needed for Eva OPS:
- admin_create_user: Provision a new Supabase auth user
- admin_generate_link: Generate a magic link for impersonation
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from src.common.config import settings

logger = logging.getLogger(__name__)


class SupabaseAdminError(Exception):
    def __init__(self, message: str, *, error_code: str = "supabase_admin_error"):
        super().__init__(message)
        self.error_code = error_code


class SupabaseConfigError(SupabaseAdminError):
    def __init__(self, message: str):
        super().__init__(message, error_code="supabase_config_error")


class SupabaseUpstreamUnavailableError(SupabaseAdminError):
    def __init__(self, message: str):
        super().__init__(message, error_code="supabase_upstream_unavailable")


class SupabaseInvalidPayloadError(SupabaseAdminError):
    def __init__(self, message: str):
        super().__init__(message, error_code="supabase_invalid_payload")


class SupabaseDuplicateUnresolvedError(SupabaseAdminError):
    def __init__(self, message: str):
        super().__init__(message, error_code="owner_duplicate_unresolved")


def map_supabase_error_to_http(exc: SupabaseAdminError) -> tuple[int, str]:
    if isinstance(exc, SupabaseDuplicateUnresolvedError):
        return 409, str(exc)
    if isinstance(exc, SupabaseUpstreamUnavailableError):
        return 503, str(exc)
    if isinstance(exc, SupabaseInvalidPayloadError):
        return 502, str(exc)
    if isinstance(exc, SupabaseConfigError):
        return 500, str(exc)
    return 400, str(exc)


def _is_duplicate_user_error(status_code: int, message: str, code: str = "") -> bool:
    if status_code not in {400, 409, 422}:
        return False

    normalized_message = (message or "").strip().lower()
    normalized_code = (code or "").strip().lower()

    duplicate_codes = {"email_exists", "user_already_exists", "duplicate_email"}
    if normalized_code in duplicate_codes:
        return True

    duplicate_markers = (
        "already been registered",
        "already registered",
        "already exists",
        "email exists",
        "usuario ya esta registrado",
        "usuario ya está registrado",
        "ya se encuentra registrado",
    )
    return any(marker in normalized_message for marker in duplicate_markers)


class SupabaseAdminClient:
    """Stateless Supabase Admin API client using httpx."""

    @staticmethod
    def _headers() -> dict[str, str]:
        return {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _base_url() -> str:
        url = settings.supabase_url.rstrip("/")
        if not url:
            raise SupabaseConfigError("Provisioning is not configured (missing SUPABASE_URL)")
        if not settings.supabase_service_role_key:
            raise SupabaseConfigError("Provisioning is not configured (missing SUPABASE_SERVICE_ROLE_KEY)")
        return url

    @staticmethod
    def _extract_user_id(user_payload: dict[str, Any]) -> str:
        user_id = (
            user_payload.get("id")
            or (user_payload.get("user") or {}).get("id")
            or (user_payload.get("properties") or {}).get("user_id")
        )
        if not user_id:
            raise SupabaseInvalidPayloadError("Provisioning provider returned an invalid user payload")
        return str(user_id)

    @classmethod
    def extract_user_id(cls, user_payload: dict[str, Any]) -> str:
        return cls._extract_user_id(user_payload)

    @staticmethod
    def _extract_error(resp: httpx.Response) -> tuple[str, str]:
        body: dict[str, Any] = {}
        if resp.headers.get("content-type", "").startswith("application/json"):
            try:
                parsed = resp.json()
                if isinstance(parsed, dict):
                    body = parsed
            except ValueError:
                body = {}
        message = body.get("msg") or body.get("message") or body.get("error") or resp.text
        code = body.get("code") or ""
        return str(message), str(code)

    @classmethod
    async def _request_with_retries(
        cls,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        retryable_statuses = {408, 429, 500, 502, 503, 504}
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                resp = await client.request(method, url, **kwargs)
            except httpx.RequestError as exc:
                if attempt == max_attempts:
                    raise SupabaseUpstreamUnavailableError(
                        "Provisioning service temporarily unavailable. Please try again."
                    ) from exc
                await asyncio.sleep(0.25 * attempt)
                continue

            if resp.status_code in retryable_statuses and attempt < max_attempts:
                await asyncio.sleep(0.25 * attempt)
                continue

            if resp.status_code in retryable_statuses and attempt == max_attempts:
                raise SupabaseUpstreamUnavailableError(
                    "Provisioning service temporarily unavailable. Please try again."
                )
            return resp

        raise SupabaseUpstreamUnavailableError("Provisioning service temporarily unavailable. Please try again.")

    @staticmethod
    def _parse_users_payload(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, dict):
            users = payload.get("users", [])
            if isinstance(users, list):
                return [u for u in users if isinstance(u, dict)]
            return []
        if isinstance(payload, list):
            return [u for u in payload if isinstance(u, dict)]
        return []

    @staticmethod
    def _matching_user(users: list[dict[str, Any]], normalized_email: str) -> dict[str, Any] | None:
        for user in users:
            candidate_email = (user.get("email") or "").strip().lower()
            if candidate_email == normalized_email:
                return user
        return None

    @classmethod
    async def admin_create_user(
        cls,
        email: str,
        password: str,
        user_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a Supabase user via the admin API.

        Returns the user object dict with at least 'id' and 'email'.
        """
        normalized_email = email.strip().lower()
        payload = {
            "email": normalized_email,
            "password": password,
            "email_confirm": True,
            "user_metadata": user_metadata or {},
        }

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await cls._request_with_retries(
                client,
                "POST",
                f"{cls._base_url()}/auth/v1/admin/users",
                headers=cls._headers(),
                json=payload,
            )

        if resp.status_code == 200:
            data = resp.json()
            cls._extract_user_id(data)
            return data

        msg, error_code = cls._extract_error(resp)
        if _is_duplicate_user_error(resp.status_code, str(msg), str(error_code)):
            logger.info("User %s already exists in Supabase, looking up...", normalized_email)
            existing = await cls._lookup_user_by_email(normalized_email)
            if existing:
                cls._extract_user_id(existing)
                return existing
            raise SupabaseDuplicateUnresolvedError(
                "Account owner email is already registered but could not be linked. Please retry."
            )

        logger.error("Supabase admin_create_user failed: %s %s", resp.status_code, msg)
        raise SupabaseAdminError(f"Failed to create user: {msg}")

    @classmethod
    async def admin_generate_link(
        cls,
        email: str,
        link_type: str = "magiclink",
    ) -> str:
        """Generate a magic link URL for a Supabase user.

        Returns the full action link URL.
        """
        normalized_email = email.strip().lower()
        payload = {
            "email": normalized_email,
            "type": link_type,
        }

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await cls._request_with_retries(
                client,
                "POST",
                f"{cls._base_url()}/auth/v1/admin/generate_link",
                headers=cls._headers(),
                json=payload,
            )

        if resp.status_code == 200:
            data = resp.json()
            return data.get("action_link") or data.get("properties", {}).get("action_link", "")

        msg, _ = cls._extract_error(resp)
        logger.error("Supabase admin_generate_link failed: %s %s", resp.status_code, msg)
        raise SupabaseAdminError(f"Failed to generate link: {msg}")

    @classmethod
    async def _lookup_user_by_email(cls, email: str) -> dict[str, Any] | None:
        """Search Supabase admin users for matching email."""
        normalized = email.strip().lower()
        filtered = await cls._lookup_user_by_email_filtered(normalized)
        if filtered:
            return filtered
        return await cls._lookup_user_by_email_paginated(normalized)

    @classmethod
    async def _lookup_user_by_email_filtered(cls, normalized: str) -> dict[str, Any] | None:
        """Primary lookup using Supabase admin filter parameter."""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await cls._request_with_retries(
                client,
                "GET",
                f"{cls._base_url()}/auth/v1/admin/users",
                headers=cls._headers(),
                params={"page": 1, "per_page": 50, "filter": normalized},
            )
            if resp.status_code != 200:
                return None
            users = cls._parse_users_payload(resp.json())
            return cls._matching_user(users, normalized)

    @classmethod
    async def _lookup_user_by_email_paginated(cls, normalized: str) -> dict[str, Any] | None:
        """Fallback lookup scanning all pages with bounded retries."""
        page = 1
        per_page = 50

        async with httpx.AsyncClient(timeout=15) as client:
            while True:
                resp = await cls._request_with_retries(
                    client,
                    "GET",
                    f"{cls._base_url()}/auth/v1/admin/users",
                    headers=cls._headers(),
                    params={"page": page, "per_page": per_page},
                )
                if resp.status_code != 200:
                    break

                users = cls._parse_users_payload(resp.json())
                if not users:
                    break

                user = cls._matching_user(users, normalized)
                if user:
                    return user

                if len(users) < per_page:
                    break
                page += 1

        return None
