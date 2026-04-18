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
    # Only emit `currency` when the caller picked a non-MXN invoice. SAT
    # defaults to MXN at exchange 1.0, so adding it for every MXN CFDI
    # would add noise without value. A USD/EUR invoice without this
    # field would stamp as if MXN — broken conversion everywhere.
    # (Codex round-5 P2, 2026-04-18.)
    invoice_currency = (data.currency or "MXN").upper()
    if invoice_currency != "MXN":
        payload["currency"] = invoice_currency
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
    SAT needs base + rate for each tax on the portion paid. The naive
    formula ``base = payment_amount / (1 + tax_rate)`` only holds when
    the invoice had no retentions — i.e. when cash received equals
    subtotal + IVA. For invoices that include ISR + IVA retentions
    (persona-moral clients like F-4), cash received is
    ``subtotal + IVA - ISR_ret - IVA_ret`` and the naive formula
    under-reports the base to SAT (e.g. F-4's $4,162.29 would become
    base=3588.18 instead of 3999.00). Either of those wrongly under-
    reports the IVA the client is entitled to acreditar.

    Correct approach: prorate the original ``subtotal`` / IVA / retention
    amounts by ``payment_amount / factura.total``. For a full payment
    this returns the untouched originals; for a partial it splits each
    tax line proportionally. This preserves the fiscal equivalence that
    base + IVA − retentions = payment_amount.
    """
    factura_total = Decimal(str(factura.total or 0))
    if factura_total <= 0:
        # Defensive — a valid factura always has total > 0. Fall back to
        # the naive calc so we at least emit *something* rather than crash.
        factura_total = Decimal(str(payment.payment_amount))
    proportion = (Decimal(str(payment.payment_amount)) / factura_total).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )

    factura_subtotal = Decimal(str(factura.subtotal or 0))
    factura_iva = Decimal(str(factura.tax or 0))
    factura_isr_ret = Decimal(str(factura.isr_retention or 0))
    factura_iva_ret = Decimal(str(factura.iva_retention or 0))
    factura_local_ret = Decimal(str(factura.local_retention or 0))

    base_amount = (factura_subtotal * proportion).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    iva_amount = (factura_iva * proportion).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    isr_retained = (factura_isr_ret * proportion).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    iva_retained = (factura_iva_ret * proportion).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    local_retained = (factura_local_ret * proportion).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    # Infer the effective IVA rate from the original invoice. For
    # 0%-rated or exento items we'd want a different rate; detect from
    # the ratio (handles the common 16% / 8% frontera / 0% cases).
    tax_rate = Decimal("0.16")
    if factura_subtotal > 0:
        computed = (factura_iva / factura_subtotal).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )
        # Snap to the nearest SAT rate to avoid float noise breaking the
        # CFDI validation (SAT rounds to 6 decimals: 0.160000, 0.080000).
        if abs(computed - Decimal("0.16")) < Decimal("0.005"):
            tax_rate = Decimal("0.16")
        elif abs(computed - Decimal("0.08")) < Decimal("0.005"):
            tax_rate = Decimal("0.08")
        elif computed == Decimal("0"):
            tax_rate = Decimal("0")
        else:
            tax_rate = computed

    taxes_block: list[dict] = [
        {"base": float(base_amount), "type": "IVA", "rate": float(tax_rate)},
    ]
    if isr_retained > 0:
        taxes_block.append({
            "base": float(base_amount),
            "type": "ISR",
            "rate": float((factura_isr_ret / factura_subtotal).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)) if factura_subtotal > 0 else 0.0,
            "withholding": True,
        })
    if iva_retained > 0:
        taxes_block.append({
            "base": float(base_amount),
            "type": "IVA",
            "rate": float((factura_iva_ret / factura_subtotal).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)) if factura_subtotal > 0 else 0.0,
            "withholding": True,
        })
    # State-level cedular (e.g., GTO 2% under Art. 37-D LHEG). If the
    # original PPD invoice carried a cedular, the complement must carry
    # it too in ``local_taxes`` — otherwise SAT sees a short tax profile
    # and the client's IVA acreditable disagrees with our record.
    # (Codex round-2 P2, 2026-04-18.)
    local_taxes_block: list[dict] = []
    if local_retained > 0 and factura_subtotal > 0:
        local_taxes_block.append({
            "base": float(base_amount),
            "type": factura.local_retention_state or "Cedular",
            "rate": float(
                (factura_local_ret / factura_subtotal).quantize(
                    Decimal("0.000001"), rounding=ROUND_HALF_UP
                )
            ),
            "withholding": True,
        })

    related_doc: dict = {
        "uuid": factura.cfdi_uuid,
        "amount": float(payment.payment_amount),
        "installment": int(payment.installment),
        "taxes": taxes_block,
    }
    if local_taxes_block:
        related_doc["local_taxes"] = local_taxes_block
    if payment.last_balance is not None:
        related_doc["last_balance"] = float(payment.last_balance)

    # SAT Anexo 20 Pago 2.0: if the payment currency differs from the
    # original invoice's (or from MXN in general), the complement must
    # carry `currency` + `exchange_rate` on the data block, otherwise
    # SAT's implicit default of MXN at exchange 1 produces a wrong
    # conversion on the client's acreditable IVA. Only emit when the
    # operator explicitly captured a non-MXN currency, so the default
    # MXN path (today's 100% of invoices) stays unchanged.
    # (Codex round-4 P2, 2026-04-18.)
    pago_data: dict = {
        "payment_form": payment.payment_form,
        "related_documents": [related_doc],
    }
    payment_currency = (payment.currency or "MXN").upper()
    if payment_currency != "MXN":
        pago_data["currency"] = payment_currency
        if payment.exchange_rate is not None:
            pago_data["exchange"] = float(payment.exchange_rate)

    complement: dict = {
        "type": "pago",
        "data": [pago_data],
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
