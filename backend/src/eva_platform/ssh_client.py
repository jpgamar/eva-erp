"""Async SSH client for infrastructure operations on OpenClaw runtime hosts."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import PurePosixPath

import asyncssh

from src.common.config import settings

logger = logging.getLogger(__name__)

# Validation patterns
_CONTAINER_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")
_IP_RE = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
_MAX_OCTET = 255


def _validate_container_name(name: str) -> str:
    if not _CONTAINER_NAME_RE.match(name) or len(name) > 128:
        raise ValueError(f"Invalid container name: {name!r}")
    return name


def _validate_ip(ip: str) -> str:
    if not _IP_RE.match(ip) or any(int(o) > _MAX_OCTET for o in ip.split(".")):
        raise ValueError(f"Invalid IP address: {ip!r}")
    return ip


def _sanitize_path(path: str) -> str:
    """Reject obviously malicious path components but allow full filesystem access."""
    resolved = PurePosixPath(path)
    # Reject paths with .. components
    for part in resolved.parts:
        if part == "..":
            raise ValueError(f"Path traversal not allowed: {path!r}")
    # Ensure absolute
    if not resolved.is_absolute():
        raise ValueError(f"Path must be absolute: {path!r}")
    return str(resolved)


def _resolve_ssh_key_path() -> str:
    """Resolve SSH private key to a file path.

    Priority:
    1. EVA_SSH_PRIVATE_KEY_PATH env var (explicit file path)
    2. EVA_SSH_PRIVATE_KEY_BASE64 setting (base64-encoded key → temp file)
    """
    explicit_path = os.environ.get("EVA_SSH_PRIVATE_KEY_PATH")
    if explicit_path and os.path.isfile(explicit_path):
        return explicit_path

    key_b64 = settings.eva_ssh_private_key_base64
    if not key_b64:
        raise RuntimeError(
            "No SSH key configured. Set EVA_SSH_PRIVATE_KEY_BASE64 or EVA_SSH_PRIVATE_KEY_PATH."
        )

    try:
        key_bytes = base64.b64decode(key_b64)
    except Exception as exc:
        raise RuntimeError(f"EVA_SSH_PRIVATE_KEY_BASE64 contains invalid base64: {exc}") from exc
    fingerprint = hashlib.sha256(key_bytes).hexdigest()[:16]
    key_path = os.path.join(tempfile.gettempdir(), f"eva_erp_ssh_{fingerprint}")

    if not os.path.isfile(key_path):
        with open(key_path, "wb") as f:
            f.write(key_bytes)
        os.chmod(key_path, stat.S_IRUSR)

    return key_path


class InfraSSHClient:
    """Async SSH client for infrastructure operations on OpenClaw hosts.

    Uses asyncssh for native async support with built-in SFTP.
    Connections are per-request (SSH multiplexing handles concurrent ops).
    """

    async def _connect(self, host_ip: str) -> asyncssh.SSHClientConnection:
        _validate_ip(host_ip)
        key_path = _resolve_ssh_key_path()
        return await asyncssh.connect(
            host_ip,
            username="root",
            client_keys=[key_path],
            known_hosts=None,  # Hetzner hosts are ephemeral
            connect_timeout=10,
        )

    async def _run_command(
        self, host_ip: str, command: str, *, timeout: int = 30
    ) -> str:
        """Run a remote command and return stdout.  Internal only."""
        async with await self._connect(host_ip) as conn:
            result = await conn.run(command, check=True, timeout=timeout)
            return result.stdout or ""

    async def docker_status(self, host_ip: str) -> list[dict]:
        """Get status of all Docker containers on a host."""
        async with await self._connect(host_ip) as conn:
            result = await conn.run(
                "docker ps -a --format json", check=False, timeout=30
            )
            stdout = result.stdout or ""
            containers = []
            for line in stdout.strip().splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    containers.append(
                        {
                            "name": data.get("Names", ""),
                            "state": data.get("State", ""),
                            "status": data.get("Status", ""),
                            "ports": data.get("Ports", ""),
                            "image": data.get("Image", ""),
                            "created_at": data.get("CreatedAt", ""),
                        }
                    )
                except json.JSONDecodeError:
                    logger.warning("Failed to parse docker ps line: %s", line[:200])
            return containers

    async def docker_logs(
        self, host_ip: str, container_name: str, *, tail: int = 100
    ) -> str:
        """Get recent logs from a Docker container."""
        _validate_container_name(container_name)
        tail = min(max(tail, 1), 500)
        async with await self._connect(host_ip) as conn:
            result = await conn.run(
                f"docker logs --tail {tail} {container_name} 2>&1",
                check=False,
                timeout=30,
            )
            return result.stdout or ""

    async def list_directory(
        self, host_ip: str, path: str = "/root/.openclaw/"
    ) -> list[dict]:
        """List directory contents via SFTP."""
        path = _sanitize_path(path)
        async with await self._connect(host_ip) as conn:
            async with conn.start_sftp_client() as sftp:
                entries = []
                async for entry in sftp.scandir(path):
                    name = entry.filename
                    if name in (".", ".."):
                        continue
                    attrs = entry.attrs
                    is_dir = bool(attrs.permissions and stat.S_ISDIR(attrs.permissions))
                    modified_at = None
                    if attrs.mtime is not None:
                        modified_at = datetime.fromtimestamp(
                            attrs.mtime, tz=timezone.utc
                        ).isoformat()
                    entries.append(
                        {
                            "name": name,
                            "path": f"{path.rstrip('/')}/{name}",
                            "is_dir": is_dir,
                            "size": attrs.size if not is_dir else None,
                            "modified_at": modified_at,
                        }
                    )
                # Sort: directories first, then alphabetically
                entries.sort(key=lambda e: (not e["is_dir"], e["name"].lower()))
                return entries

    async def read_file(
        self, host_ip: str, path: str, *, max_bytes: int = 1_048_576
    ) -> dict:
        """Read file content via SFTP (capped at max_bytes)."""
        path = _sanitize_path(path)
        async with await self._connect(host_ip) as conn:
            async with conn.start_sftp_client() as sftp:
                file_attrs = await sftp.stat(path)
                file_size = file_attrs.size or 0
                truncated = file_size > max_bytes

                async with sftp.open(path, "rb") as f:
                    raw = await f.read(max_bytes)

                try:
                    content = raw.decode("utf-8")
                except UnicodeDecodeError:
                    content = f"[Binary file, {file_size} bytes]"

                return {
                    "path": path,
                    "content": content,
                    "size": file_size,
                    "truncated": truncated,
                }


# Module-level singleton
infra_ssh = InfraSSHClient()
