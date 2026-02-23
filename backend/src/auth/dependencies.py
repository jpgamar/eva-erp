import hmac
import logging
import uuid

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.models import User
from src.auth.service import decode_token
from src.common.config import settings
from src.common.database import get_db

logger = logging.getLogger(__name__)
AGENT_KEY_HEADER = "x-agent-key"


async def _resolve_agent_actor_user(db: AsyncSession) -> User:
    if settings.agent_api_actor_email:
        result = await db.execute(
            select(User).where(
                User.email == settings.agent_api_actor_email,
                User.is_active == True,
            )
        )
        user = result.scalar_one_or_none()
        if user:
            return user
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Agent actor user is missing or inactive",
        )

    # Fallback for fast setup: first active admin account in the ERP.
    result = await db.execute(
        select(User)
        .where(User.role == "admin", User.is_active == True)
        .order_by(User.created_at.asc())
    )
    user = result.scalars().first()
    if user:
        return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No active admin user available for agent authentication",
    )


async def _authenticate_with_agent_key(request: Request, db: AsyncSession) -> User | None:
    key = request.headers.get(AGENT_KEY_HEADER)
    if not key:
        return None

    configured_key = settings.agent_api_key.strip()
    if not configured_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Agent API key auth is not configured",
        )

    if not hmac.compare_digest(key.strip(), configured_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid agent API key",
        )

    actor = await _resolve_agent_actor_user(db)
    request.state.agent_authenticated = True
    request.state.auth_mode = "agent_api_key"
    request.state.auth_actor_email = actor.email
    logger.info("Agent API key authenticated for %s %s", request.method, request.url.path)
    return actor


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    agent_user = await _authenticate_with_agent_key(request, db)
    if agent_user is not None:
        return agent_user

    token = request.cookies.get("erp_access_token")
    if not token:
        # Also check Authorization header as fallback
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user_id = uuid.UUID(payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id, User.is_active == True))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user


async def require_agent_user(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> User:
    if not getattr(request.state, "agent_authenticated", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent API key required",
        )
    return current_user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user
