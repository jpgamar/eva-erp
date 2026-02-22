import logging
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from jose import jwt
from passlib.context import CryptContext

from src.common.config import settings

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: uuid.UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(user_id), "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: uuid.UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    payload = {"sub": str(user_id), "exp": expire, "type": "refresh"}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload
    except Exception:
        return None


async def sync_password_to_supabase(email: str, new_password: str) -> None:
    """Sync a password change to Supabase Auth (best-effort).

    Uses the Supabase Admin API to find the user by email and update
    their password. Failures are logged but never raised so the caller's
    own password-change flow is not disrupted.
    """
    if not settings.supabase_url or not settings.supabase_service_role_key:
        logger.warning("Supabase not configured, skipping password sync")
        return

    headers = {
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "apikey": settings.supabase_service_role_key,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Find the Supabase user by email (paginated)
            supabase_uid: str | None = None
            page = 1
            while True:
                resp = await client.get(
                    f"{settings.supabase_url}/auth/v1/admin/users",
                    headers=headers,
                    params={"page": page, "per_page": 50},
                )
                resp.raise_for_status()
                data = resp.json()
                users = data.get("users", []) if isinstance(data, dict) else data
                for u in users:
                    if u.get("email", "").lower() == email.lower():
                        supabase_uid = u["id"]
                        break
                if supabase_uid or len(users) < 50:
                    break
                page += 1

            if not supabase_uid:
                logger.warning("No Supabase user found for %s, skipping sync", email)
                return

            # Update password
            resp = await client.put(
                f"{settings.supabase_url}/auth/v1/admin/users/{supabase_uid}",
                headers=headers,
                json={"password": new_password},
            )
            resp.raise_for_status()
            logger.info("Password synced to Supabase for %s", email)
    except Exception:
        logger.warning("Failed to sync password to Supabase for %s", email, exc_info=True)
