"""Owner onboarding helpers for account provisioning flows."""

from __future__ import annotations

import logging

import httpx

from src.common.config import settings
from src.eva_platform.schemas import AccountOnboardingResponse
from src.eva_platform.supabase_client import SupabaseAdminClient, SupabaseAdminError

logger = logging.getLogger(__name__)


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
    try:
        onboarding_link = await SupabaseAdminClient.admin_generate_link(
            email=owner_email,
            link_type="recovery",
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
        try:
            await SupabaseAdminClient.send_recovery_email(owner_email)
            logger.info("Setup email fallback sent via Supabase Auth for %s (%s)", owner_email, reason)
            return True, "Setup email sent via Supabase fallback."
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
                "subject": f"Configura tu acceso a {product_label}",
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
                    "Completa tu configuracion con este enlace:\n"
                    f"{onboarding_link}"
                ),
            },
            {
                "type": "text/html",
                "value": (
                    "<div style=\"margin:0;padding:24px 0;background:#ffffff;font-family:'Segoe UI',Arial,sans-serif;\">"
                    "<table role=\"presentation\" cellpadding=\"0\" cellspacing=\"0\" border=\"0\" width=\"100%\">"
                    "<tr><td align=\"center\" style=\"padding:0 16px;\">"
                    "<table role=\"presentation\" cellpadding=\"0\" cellspacing=\"0\" border=\"0\" width=\"560\" "
                    "style=\"max-width:560px;background:#ffffff;border:1px solid #e2e8f0;border-radius:14px;\">"
                    "<tr><td style=\"padding:24px 28px 8px 28px;text-align:center;\">"
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
                    "<div style=\"font-size:26px;line-height:1.1;color:#0B1220;font-weight:700;letter-spacing:-0.6px;margin:0 0 10px 0;\">EvaAI</div>"
                    f"<div style=\"font-size:34px;line-height:1.2;color:#0f172a;font-weight:700;\">Hola {display_name}</div>"
                    "</td></tr>"
                    "<tr><td style=\"padding:0 28px 8px 28px;\">"
                    f"<p style=\"margin:0 0 12px 0;color:#334155;font-size:17px;line-height:1.55;\">"
                    f"Tu cuenta de <strong>{product_label}</strong> esta lista.</p>"
                    "</td></tr>"
                    "<tr><td style=\"padding:14px 28px 6px 28px;text-align:center;\">"
                    f"<a href=\"{onboarding_link}\" "
                    "style=\"display:inline-block;background:#2563eb;color:#ffffff;text-decoration:none;"
                    "font-weight:700;font-size:15px;line-height:1;padding:14px 24px;border-radius:10px;border:1px solid #1d4ed8;\">Completar configuracion</a>"
                    "</td></tr>"
                    "<tr><td style=\"padding:12px 28px 16px 28px;\">"
                    "<div style=\"padding:12px 14px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;\">"
                    "<p style=\"margin:0;color:#64748b;font-size:13px;line-height:1.55;\">"
                    "Si el boton no abre, copia y pega este enlace en tu navegador:</p>"
                    f"<p style=\"margin:6px 0 0 0;word-break:break-all;color:#1e40af;font-size:12px;line-height:1.5;\">{onboarding_link}</p>"
                    "</div>"
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

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers=headers,
                json=payload,
            )
    except Exception as exc:
        logger.warning("Failed to send onboarding email to %s: %s", owner_email, exc, exc_info=True)
        return await _send_via_supabase_fallback("sendgrid_exception")

    if 200 <= response.status_code < 300:
        return True, "Setup email sent successfully."

    logger.warning(
        "Setup email provider rejected request for %s: status=%s body=%s",
        owner_email,
        response.status_code,
        response.text[:300],
    )
    sent, message = await _send_via_supabase_fallback(f"sendgrid_status_{response.status_code}")
    if sent:
        return True, message
    return False, f"Email provider returned {response.status_code}. Share the setup link manually."
