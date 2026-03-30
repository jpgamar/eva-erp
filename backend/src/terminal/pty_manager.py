from __future__ import annotations

import asyncio
import fcntl
import logging
import os
import pty
import signal
import struct
import subprocess
import termios
import uuid
from datetime import datetime, timezone

from src.common.config import settings

logger = logging.getLogger(__name__)

# Environment variables safe to pass to child PTY processes.
_SAFE_ENV_KEYS = {"PATH", "HOME", "LANG", "TERM", "SHELL", "USER", "LOGNAME"}
_EXTRA_ENV = {
    "TERM": "xterm-256color",
    "COLORTERM": "truecolor",
}


def _build_child_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for key in _SAFE_ENV_KEYS:
        val = os.environ.get(key)
        if val:
            env[key] = val
    env.update(_EXTRA_ENV)

    # Git identity
    for key in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
        val = os.environ.get(key)
        if val:
            env[key] = val

    return env


class PtySession:
    """Wraps a PTY child process with async I/O helpers."""

    def __init__(
        self,
        session_id: str,
        user_id: str,
        master_fd: int,
        slave_fd: int,
        process: subprocess.Popen,
    ):
        self.session_id = session_id
        self.user_id = user_id
        self.master_fd = master_fd
        self.slave_fd = slave_fd
        self.process = process
        self.created_at = datetime.now(timezone.utc)
        self.last_activity = datetime.now(timezone.utc)
        self._closed = False

    # -- factory ----------------------------------------------------------

    @classmethod
    def create(cls, user_id: str, cols: int = 120, rows: int = 40) -> PtySession:
        master_fd, slave_fd = pty.openpty()

        # Set initial window size
        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, winsize)

        # Make master non-blocking for async reads
        flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
        fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        working_dir = settings.terminal_working_dir or os.getcwd()

        shell = os.environ.get("SHELL", "/bin/bash")
        process = subprocess.Popen(
            [shell, "-l"],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            preexec_fn=os.setsid,
            env=_build_child_env(),
            cwd=working_dir,
            close_fds=True,
        )

        session_id = uuid.uuid4().hex[:12]
        logger.info("PTY session %s created for user %s (pid=%d)", session_id, user_id, process.pid)
        return cls(
            session_id=session_id,
            user_id=user_id,
            master_fd=master_fd,
            slave_fd=slave_fd,
            process=process,
        )

    # -- I/O --------------------------------------------------------------

    def write(self, data: bytes) -> None:
        if self._closed:
            return
        self.last_activity = datetime.now(timezone.utc)
        try:
            os.write(self.master_fd, data)
        except OSError:
            pass

    def read(self, bufsize: int = 65536) -> bytes:
        if self._closed:
            return b""
        try:
            return os.read(self.master_fd, bufsize)
        except (OSError, BlockingIOError):
            return b""

    def resize(self, cols: int, rows: int) -> None:
        if self._closed:
            return
        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        try:
            fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)
        except OSError:
            pass

    # -- lifecycle ---------------------------------------------------------

    def is_alive(self) -> bool:
        if self._closed:
            return False
        return self.process.poll() is None

    def terminate(self) -> int | None:
        if self._closed:
            return self.process.returncode
        self._closed = True

        # Kill the entire process group
        try:
            os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
        except (OSError, ProcessLookupError):
            pass

        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
            except (OSError, ProcessLookupError):
                pass
            self.process.wait(timeout=2)

        # Close file descriptors
        for fd in (self.master_fd, self.slave_fd):
            try:
                os.close(fd)
            except OSError:
                pass

        logger.info("PTY session %s terminated (exit=%s)", self.session_id, self.process.returncode)
        return self.process.returncode


class SessionManager:
    """Tracks active PTY sessions. One session per user."""

    def __init__(self) -> None:
        self._sessions: dict[str, PtySession] = {}  # session_id -> session
        self._user_sessions: dict[str, str] = {}  # user_id -> session_id

    def create_session(self, user_id: str, cols: int = 120, rows: int = 40) -> PtySession:
        # Kill existing session for this user
        existing_id = self._user_sessions.get(user_id)
        if existing_id:
            self.destroy_session(existing_id)

        session = PtySession.create(user_id, cols, rows)
        self._sessions[session.session_id] = session
        self._user_sessions[user_id] = session.session_id
        return session

    def get_session(self, session_id: str) -> PtySession | None:
        return self._sessions.get(session_id)

    def get_user_session(self, user_id: str) -> PtySession | None:
        sid = self._user_sessions.get(user_id)
        if sid:
            session = self._sessions.get(sid)
            if session and session.is_alive():
                return session
            # Dead session — clean up
            self.destroy_session(sid)
        return None

    def destroy_session(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session:
            self._user_sessions.pop(session.user_id, None)
            session.terminate()

    def destroy_all(self) -> None:
        for session in list(self._sessions.values()):
            session.terminate()
        self._sessions.clear()
        self._user_sessions.clear()

    def cleanup_idle(self, max_idle_seconds: int | None = None) -> int:
        timeout = max_idle_seconds or settings.terminal_idle_timeout_seconds
        now = datetime.now(timezone.utc)
        cleaned = 0
        for sid, session in list(self._sessions.items()):
            idle = (now - session.last_activity).total_seconds()
            if idle > timeout or not session.is_alive():
                self.destroy_session(sid)
                cleaned += 1
        return cleaned
