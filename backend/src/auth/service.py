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
    """Sync a password change to Supabase Auth via the EVA backend (best-effort).

    Calls the EVA backend's /auth/erp-password-sync endpoint which has
    Supabase admin access.  Uses the shared ERP_SSO_SECRET for auth.
    Failures are logged but never raised so the caller's own
    password-change flow is not disrupted.
    """
    if not settings.erp_sso_secret:
        logger.warning("ERP SSO secret not configured, skipping password sync")
        return

    eva_base = "https://api.goeva.ai"
    if settings.environment == "development":
        eva_base = "http://localhost:8000"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{eva_base}/api/v1/auth/erp-password-sync",
                headers={"Authorization": f"Bearer {settings.erp_sso_secret}"},
                json={"email": email, "new_password": new_password},
            )
            if resp.status_code == 404:
                logger.info("No Supabase user for %s, skipping sync", email)
            elif resp.is_success:
                logger.info("Password synced to Supabase (via EVA) for %s", email)
            else:
                logger.warning(
                    "EVA password sync returned %s for %s",
                    resp.status_code, email,
                )
    except Exception:
        logger.warning("Failed to sync password to Supabase for %s", email, exc_info=True)
