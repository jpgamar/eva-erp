"""Constancia fiscal extraction using OpenAI vision + Supabase storage."""

from __future__ import annotations

import base64
import io
import json
import logging
import mimetypes
from typing import Any
from uuid import UUID

import httpx
from openai import AsyncOpenAI

from src.common.config import settings

logger = logging.getLogger(__name__)


# ── Supabase Storage helpers ─────────────────────────────────────────


def _supabase_headers() -> dict[str, str]:
    if not settings.supabase_service_role_key:
        raise RuntimeError("supabase_service_role_key not configured")
    return {
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "apikey": settings.supabase_service_role_key,
    }


async def upload_constancia(
    *, empresa_id: UUID | str, filename: str, file_bytes: bytes, content_type: str | None = None
) -> str:
    """Upload the constancia PDF/image to Supabase Storage and return the
    bucket-relative object key. Never returns the signed URL — callers mint
    one on read via ``signed_constancia_url``.
    """
    if not settings.supabase_url:
        raise RuntimeError("supabase_url not configured")
    resolved_type = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    # Suffix a random segment so we don't overwrite earlier uploads.
    from uuid import uuid4
    safe_name = filename.replace("/", "_").replace("..", "_")
    object_key = f"{empresa_id}/{uuid4().hex[:8]}_{safe_name}"
    url = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/{settings.supabase_bucket_constancias}/{object_key}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            url,
            headers={**_supabase_headers(), "Content-Type": resolved_type, "x-upsert": "true"},
            content=file_bytes,
        )
    if resp.status_code >= 300:
        raise RuntimeError(f"Supabase upload failed: {resp.status_code} {resp.text[:200]}")
    return object_key


async def signed_constancia_url(object_key: str, *, expires_in_seconds: int = 3600) -> str:
    """Mint a time-limited signed URL for reading an uploaded constancia."""
    if not object_key:
        raise ValueError("object_key required")
    url = (
        f"{settings.supabase_url.rstrip('/')}/storage/v1/object/sign/"
        f"{settings.supabase_bucket_constancias}/{object_key}"
    )
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            url,
            headers={**_supabase_headers(), "Content-Type": "application/json"},
            json={"expiresIn": expires_in_seconds},
        )
    if resp.status_code >= 300:
        raise RuntimeError(f"Supabase sign URL failed: {resp.status_code} {resp.text[:200]}")
    body = resp.json()
    signed_path = body.get("signedURL") or body.get("signed_url")
    if not signed_path:
        raise RuntimeError("Supabase sign URL returned no signed path")
    return f"{settings.supabase_url.rstrip('/')}{signed_path}"

EXTRACTION_MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = """You are a Mexican tax document data extractor.
Extract the following fields from the constancia de situacion fiscal (Mexican tax certificate):

- rfc: The RFC (Registro Federal de Contribuyentes) — 12 or 13 alphanumeric characters
- legal_name: The full legal name (Razon Social for persona moral, or full name for persona fisica)
- tax_regime: The 3-digit tax regime code (e.g., "601", "612", "625") from the Regímenes section
- postal_code: The 5-digit fiscal postal code (Código Postal del domicilio fiscal)
- person_type: Either "persona_fisica" or "persona_moral"

Return ONLY valid JSON. If you cannot extract a field, set it to null."""

EXTRACTION_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "constancia_extraction",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "rfc": {"type": ["string", "null"]},
                "legal_name": {"type": ["string", "null"]},
                "tax_regime": {"type": ["string", "null"]},
                "postal_code": {"type": ["string", "null"]},
                "person_type": {"type": ["string", "null"], "enum": ["persona_fisica", "persona_moral", None]},
            },
            "required": ["rfc", "legal_name", "tax_regime", "postal_code", "person_type"],
            "additionalProperties": False,
        },
    },
}


async def extract_from_file(file_bytes: bytes, content_type: str) -> dict[str, Any]:
    """Extract fiscal data from a constancia PDF or image using OpenAI vision."""
    api_key = (settings.openai_api_key or "").strip()
    if not api_key:
        return {"extracted": {}, "warnings": ["OpenAI API key not configured"], "source": "error"}

    images = _prepare_images(file_bytes, content_type)
    if not images:
        return {"extracted": {}, "warnings": ["Could not process the uploaded file"], "source": "error"}

    client = AsyncOpenAI(api_key=api_key)

    content: list[dict] = [{"type": "text", "text": "Extract the fiscal data from this constancia de situacion fiscal."}]
    for img_b64, mime in images:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{img_b64}", "detail": "high"},
        })

    try:
        response = await client.chat.completions.create(
            model=EXTRACTION_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            response_format=EXTRACTION_SCHEMA,
            max_tokens=500,
            temperature=0,
        )
        raw = response.choices[0].message.content
        data = json.loads(raw)
        warnings = _validate_extracted(data)
        return {"extracted": data, "warnings": warnings, "source": "llm_vision"}
    except Exception as exc:
        logger.exception("Constancia extraction failed: %s", exc)
        return {"extracted": {}, "warnings": [f"Extraction failed: {str(exc)[:200]}"], "source": "error"}


def _prepare_images(file_bytes: bytes, content_type: str) -> list[tuple[str, str]]:
    """Convert file to list of (base64_data, mime_type) tuples."""
    if content_type == "application/pdf":
        return _pdf_to_images(file_bytes)
    if content_type.startswith("image/"):
        b64 = base64.b64encode(file_bytes).decode("ascii")
        return [(b64, content_type)]
    return []


def _pdf_to_images(pdf_bytes: bytes, max_pages: int = 3, dpi: int = 150) -> list[tuple[str, str]]:
    """Render PDF pages as JPEG images."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.warning("PyMuPDF not installed — cannot convert PDF to images")
        return []

    images = []
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            zoom = dpi / 72
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("jpeg")
            b64 = base64.b64encode(img_bytes).decode("ascii")
            images.append((b64, "image/jpeg"))
        doc.close()
    except Exception as exc:
        logger.warning("PDF to image conversion failed: %s", exc)
    return images


def _validate_extracted(data: dict) -> list[str]:
    """Return warnings for missing or suspicious fields."""
    warnings = []
    if not data.get("rfc"):
        warnings.append("No se pudo extraer el RFC")
    elif len(data["rfc"]) < 12:
        warnings.append(f"RFC parece incompleto: {data['rfc']}")
    if not data.get("legal_name"):
        warnings.append("No se pudo extraer la razon social")
    if not data.get("tax_regime"):
        warnings.append("No se pudo extraer el regimen fiscal")
    elif len(data["tax_regime"]) != 3:
        warnings.append(f"Regimen fiscal deberia ser de 3 digitos: {data['tax_regime']}")
    if not data.get("postal_code"):
        warnings.append("No se pudo extraer el codigo postal fiscal")
    elif len(data["postal_code"]) != 5:
        warnings.append(f"Codigo postal deberia ser de 5 digitos: {data['postal_code']}")
    return warnings
