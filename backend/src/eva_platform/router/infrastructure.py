"""Infrastructure monitoring endpoints for OpenClaw runtime hosts."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.common.database import get_eva_db
from src.eva_platform.models import (
    EvaAccount,
    EvaOpenclawAgent,
    EvaOpenclawRuntimeAllocation,
    EvaOpenclawRuntimeEvent,
    EvaOpenclawRuntimeHost,
)
from src.eva_platform.schemas import (
    DockerContainerResponse,
    DockerLogsResponse,
    FileContentResponse,
    FileEntryResponse,
    RuntimeEmployeeDetailResponse,
    RuntimeEmployeeResponse,
    RuntimeEventResponse,
    RuntimeHostResponse,
)
from src.eva_platform.ssh_client import infra_ssh

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/infrastructure", tags=["infrastructure"])

ACTIVE_ALLOCATION_STATES = ("placed", "running", "recovering", "error")


# ── Helpers ──────────────────────────────────────────────


async def _validate_host_ip(ip: str, eva_db: AsyncSession) -> None:
    """Ensure the IP belongs to a known runtime host."""
    result = await eva_db.execute(
        select(EvaOpenclawRuntimeHost.id).where(
            EvaOpenclawRuntimeHost.public_ip == ip,
            EvaOpenclawRuntimeHost.state != "released",
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="No active host with that IP")


# ── Endpoints ────────────────────────────────────────────


@router.get("/hosts", response_model=list[RuntimeHostResponse])
async def list_hosts(
    _user=Depends(get_current_user),
    eva_db: AsyncSession = Depends(get_eva_db),
):
    """List all active runtime hosts with tenant counts."""
    # Subquery: count active allocations per host
    alloc_counts = (
        select(
            EvaOpenclawRuntimeAllocation.runtime_host_id,
            func.count().label("tenant_count"),
        )
        .where(EvaOpenclawRuntimeAllocation.state.in_(ACTIVE_ALLOCATION_STATES))
        .group_by(EvaOpenclawRuntimeAllocation.runtime_host_id)
        .subquery()
    )

    query = (
        select(EvaOpenclawRuntimeHost, func.coalesce(alloc_counts.c.tenant_count, 0).label("tenant_count"))
        .outerjoin(alloc_counts, EvaOpenclawRuntimeHost.id == alloc_counts.c.runtime_host_id)
        .where(EvaOpenclawRuntimeHost.state != "released")
        .order_by(EvaOpenclawRuntimeHost.created_at)
    )

    result = await eva_db.execute(query)
    hosts = []
    for row in result.all():
        host = row[0]
        tenant_count = row[1]
        hosts.append(
            RuntimeHostResponse(
                id=host.id,
                provider_host_id=host.provider_host_id,
                name=host.name,
                region=host.region,
                host_class=host.host_class,
                state=host.state,
                public_ip=host.public_ip,
                vcpu=host.vcpu,
                ram_mb=host.ram_mb,
                disk_gb=host.disk_gb,
                max_tenants=host.max_tenants,
                tenant_count=tenant_count,
                saturation=host.saturation,
                last_heartbeat_at=host.last_heartbeat_at,
                created_at=host.created_at,
            )
        )
    return hosts


@router.get("/hosts/{host_id}/employees", response_model=list[RuntimeEmployeeResponse])
async def list_host_employees(
    host_id: uuid.UUID,
    _user=Depends(get_current_user),
    eva_db: AsyncSession = Depends(get_eva_db),
):
    """List employees allocated to a specific host."""
    query = (
        select(EvaOpenclawAgent, EvaOpenclawRuntimeAllocation, EvaAccount.name.label("account_name"))
        .outerjoin(
            EvaOpenclawRuntimeAllocation,
            EvaOpenclawAgent.id == EvaOpenclawRuntimeAllocation.openclaw_agent_id,
        )
        .outerjoin(EvaAccount, EvaOpenclawAgent.account_id == EvaAccount.id)
        .where(
            EvaOpenclawRuntimeAllocation.runtime_host_id == host_id,
            EvaOpenclawRuntimeAllocation.state.in_(ACTIVE_ALLOCATION_STATES),
        )
        .order_by(EvaOpenclawAgent.label)
    )
    result = await eva_db.execute(query)
    employees = []
    for row in result.all():
        agent = row[0]
        alloc = row[1]
        account_name = row[2]
        employees.append(
            RuntimeEmployeeResponse(
                id=agent.id,
                agent_id=agent.agent_id,
                account_id=agent.account_id,
                account_name=account_name,
                label=agent.label,
                status=agent.status,
                phone_number=agent.phone_number,
                allocation_state=alloc.state if alloc else None,
                container_name=alloc.container_name if alloc else None,
                gateway_port=alloc.gateway_port if alloc else None,
                cpu_reservation_mcpu=alloc.cpu_reservation_mcpu if alloc else None,
                ram_reservation_mb=alloc.ram_reservation_mb if alloc else None,
                reconnect_risk=alloc.reconnect_risk if alloc else None,
                whatsapp_connected=agent.whatsapp_connected,
                telegram_connected=agent.telegram_connected,
                vps_ip=agent.vps_ip,
            )
        )
    return employees


@router.get("/employees/{openclaw_agent_id}", response_model=RuntimeEmployeeDetailResponse)
async def get_employee_detail(
    openclaw_agent_id: uuid.UUID,
    _user=Depends(get_current_user),
    eva_db: AsyncSession = Depends(get_eva_db),
):
    """Get full employee detail including allocation and recent events."""
    # Agent + allocation + host + account
    query = (
        select(
            EvaOpenclawAgent,
            EvaOpenclawRuntimeAllocation,
            EvaOpenclawRuntimeHost,
            EvaAccount.name.label("account_name"),
        )
        .outerjoin(
            EvaOpenclawRuntimeAllocation,
            (EvaOpenclawAgent.id == EvaOpenclawRuntimeAllocation.openclaw_agent_id)
            & EvaOpenclawRuntimeAllocation.state.in_(ACTIVE_ALLOCATION_STATES),
        )
        .outerjoin(
            EvaOpenclawRuntimeHost,
            EvaOpenclawRuntimeAllocation.runtime_host_id == EvaOpenclawRuntimeHost.id,
        )
        .outerjoin(EvaAccount, EvaOpenclawAgent.account_id == EvaAccount.id)
        .where(EvaOpenclawAgent.id == openclaw_agent_id)
    )
    result = await eva_db.execute(query)
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Employee not found")

    agent, alloc, host, account_name = row

    # Recent events
    events_query = (
        select(EvaOpenclawRuntimeEvent)
        .where(EvaOpenclawRuntimeEvent.openclaw_agent_id == openclaw_agent_id)
        .order_by(EvaOpenclawRuntimeEvent.created_at.desc())
        .limit(20)
    )
    events_result = await eva_db.execute(events_query)
    events = [
        RuntimeEventResponse(
            id=e.id,
            source=e.source,
            event_type=e.event_type,
            severity=e.severity,
            reason_code=e.reason_code,
            payload=e.payload or {},
            created_at=e.created_at,
        )
        for e in events_result.scalars().all()
    ]

    return RuntimeEmployeeDetailResponse(
        id=agent.id,
        agent_id=agent.agent_id,
        account_id=agent.account_id,
        account_name=account_name,
        label=agent.label,
        status=agent.status,
        status_detail=agent.status_detail,
        error=agent.error,
        phone_number=agent.phone_number,
        connections_state=agent.connections_state or {},
        whatsapp_connected=agent.whatsapp_connected,
        telegram_connected=agent.telegram_connected,
        provisioning_started_at=agent.provisioning_started_at,
        provisioning_completed_at=agent.provisioning_completed_at,
        allocation_state=alloc.state if alloc else None,
        container_name=alloc.container_name if alloc else None,
        gateway_port=alloc.gateway_port if alloc else None,
        host_name=host.name if host else None,
        host_ip=host.public_ip if host else None,
        cpu_reservation_mcpu=alloc.cpu_reservation_mcpu if alloc else None,
        ram_reservation_mb=alloc.ram_reservation_mb if alloc else None,
        reconnect_risk=alloc.reconnect_risk if alloc else None,
        queued_reason=alloc.queued_reason if alloc else None,
        placed_at=alloc.placed_at if alloc else None,
        started_at=alloc.started_at if alloc else None,
        recent_events=events,
    )


@router.get(
    "/hosts/{host_ip}/docker/status",
    response_model=list[DockerContainerResponse],
)
async def get_docker_status(
    host_ip: str,
    _user=Depends(get_current_user),
    eva_db: AsyncSession = Depends(get_eva_db),
):
    """Get Docker container status on a host via SSH."""
    await _validate_host_ip(host_ip, eva_db)
    try:
        containers = await infra_ssh.docker_status(host_ip)
        return [DockerContainerResponse(**c) for c in containers]
    except Exception as exc:
        logger.warning("SSH docker status failed for %s: %s", host_ip, exc)
        raise HTTPException(
            status_code=502, detail="Host unreachable"
        ) from exc


@router.get(
    "/hosts/{host_ip}/docker/logs/{container_name}",
    response_model=DockerLogsResponse,
)
async def get_docker_logs(
    host_ip: str,
    container_name: str,
    tail: int = Query(default=100, ge=1, le=500),
    _user=Depends(get_current_user),
    eva_db: AsyncSession = Depends(get_eva_db),
):
    """Get recent Docker logs from a container via SSH."""
    await _validate_host_ip(host_ip, eva_db)
    try:
        logs = await infra_ssh.docker_logs(host_ip, container_name, tail=tail)
        return DockerLogsResponse(
            container_name=container_name, lines=logs, tail=tail
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.warning("SSH docker logs failed for %s/%s: %s", host_ip, container_name, exc)
        raise HTTPException(
            status_code=502, detail="Host unreachable"
        ) from exc


@router.get("/hosts/{host_ip}/files", response_model=list[FileEntryResponse])
async def list_files(
    host_ip: str,
    path: str = Query(default="/root/.openclaw/"),
    _user=Depends(get_current_user),
    eva_db: AsyncSession = Depends(get_eva_db),
):
    """List directory contents on a host via SFTP."""
    await _validate_host_ip(host_ip, eva_db)
    try:
        entries = await infra_ssh.list_directory(host_ip, path)
        return [FileEntryResponse(**e) for e in entries]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.warning("SFTP list failed for %s:%s: %s", host_ip, path, exc)
        raise HTTPException(
            status_code=502, detail="Host unreachable"
        ) from exc


@router.get("/hosts/{host_ip}/files/content", response_model=FileContentResponse)
async def get_file_content(
    host_ip: str,
    path: str = Query(...),
    _user=Depends(get_current_user),
    eva_db: AsyncSession = Depends(get_eva_db),
):
    """Read file content on a host via SFTP."""
    await _validate_host_ip(host_ip, eva_db)
    try:
        result = await infra_ssh.read_file(host_ip, path)
        return FileContentResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.warning("SFTP read failed for %s:%s: %s", host_ip, path, exc)
        raise HTTPException(
            status_code=502, detail="Host unreachable"
        ) from exc
