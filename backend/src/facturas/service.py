import httpx
from fastapi import HTTPException

from src.common.config import settings

FACTURAPI_BASE = "https://www.facturapi.io/v2"


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.facturapi_api_key}",
        "Content-Type": "application/json",
    }


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
