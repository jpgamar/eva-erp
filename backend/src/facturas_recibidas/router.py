"""HTTP endpoints for gastos / facturas recibidas."""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.common.database import get_db
from src.eva_billing.service import PROVIDER_REGIME  # noqa: F401 - kept for docs
from src.facturas_recibidas.models import FacturaRecibida
from src.facturas_recibidas.schemas import (
    FacturaRecibidaResponse,
    FacturaRecibidaUpdate,
    GastosUploadResult,
    IvaAcreditableSummary,
)
from src.facturas_recibidas.service import (
    UploadRejected,
    get_iva_acreditable,
    ingest_cfdi_xml,
    list_gastos,
)

router = APIRouter(prefix="/gastos", tags=["gastos"])


# NOTE: today the ERP operates as a single taxpayer (Gustavo, ZEPG070314VC1).
# When multi-tenancy arrives, this constant moves to the empresa record
# and each upload validates against the operator's empresa.rfc.
_OPERATOR_RFC = "ZEPG070314VC1"


@router.post("/upload", response_model=GastosUploadResult)
async def upload_gastos(
    files: list[UploadFile] = File(..., description="CFDI XML files"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Upload one or more CFDI XMLs.

    Each file is parsed, validated (receiver RFC = operator RFC), and
    stored. Duplicates (by SAT UUID) are counted but not reinserted.
    Rejected files (bad XML or wrong receiver) are reported in the
    response but do not abort the whole batch.
    """
    imported = 0
    duplicates = 0
    rejected = 0
    errors: list[str] = []

    for upload in files:
        try:
            content = await upload.read()
            _row, was_new = await ingest_cfdi_xml(
                db=db,
                xml_content=content,
                expected_receiver_rfc=_OPERATOR_RFC,
                user_id=user.id,
            )
            if was_new:
                imported += 1
            else:
                duplicates += 1
        except UploadRejected as exc:
            rejected += 1
            errors.append(f"{upload.filename}: {str(exc)[:200]}")

    return GastosUploadResult(
        imported=imported,
        duplicates=duplicates,
        rejected=rejected,
        errors=errors,
    )


@router.get("", response_model=list[FacturaRecibidaResponse])
async def list_gastos_endpoint(
    year: int | None = None,
    month: int | None = None,
    category: str | None = None,
    acreditable_only: bool = False,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List received CFDIs with filters.

    Default filter: none (returns everything). Most-common use is the
    declaración page, which calls with ``year`` and ``month`` to show
    the gastos that feed that period's IVA acreditable.
    """
    return await list_gastos(
        db=db,
        year=year,
        month=month,
        category=category,
        acreditable_only=acreditable_only,
    )


@router.get("/iva-acreditable", response_model=IvaAcreditableSummary)
async def iva_acreditable_endpoint(
    year: int,
    month: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Total IVA acreditable for a calendar month.

    Called from the declaración page to show the "copy to SAT"
    preview. Also used to verify parity between the ERP's math and
    SAT's visor when debugging.
    """
    total, rows = await get_iva_acreditable(db, year=year, month=month)
    return IvaAcreditableSummary(
        year=year, month=month, iva_acreditable=total, row_count=rows
    )


@router.patch("/{row_id}", response_model=FacturaRecibidaResponse)
async def update_gasto(
    row_id: uuid.UUID,
    data: FacturaRecibidaUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update operator-editable fields (category, notes, is_acreditable,
    payment_date for PPD). The CFDI data itself is immutable — SAT is
    the source of truth."""
    row = await db.get(FacturaRecibida, row_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Gasto not found")
    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(row, key, value)
    db.add(row)
    await db.flush()
    await db.refresh(row)
    return row
