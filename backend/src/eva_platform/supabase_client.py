"""Lightweight httpx client for Supabase Admin API.

Only implements the two operations needed for Eva OPS:
- admin_create_user: Provision a new Supabase auth user
- admin_generate_link: Generate a magic link for impersonation
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from src.common.config import settings

logger = logging.getLogger(__name__)


class SupabaseAdminError(Exception):
    pass


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
            raise SupabaseAdminError("SUPABASE_URL is not configured")
        return url

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
        normalized_email = email.strip()
        payload = {
            "email": normalized_email,
            "password": password,
            "email_confirm": True,
            "user_metadata": user_metadata or {},
        }

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{cls._base_url()}/auth/v1/admin/users",
                headers=cls._headers(),
                json=payload,
            )

        if resp.status_code == 200:
            return resp.json()

        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        msg = body.get("msg") or body.get("message") or body.get("error") or resp.text

        # Handle duplicate user
        if resp.status_code == 422 and "already been registered" in str(msg).lower():
            logger.info("User %s already exists in Supabase, looking up...", normalized_email)
            existing = await cls._lookup_user_by_email(normalized_email)
            if existing:
                return existing
            raise SupabaseAdminError(f"User reported as duplicate but not found: {normalized_email}")

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
        normalized_email = email.strip()
        payload = {
            "email": normalized_email,
            "type": link_type,
        }

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{cls._base_url()}/auth/v1/admin/generate_link",
                headers=cls._headers(),
                json=payload,
            )

        if resp.status_code == 200:
            data = resp.json()
            return data.get("action_link") or data.get("properties", {}).get("action_link", "")

        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        msg = body.get("msg") or body.get("message") or resp.text
        logger.error("Supabase admin_generate_link failed: %s %s", resp.status_code, msg)
        raise SupabaseAdminError(f"Failed to generate link: {msg}")

    @classmethod
    async def _lookup_user_by_email(cls, email: str) -> dict[str, Any] | None:
        """Search Supabase admin users for matching email."""
        normalized = email.strip().lower()
        page = 1
        per_page = 50

        async with httpx.AsyncClient(timeout=15) as client:
            while True:
                resp = await client.get(
                    f"{cls._base_url()}/auth/v1/admin/users",
                    headers=cls._headers(),
                    params={"page": page, "per_page": per_page},
                )
                if resp.status_code != 200:
                    break

                data = resp.json()
                users = data.get("users", []) if isinstance(data, dict) else data
                if not users:
                    break

                for user in users:
                    if (user.get("email") or "").strip().lower() == normalized:
                        return user

                if len(users) < per_page:
                    break
                page += 1

        return None
