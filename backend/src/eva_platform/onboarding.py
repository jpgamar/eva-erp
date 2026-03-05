"""Owner onboarding helpers for account provisioning flows."""

from __future__ import annotations

import asyncio
import logging
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

from src.common.config import settings
from src.eva_platform.schemas import AccountOnboardingResponse
from src.eva_platform.supabase_client import (
    SupabaseAdminClient,
    SupabaseAdminError,
    SupabaseGenerateLinkResult,
)

logger = logging.getLogger(__name__)

DEFAULT_ONBOARDING_REDIRECT_URL = "https://app.goeva.ai/auth/change-password"
SENDGRID_MAX_ATTEMPTS = 3
SENDGRID_RETRYABLE_STATUSES = {408, 409, 425, 429, 500, 502, 503, 504}


def _resolve_onboarding_redirect_url(raw_redirect_url: str | None) -> str:
    configured = (raw_redirect_url or "").strip()
    if not configured:
        return DEFAULT_ONBOARDING_REDIRECT_URL

    parsed = urlparse(configured)
    path = (parsed.path or "").rstrip("/") or "/"
    if path in {"/login", "/auth/login"}:
        normalized = parsed._replace(path="/auth/change-password", query="", params="", fragment="")
        resolved = urlunparse(normalized)
        logger.warning(
            "Normalizing onboarding redirect from login path to change-password: %s -> %s",
            configured,
            resolved,
        )
        return resolved

    return configured


def _build_direct_recovery_link(*, redirect_to: str, token_hash: str) -> str:
    return _build_direct_otp_link(
        redirect_to=redirect_to,
        otp_type="recovery",
        token_hash=token_hash,
    )


def _build_direct_otp_link(
    *,
    redirect_to: str,
    otp_type: str,
    token_hash: str | None = None,
    token: str | None = None,
) -> str:
    parsed = urlparse(redirect_to)
    params = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key not in {"token_hash", "token", "otp_token", "type", "otp_type"}
    ]
    if token_hash:
        params.append(("token_hash", token_hash))
    elif token:
        params.append(("token", token))
    params.append(("type", otp_type))
    return urlunparse(parsed._replace(query=urlencode(params, doseq=True), fragment=""))


def _resolve_onboarding_link(
    *,
    redirect_to: str,
    generated: SupabaseGenerateLinkResult,
) -> str:
    action_link = (generated.get("action_link") or "").strip()
    hashed_token = (generated.get("hashed_token") or "").strip()
    if hashed_token:
        return _build_direct_recovery_link(redirect_to=redirect_to, token_hash=hashed_token)
    if action_link:
        parsed_action = urlparse(action_link)
        action_params = dict(parse_qsl(parsed_action.query, keep_blank_values=True))
        action_token_hash = (
            (action_params.get("token_hash") or "").strip()
            or (action_params.get("hashed_token") or "").strip()
        )
        action_token = (
            (action_params.get("token") or "").strip()
            or (action_params.get("otp_token") or "").strip()
        )
        action_type = (
            (action_params.get("type") or action_params.get("otp_type") or "recovery")
            .strip()
            .lower()
            or "recovery"
        )
        action_redirect = _resolve_onboarding_redirect_url(action_params.get("redirect_to") or redirect_to)
        if action_token_hash:
            return _build_direct_otp_link(
                redirect_to=action_redirect,
                otp_type=action_type,
                token_hash=action_token_hash,
            )
        if action_token:
            return _build_direct_otp_link(
                redirect_to=action_redirect,
                otp_type=action_type,
                token=action_token,
            )
    return action_link


