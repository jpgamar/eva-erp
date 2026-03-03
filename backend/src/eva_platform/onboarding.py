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
    account_name: str,
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
        account_name=account_name,
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
    account_name: str,
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
                "subject": f"Set up your access to {account_name}",
            }
        ],
        "from": {
            "email": "no-reply@goeva.ai",
            "name": "Eva ERP",
        },
        "content": [
            {
                "type": "text/plain",
                "value": (
                    f"Hi {display_name},\n\n"
                    f"Your account for {account_name} is ready.\n"
                    "Use this secure link to set your password and finish setup:\n"
                    f"{onboarding_link}\n\n"
                    "If the link expires, contact your administrator for a new one."
                ),
            },
            {
                "type": "text/html",
                "value": (
                    f"<p>Hi {display_name},</p>"
                    f"<p>Your account for <strong>{account_name}</strong> is ready.</p>"
                    "<p>Use this secure link to set your password and finish setup:</p>"
                    f"<p><a href=\"{onboarding_link}\">Complete account setup</a></p>"
                    "<p>If the link expires, contact your administrator for a new one.</p>"
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
