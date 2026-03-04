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
                    "Usa este enlace seguro para definir tu contrasena y terminar la configuracion:\n"
                    f"{onboarding_link}\n\n"
                    "Si el enlace expira, contacta a tu administrador para generar uno nuevo."
                ),
            },
            {
                "type": "text/html",
                "value": (
                    "<div style=\"background:#f3f4f6;padding:24px 0;font-family:Arial,sans-serif;\">"
                    "<table role=\"presentation\" cellpadding=\"0\" cellspacing=\"0\" border=\"0\" width=\"100%\">"
                    "<tr><td align=\"center\">"
                    "<table role=\"presentation\" cellpadding=\"0\" cellspacing=\"0\" border=\"0\" width=\"560\" "
                    "style=\"max-width:560px;background:#ffffff;border:1px solid #e5e7eb;border-radius:12px;\">"
                    "<tr><td style=\"padding:24px 24px 8px 24px;text-align:center;\">"
                    "<svg width=\"52\" height=\"44\" viewBox=\"0 0 52 44\" fill=\"none\" "
                    "xmlns=\"http://www.w3.org/2000/svg\" style=\"display:block;margin:0 auto 12px auto;\">"
                    "<defs><linearGradient id=\"evagr\" x1=\"0\" y1=\"0\" x2=\"1\" y2=\"1\">"
                    "<stop offset=\"0%\" stop-color=\"#2563EB\"/><stop offset=\"100%\" stop-color=\"#60A5FA\"/>"
                    "</linearGradient></defs>"
                    "<g transform=\"skewX(-15) translate(6,0)\">"
                    "<rect x=\"0\" y=\"14\" width=\"6\" height=\"16\" rx=\"3\" fill=\"url(#evagr)\" opacity=\"0.9\"/>"
                    "<rect x=\"10\" y=\"8\" width=\"6\" height=\"28\" rx=\"3\" fill=\"url(#evagr)\"/>"
                    "<rect x=\"20\" y=\"2\" width=\"6\" height=\"40\" rx=\"3\" fill=\"url(#evagr)\"/>"
                    "<rect x=\"30\" y=\"8\" width=\"6\" height=\"28\" rx=\"3\" fill=\"url(#evagr)\"/>"
                    "<rect x=\"40\" y=\"14\" width=\"6\" height=\"16\" rx=\"3\" fill=\"url(#evagr)\" opacity=\"0.9\"/>"
                    "</g></svg>"
                    "<div style=\"font-size:14px;line-height:1;color:#2563eb;font-weight:700;margin-bottom:8px;\">Eva AI</div>"
                    f"<div style=\"font-size:28px;line-height:1.25;color:#111827;font-weight:700;\">Hola {display_name}</div>"
                    "</td></tr>"
                    "<tr><td style=\"padding:0 24px 8px 24px;\">"
                    f"<p style=\"margin:0 0 14px 0;color:#374151;font-size:15px;line-height:1.6;\">"
                    f"Tu cuenta de <strong>{product_label}</strong> esta lista.</p>"
                    "<p style=\"margin:0 0 14px 0;color:#374151;font-size:15px;line-height:1.6;\">"
                    "Usa este enlace seguro para definir tu contrasena y terminar la configuracion:</p>"
                    "</td></tr>"
                    "<tr><td style=\"padding:0 24px 8px 24px;text-align:center;\">"
                    f"<a href=\"{onboarding_link}\" "
                    "style=\"display:inline-block;background:#2563eb;color:#ffffff;text-decoration:none;"
                    "font-weight:700;font-size:14px;padding:12px 18px;border-radius:8px;\">Completar configuracion</a>"
                    "</td></tr>"
                    "<tr><td style=\"padding:8px 24px 20px 24px;\">"
                    "<p style=\"margin:0;color:#6b7280;font-size:12px;line-height:1.6;\">"
                    "Si el boton no abre, copia y pega este enlace en tu navegador:</p>"
                    f"<p style=\"margin:6px 0 0 0;word-break:break-all;color:#1d4ed8;font-size:12px;\">{onboarding_link}</p>"
                    "</td></tr>"
                    "<tr><td style=\"padding:0 24px 24px 24px;\">"
                    "<p style=\"margin:0;color:#6b7280;font-size:12px;line-height:1.6;\">"
                    "Si el enlace expira, contacta a tu administrador para generar uno nuevo.</p>"
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