async def build_account_onboarding(
    *,
    owner_email: str,
    owner_name: str,
    product_label: str,
    send_setup_email: bool,
) -> AccountOnboardingResponse:
    """Generate setup link and attempt email delivery.

    Setup link generation is required for a successful response. Email delivery
    is best-effort and falls back to manual sharing.
    """
    redirect_to = _resolve_onboarding_redirect_url(settings.eva_app_onboarding_redirect_url)
    try:
        generated_link = await SupabaseAdminClient.admin_generate_link_details(
            email=owner_email,
            link_type="recovery",
            redirect_to=redirect_to,
        )
        onboarding_link = _resolve_onboarding_link(
            redirect_to=redirect_to,
            generated=generated_link,
        )
    except SupabaseAdminError as exc:
        raise exc

    if not onboarding_link:
        raise SupabaseAdminError("Failed to generate setup link")

    if not send_setup_email:
        return AccountOnboardingResponse(
            owner_email=owner_email,
            onboarding_link=onboarding_link,
            email_status="skipped",
            email_message="Setup email skipped by operator. Share the link manually.",
        )

    sent, message = await _send_setup_email(
        owner_email=owner_email,
        owner_name=owner_name,
        product_label=product_label,
        onboarding_link=onboarding_link,
    )

    return AccountOnboardingResponse(
        owner_email=owner_email,
        onboarding_link=onboarding_link,
        email_status="sent" if sent else "failed",
        email_message=message,
    )


