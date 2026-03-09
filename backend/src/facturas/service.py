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


def build_facturapi_payload(data: FacturaCreate) -> dict:
    """Transform our schema into Facturapi's expected payload."""
    items = []
    for li in data.line_items:
        taxes = [{"type": "IVA", "rate": float(li.tax_rate)}]
        if li.isr_retention:
            taxes.append({"type": "ISR", "rate": float(li.isr_retention), "withholding": True})
        if li.iva_retention:
            taxes.append({"type": "IVA", "rate": float(li.iva_retention), "withholding": True})
        items.append(
            {
                "product": {
                    "description": li.description,
                    "product_key": li.product_key,
                    "price": float(li.unit_price),
                    "tax_included": False,
                    "taxes": taxes,
                },
                "quantity": li.quantity,
            }
        )

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
    if data.notes:
        payload["comments"] = data.notes
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
