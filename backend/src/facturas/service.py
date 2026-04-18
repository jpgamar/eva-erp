from decimal import Decimal, ROUND_HALF_UP

import httpx
from fastapi import HTTPException

from src.common.config import settings
from src.facturas.schemas import FacturaCreate

FACTURAPI_BASE = "https://www.facturapi.io/v2"


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.facturapi_api_key}",
        "Content-Type": "application/json",
    }


def build_facturapi_payload(
    data: FacturaCreate,
    *,
    idempotency_key: str | None = None,
) -> dict:
    """Transform our schema into Facturapi's expected payload.

    Federal retentions (ISR/IVA) ride on ``product.taxes``; state-level
    cedular (e.g., Guanajuato Art. 37-D LHEG 2%) rides on
    ``product.local_taxes`` — the SAT "Impuestos Locales 1.0" complement.

    ``idempotency_key`` (if provided) is sent as a top-level body field
    per Facturapi's async-safe retry protocol. Required by the outbox
    worker so a retry after a "stamped but not committed" crash returns
    the same CFDI instead of creating a duplicate.
    """
    items = []
    for li in data.line_items:
        taxes = [{"type": "IVA", "rate": float(li.tax_rate)}]
        if li.isr_retention:
            taxes.append({"type": "ISR", "rate": float(li.isr_retention), "withholding": True})
        if li.iva_retention:
            taxes.append({"type": "IVA", "rate": float(li.iva_retention), "withholding": True})

        product: dict = {
            "description": li.description,
            "product_key": li.product_key,
            "price": float(li.unit_price),
            "tax_included": False,
            "taxes": taxes,
        }

        if li.cedular_rate:
            # Facturapi accepts ``type`` as a free-form label that SAT will
            # render in ``implocal:ImpLocRetenido`` on the CFDI. Use the
            # human-readable cedular label when provided so the PDF line
            # reads e.g. "Cedular GTO 2.00%".
            product["local_taxes"] = [
                {
                    "type": li.cedular_label or "Cedular",
                    "rate": float(li.cedular_rate),
                    "withholding": True,
                }
            ]

        items.append({"product": product, "quantity": li.quantity})

    payload: dict = {
        "customer": {
            "legal_name": data.customer_name,
            "tax_id": data.customer_rfc,
            "tax_system": data.customer_tax_system,
            "address": {"zip": data.customer_zip},
        },
        "items": items,
        "use": data.use,
        "payment_form": data.payment_form,
        "payment_method": data.payment_method,
    }
    if idempotency_key:
        payload["idempotency_key"] = idempotency_key
    # Note: Facturapi no longer accepts the "comments" field.
    # data.notes is internal metadata (e.g. "Eva billing source=subscription_invoice")
    # and is not needed on the CFDI itself.
    return payload


def _check_key():
    if not settings.facturapi_api_key:
        raise HTTPException(
            status_code=503,
            detail="Facturapi API key not configured. Add FACTURAPI_API_KEY to .env",
        )


async def create_invoice(payload: dict) -> dict:
    """POST /v2/invoices — create and stamp a CFDI."""
    _check_key()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{FACTURAPI_BASE}/invoices",
            json=payload,
            headers=_headers(),
        )
        if resp.status_code >= 400:
            detail = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
            raise HTTPException(status_code=502, detail={"facturapi_error": detail})
        return resp.json()


async def create_draft_invoice(payload: dict) -> dict:
    """POST /v2/invoices with status:"draft" — create a preview invoice without SAT stamping."""
    _check_key()
    draft_payload = {**payload, "status": "draft"}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{FACTURAPI_BASE}/invoices",
            json=draft_payload,
            headers=_headers(),
        )
        if resp.status_code >= 400:
            detail = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
            raise HTTPException(status_code=502, detail={"facturapi_error": detail})
        return resp.json()


async def stamp_draft_invoice(facturapi_id: str) -> dict:
    """POST /v2/invoices/{id}/stamp — promote a draft to a valid stamped CFDI."""
    _check_key()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{FACTURAPI_BASE}/invoices/{facturapi_id}/stamp",
            headers=_headers(),
        )
        if resp.status_code >= 400:
            detail = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
            status = 400 if resp.status_code == 400 else 502
            raise HTTPException(status_code=status, detail={"facturapi_error": detail})
        return resp.json()