async def _send_setup_email(
    *,
    owner_email: str,
    owner_name: str,
    product_label: str,
    onboarding_link: str,
) -> tuple[bool, str]:
    async def _send_via_supabase_fallback(reason: str) -> tuple[bool, str]:
        redirect_to = _resolve_onboarding_redirect_url(settings.eva_app_onboarding_redirect_url)
        try:
            await SupabaseAdminClient.send_recovery_email(owner_email, redirect_to=redirect_to)
            logger.info(
                "Setup email fallback sent via Supabase for %s (reason=%s)",
                owner_email,
                reason,
            )
            return True, "Setup email sent successfully via fallback provider."
        except SupabaseAdminError as exc:
            logger.warning(
                "Supabase fallback email failed for %s after reason=%s: %s",
                owner_email,
                reason,
                exc,
            )
            return False, "Failed to send setup email. Share the setup link manually."

    api_key = (settings.sendgrid_api_key or "").strip()
    if not api_key:
        return await _send_via_supabase_fallback("sendgrid_not_configured")

    display_name = owner_name.strip() or "there"

    payload = {
        "personalizations": [
            {
                "to": [{"email": owner_email}],
                "subject": f"Configura tu contrasena para {product_label}",
            }
        ],
        "from": {
            "email": settings.sendgrid_from_email,
            "name": settings.sendgrid_from_name,
        },
        "reply_to": {"email": settings.sendgrid_reply_to},
        "tracking_settings": {
            "click_tracking": {"enable": False, "enable_text": False},
            "open_tracking": {"enable": False},
            "subscription_tracking": {"enable": False},
        },
        "content": [
            {
                "type": "text/plain",
                "value": (
                    f"Hola {display_name},\n\n"
                    f"Tu cuenta de {product_label} esta lista.\n"
                    "Configura tu contrasena aqui:\n"
                    f"{onboarding_link}"
                ),
            },
            {
                "type": "text/html",
                "value": (
                    "<div style=\"margin:0;padding:24px 0;background:#f8fafc;font-family:'Segoe UI',Arial,sans-serif;\">"
                    "<table role=\"presentation\" cellpadding=\"0\" cellspacing=\"0\" border=\"0\" width=\"100%\">"
                    "<tr><td align=\"center\" style=\"padding:0 16px;\">"
                    "<table role=\"presentation\" cellpadding=\"0\" cellspacing=\"0\" border=\"0\" width=\"520\" "
                    "style=\"max-width:520px;background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;\">"
                    "<tr><td style=\"padding:20px 28px 6px 28px;text-align:center;\">"
                    "<table role=\"presentation\" cellpadding=\"0\" cellspacing=\"0\" border=\"0\" style=\"margin:0 auto 8px auto;\">"
                    "<tr style=\"height:34px;\">"
                    "<td style=\"width:6px;vertical-align:bottom;\"><div style=\"width:6px;height:14px;border-radius:3px;background:#60A5FA;\"></div></td>"
                    "<td style=\"width:5px;\"></td>"
                    "<td style=\"width:6px;vertical-align:bottom;\"><div style=\"width:6px;height:24px;border-radius:3px;background:#3B82F6;\"></div></td>"
                    "<td style=\"width:5px;\"></td>"
                    "<td style=\"width:6px;vertical-align:bottom;\"><div style=\"width:6px;height:34px;border-radius:3px;background:#2563EB;\"></div></td>"
                    "<td style=\"width:5px;\"></td>"
                    "<td style=\"width:6px;vertical-align:bottom;\"><div style=\"width:6px;height:24px;border-radius:3px;background:#3B82F6;\"></div></td>"
                    "<td style=\"width:5px;\"></td>"
                    "<td style=\"width:6px;vertical-align:bottom;\"><div style=\"width:6px;height:14px;border-radius:3px;background:#60A5FA;\"></div></td>"
                    "</tr>"
                    "</table>"
                    "<div style=\"font-size:22px;line-height:1.2;color:#0B1220;font-weight:700;letter-spacing:-0.4px;margin:0 0 8px 0;\">EvaAI</div>"
                    f"<div style=\"font-size:30px;line-height:1.2;color:#0f172a;font-weight:700;\">Hola {display_name}</div>"
                    "</td></tr>"
                    "<tr><td style=\"padding:2px 28px 8px 28px;\">"
                    f"<p style=\"margin:0 0 12px 0;color:#334155;font-size:17px;line-height:1.55;\">"
                    f"Tu cuenta de <strong>{product_label}</strong> esta lista.</p>"
                    "</td></tr>"
                    "<tr><td style=\"padding:10px 28px 8px 28px;text-align:center;\">"
                    f"<a href=\"{onboarding_link}\" "
                    "style=\"display:inline-block;background:#2563eb;color:#ffffff;text-decoration:none;"
                    "font-weight:700;font-size:15px;line-height:1;padding:13px 22px;border-radius:10px;border:1px solid #1d4ed8;\">Configurar contrasena</a>"
                    "</td></tr>"
                    "<tr><td style=\"padding:4px 28px 22px 28px;\">"
                    "<p style=\"margin:0;color:#64748b;font-size:13px;line-height:1.6;text-align:center;\">"
                    "Si no solicitaste este acceso, ignora este correo.</p>"
                    "</td></tr>"
                    "</table>"
                    "</td></tr></table></div>"
                ),
            },
        ],
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    response: httpx.Response | None = None
    for attempt in range(1, SENDGRID_MAX_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    headers=headers,
                    json=payload,
                )
        except Exception as exc:
            logger.warning(
                "Failed to send onboarding email to %s (attempt %s/%s): %s",
                owner_email,
                attempt,
                SENDGRID_MAX_ATTEMPTS,
                exc,
                exc_info=True,
            )
            if attempt < SENDGRID_MAX_ATTEMPTS:
                await asyncio.sleep(0.6 * attempt)
                continue
            return await _send_via_supabase_fallback("sendgrid_exception")

        if 200 <= response.status_code < 300:
            return True, "Setup email sent successfully."

        should_retry = response.status_code in SENDGRID_RETRYABLE_STATUSES
        logger.warning(
            "Setup email provider rejected request for %s: status=%s attempt=%s/%s body=%s",
            owner_email,
            response.status_code,
            attempt,
            SENDGRID_MAX_ATTEMPTS,
            response.text[:300],
        )
        if should_retry and attempt < SENDGRID_MAX_ATTEMPTS:
            await asyncio.sleep(0.6 * attempt)
            continue
        break

    status = response.status_code if response is not None else "unknown"
    sent_fallback, fallback_message = await _send_via_supabase_fallback(f"sendgrid_status_{status}")
    if sent_fallback:
        return True, f"{fallback_message} (SendGrid status: {status})"
    return False, f"Email provider returned {status}. Share the setup link manually."
