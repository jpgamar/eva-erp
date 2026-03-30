from __future__ import annotations

import asyncio
import base64
import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from src.auth.dependencies import get_current_user, require_admin
from src.auth.models import User
from src.auth.service import create_access_token, decode_token
from src.common.config import settings
from src.common.database import async_session
from src.terminal.pty_manager import PtySession, SessionManager

logger = logging.getLogger(__name__)

router = APIRouter()

# Global session manager — initialized once, lives for the app lifetime.
session_manager = SessionManager()


async def _authenticate(ws: WebSocket) -> User | None:
    """Authenticate via cookie from the WebSocket handshake, or via an auth message."""
    token: str | None = None

    # 1. Try to read the HttpOnly cookie from the handshake headers
    token = ws.cookies.get("erp_access_token")

    # 2. Fallback: wait for an explicit auth message
    if not token:
        try:
            raw = await asyncio.wait_for(ws.receive_text(), timeout=10)
            msg = json.loads(raw)
            if msg.get("type") == "auth" and msg.get("token"):
                token = msg["token"]
        except (asyncio.TimeoutError, WebSocketDisconnect, json.JSONDecodeError):
            pass

    if not token:
        await ws.send_json({"type": "error", "message": "No auth token found"})
        return None

    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        await ws.send_json({"type": "error", "message": "Invalid or expired token"})
        return None

    user_id = uuid.UUID(payload["sub"])

    async with async_session() as db:
        result = await db.execute(
            select(User).where(User.id == user_id, User.is_active == True)
        )
        user = result.scalar_one_or_none()

    if not user:
        await ws.send_json({"type": "error", "message": "User not found"})
        return None

    if user.role != "admin":
        await ws.send_json({"type": "error", "message": "Admin access required"})
        await ws.close(code=4403, reason="Forbidden")
        return None

    return user


async def _pty_output_loop(ws: WebSocket, session: PtySession) -> None:
    """Read PTY output and forward to WebSocket."""
    loop = asyncio.get_event_loop()
    while session.is_alive():
        try:
            data = await loop.run_in_executor(None, session.read)
        except Exception:
            break
        if data:
            encoded = base64.b64encode(data).decode("ascii")
            try:
                await ws.send_json({"type": "output", "data": encoded})
            except Exception:
                break
        else:
            # No data available — brief sleep to avoid busy-waiting
            await asyncio.sleep(0.01)

    # Process exited
    exit_code = session.process.returncode
    try:
        await ws.send_json({"type": "exit", "code": exit_code})
    except Exception:
        pass


async def _ws_input_loop(ws: WebSocket, session: PtySession) -> None:
    """Read WebSocket messages and forward to PTY."""
    while True:
        try:
            raw = await ws.receive_text()
        except WebSocketDisconnect:
            break

        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue

        msg_type = msg.get("type")

        if msg_type == "input":
            data = base64.b64decode(msg.get("data", ""))
            session.write(data)

        elif msg_type == "resize":
            cols = msg.get("cols", 120)
            rows = msg.get("rows", 40)
            session.resize(cols, rows)

        elif msg_type == "ping":
            try:
                await ws.send_json({"type": "pong"})
            except Exception:
                break


@router.get("/api/v1/terminal/token")
async def get_terminal_token(user: User = Depends(require_admin)):
    """Return a short-lived JWT for WebSocket auth (admin only)."""
    if not settings.terminal_enabled:
        raise HTTPException(status_code=403, detail="Terminal feature disabled")
    token = create_access_token(user.id)
    return {"token": token}


@router.websocket("/ws/terminal")
async def terminal_ws(ws: WebSocket) -> None:
    if not settings.terminal_enabled:
        await ws.close(code=4403, reason="Terminal feature disabled")
        return

    await ws.accept()

    user = await _authenticate(ws)
    if not user:
        try:
            await ws.close(code=4401, reason="Authentication failed")
        except Exception:
            pass
        return

    user_id_str = str(user.id)

    # Reattach to existing session or create a new one
    session = session_manager.get_user_session(user_id_str)
    if session is None:
        session = session_manager.create_session(user_id_str)

    await ws.send_json({"type": "ready", "session_id": session.session_id})

    # Run input and output loops concurrently
    output_task = asyncio.create_task(_pty_output_loop(ws, session))
    input_task = asyncio.create_task(_ws_input_loop(ws, session))

    try:
        done, pending = await asyncio.wait(
            [output_task, input_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    except Exception:
        output_task.cancel()
        input_task.cancel()

    # Don't destroy the session on disconnect — allow reattach
    logger.info("Terminal WebSocket closed for user %s (session %s)", user.email, session.session_id)