async def delete_draft_invoice(facturapi_id: str) -> None:
    """DELETE /v2/invoices/{id} — remove a draft from Facturapi (no motive for drafts)."""
    _check_key()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.delete(
            f"{FACTURAPI_BASE}/invoices/{facturapi_id}",
            headers=_headers(),
        )
        if resp.status_code >= 400 and resp.status_code != 404:
            detail = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
            raise HTTPException(status_code=502, detail={"facturapi_error": detail})


async def create_egreso_invoice(payload: dict) -> dict:
    """POST /v2/invoices — create and stamp an egreso CFDI."""
    _check_key()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{FACTURAPI_BASE}/invoices",
            json=payload,
            headers=_headers(),
        )
        if resp.status_code >= 400:
            detail = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
            raise HTTPException(status_code=502, detail={"facturapi_error": detail})
        return resp.json()


async def cancel_invoice(facturapi_id: str, motive: str = "02") -> dict:
    """DELETE /v2/invoices/{id} — cancel a stamped CFDI."""
    _check_key()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.delete(
            f"{FACTURAPI_BASE}/invoices/{facturapi_id}",
            params={"motive": motive},
            headers=_headers(),
        )
        if resp.status_code >= 400:
            detail = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
            raise HTTPException(status_code=502, detail={"facturapi_error": detail})
        return resp.json()


async def download_pdf(facturapi_id: str) -> bytes:
    """GET /v2/invoices/{id}/pdf — download CFDI PDF."""
    _check_key()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{FACTURAPI_BASE}/invoices/{facturapi_id}/pdf",
            headers=_headers(),
        )
        if resp.status_code >= 400:
            raise HTTPException(status_code=502, detail="Failed to download PDF from Facturapi")
        return resp.content


def build_payment_complement_payload(
    *,
    factura: "Factura",  # noqa: F821 - forward ref; imported only for typing
    payment,
    idempotency_key: str | None = None,
) -> dict:
    """Build the FacturAPI body for a CFDI tipo P.

    Spec reference: https://docs.facturapi.io/en/docs/guides/invoices/pago/

    Structure
    ---------
    ``type: "P"`` + customer block + ``complements[{type:"pago", data:[...]}]``.
    The data entry references the original PPD CFDI by UUID and declares
    the amount paid, installment number, running balance, and the tax
    breakdown so SAT can recompute the tax acreditable for that payment.

    Tax rebuild
    -----------
    SAT needs the base + rate for each tax on the portion paid. For PUE
    invoices this isn't required, but for P we have to decompose the
    payment into (subtotal × taxes) proportional to the original CFDI.
    We compute: ``base = payment_amount / (1 + tax_rate)``.

    Only IVA 16% handled here explicitly; other rates (0%, 8% frontera)
    fall through with their stored rate. Retentions (ISR/IVA/cedular)
    are NOT re-declared on the complement — they applied once at
    stamping of the original PPD invoice.
    """
    tax_rate = Decimal("0.16")
    # Try to infer tax_rate from the original line_items (they're all the
    # same in practice for our SaaS billing).
    items = factura.line_items_json or []
    if items:
        tr = items[0].get("tax_rate")
        if tr is not None:
            tax_rate = Decimal(str(tr))
    base_amount = (Decimal(str(payment.payment_amount)) / (Decimal("1") + tax_rate)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    related_doc: dict = {
        "uuid": factura.cfdi_uuid,
        "amount": float(payment.payment_amount),
        "installment": int(payment.installment),
        "taxes": [
            {
                "base": float(base_amount),
                "type": "IVA",
                "rate": float(tax_rate),
            }
        ],
    }
    if payment.last_balance is not None:
        related_doc["last_balance"] = float(payment.last_balance)

    complement: dict = {
        "type": "pago",
        "data": [
            {
                "payment_form": payment.payment_form,
                "related_documents": [related_doc],
            }
        ],
    }

    payload: dict = {
        "type": "P",
        "customer": {
            "legal_name": factura.customer_name,
            "tax_id": factura.customer_rfc,
            "tax_system": factura.customer_tax_system,
            "address": {"zip": factura.customer_zip},
        },
        "complements": [complement],
    }
    if idempotency_key:
        payload["idempotency_key"] = idempotency_key
    return payload


async def download_xml(facturapi_id: str) -> bytes:
    """GET /v2/invoices/{id}/xml — download CFDI XML."""
    _check_key()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{FACTURAPI_BASE}/invoices/{facturapi_id}/xml",
            headers=_headers(),
        )
        if resp.status_code >= 400:
            raise HTTPException(status_code=502, detail="Failed to download XML from Facturapi")
        return resp.content
