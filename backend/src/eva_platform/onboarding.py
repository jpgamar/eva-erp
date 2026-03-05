"""Owner onboarding helpers for account provisioning flows."""

from __future__ import annotations

import asyncio
import logging
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse

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
DEFAULT_SENDGRID_FROM_EMAIL = "no-reply@goeva.ai"
DEFAULT_SENDGRID_FROM_NAME = "EvaAI"
DEFAULT_SENDGRID_REPLY_TO = "hi@goeva.ai"
SENDGRID_MAX_ATTEMPTS = 3
SENDGRID_RETRYABLE_STATUSES = {408, 409, 425, 429, 500, 502, 503, 504}
SENDGRID_SUPPRESSION_ENDPOINTS = (
    ("blocks", "/v3/suppression/blocks/{email}"),
    ("bounces", "/v3/suppression/bounces/{email}"),
    ("spam_reports", "/v3/suppression/spam_reports/{email}"),
    ("invalid_emails", "/v3/suppression/invalid_emails/{email}"),
    ("unsubscribes", "/v3/suppression/unsubscribes/{email}"),
    ("global_unsubscribe", "/v3/asm/suppressions/global/{email}"),
)


async def _get_sendgrid_active_suppressions(
    client: httpx.AsyncClient,
    *,
    email: str,
    headers: dict[str, str],
) -> tuple[list[str], bool]:
    encoded_email = quote(email.strip().lower(), safe="")
    active: list[str] = []
    permissions_unknown = False
    for suppression_key, endpoint_template in SENDGRID_SUPPRESSION_ENDPOINTS:
        endpoint = endpoint_template.format(email=encoded_email)
        url = f"https://api.sendgrid.com{endpoint}"
        try:
            get_resp = await client.get(url, headers=headers)
        except Exception as exc:
            permissions_unknown = True
            logger.warning(
                "SendGrid suppression read failed for %s (%s): %s",
                email,
                suppression_key,
                exc,
            )
            continue

        if get_resp.status_code == 200:
            active.append(suppression_key)
            continue
        if get_resp.status_code == 404:
            continue
        if get_resp.status_code in {401, 403}:
            permissions_unknown = True
            logger.warning(
                "SendGrid suppression read denied for %s (%s): status=%s body=%s",
                email,
                suppression_key,
                get_resp.status_code,
                get_resp.text[:200],
            )
            continue

        logger.warning(
            "SendGrid suppression read unexpected status for %s (%s): status=%s body=%s",
            email,
            suppression_key,
            get_resp.status_code,
            get_resp.text[:200],
        )

    return active, permissions_unknown


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
        await SupabaseAdminClient.admin_mark_password_change_required(
            email=owner_email,
            owner_name=owner_name,
        )
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
    async def _clear_sendgrid_suppressions(
        client: httpx.AsyncClient,
        *,
        email: str,
    ) -> tuple[list[str], bool]:
        encoded_email = quote(email.strip().lower(), safe="")
        cleared: list[str] = []
        permission_denied = False
        for suppression_key, endpoint_template in SENDGRID_SUPPRESSION_ENDPOINTS:
            endpoint = endpoint_template.format(email=encoded_email)
            url = f"https://api.sendgrid.com{endpoint}"
            try:
                delete_resp = await client.delete(url, headers=headers)
            except Exception as exc:
                logger.warning(
                    "SendGrid suppression clear failed for %s (%s): %s",
                    email,
                    suppression_key,
                    exc,
                )
                continue

            if delete_resp.status_code not in {200, 202, 204, 404}:
                if delete_resp.status_code in {401, 403}:
                    permission_denied = True
                logger.warning(
                    "SendGrid suppression clear rejected for %s (%s): status=%s body=%s",
                    email,
                    suppression_key,
                    delete_resp.status_code,
                    delete_resp.text[:200],
                )
                continue

            if delete_resp.status_code != 404:
                cleared.append(suppression_key)
                logger.warning("Cleared SendGrid suppression for %s (%s)", email, suppression_key)

        return cleared, permission_denied

    api_key = (settings.sendgrid_api_key or "").strip()
    if not api_key:
        return False, "Failed to send setup email (SendGrid not configured). Share the setup link manually."

    recipient_email = owner_email.strip().lower()
    if not recipient_email:
        return False, "Failed to send setup email (owner email is empty). Share the setup link manually."

    configured_sender_email = (settings.sendgrid_from_email or "").strip().lower()
    sender_email = DEFAULT_SENDGRID_FROM_EMAIL
    if configured_sender_email and configured_sender_email != DEFAULT_SENDGRID_FROM_EMAIL:
        logger.warning(
            "Overriding SENDGRID_FROM_EMAIL=%s to enforced onboarding sender=%s",
            configured_sender_email,
            DEFAULT_SENDGRID_FROM_EMAIL,
        )

    configured_sender_name = (settings.sendgrid_from_name or "").strip()
    sender_name = configured_sender_name or DEFAULT_SENDGRID_FROM_NAME
    if sender_name.lower() == "eva erp":
        sender_name = DEFAULT_SENDGRID_FROM_NAME

    reply_to_email = (settings.sendgrid_reply_to or "").strip().lower() or DEFAULT_SENDGRID_REPLY_TO
    display_name = owner_name.strip() or "there"

    payload = {
        "personalizations": [
            {
                "to": [{"email": recipient_email}],
                "subject": f"Configura tu contrasena para {product_label}",
            }
        ],
        "from": {
            "email": sender_email,
            "name": sender_name,
        },
        "reply_to": {"email": reply_to_email},
        "mail_settings": {
            "bypass_list_management": {"enable": True},
        },
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
                    "<div style=\"margin:0;padding:24px;background:#f8fafc;font-family:Arial,sans-serif;color:#0f172a;\">"
                    "<div style=\"max-width:520px;margin:0 auto;background:#ffffff;border:1px solid #e2e8f0;border-radius:10px;padding:24px;\">"
                    "<h1 style=\"margin:0 0 12px 0;font-size:22px;line-height:1.3;color:#0f172a;\">EvaAI</h1>"
                    f"<p style=\"margin:0 0 10px 0;font-size:16px;line-height:1.5;\">Hola {display_name},</p>"
                    f"<p style=\"margin:0 0 18px 0;font-size:16px;line-height:1.5;\">Tu cuenta de <strong>{product_label}</strong> esta lista.</p>"
                    f"<a href=\"{onboarding_link}\" style=\"display:inline-block;background:#2563eb;color:#ffffff;text-decoration:none;font-weight:600;font-size:15px;padding:12px 18px;border-radius:8px;\">Configurar contrasena</a>"
                    f"<p style=\"margin:16px 0 0 0;font-size:13px;line-height:1.5;color:#64748b;\">Si no solicitaste este acceso, ignora este correo.</p>"
                    "</div></div>"
                ),
            },
        ],
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    response: httpx.Response | None = None
    suppressions_seen: list[str] = []
    for attempt in range(1, SENDGRID_MAX_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                if attempt == 1:
                    active_before, permissions_unknown = await _get_sendgrid_active_suppressions(
                        client,
                        email=recipient_email,
                        headers=headers,
                    )
                    if permissions_unknown and not active_before:
                        logger.warning(
                            "Proceeding with setup email send for %s without full suppression visibility.",
                            recipient_email,
                        )
                    if active_before:
                        cleared, permission_denied = await _clear_sendgrid_suppressions(
                            client,
                            email=recipient_email,
                        )
                        active_after, permissions_unknown_after = await _get_sendgrid_active_suppressions(
                            client,
                            email=recipient_email,
                            headers=headers,
                        )
                        if (permissions_unknown or permissions_unknown_after or permission_denied) and not cleared:
                            logger.warning(
                                "Could not fully verify SendGrid suppressions for %s due to permission limits.",
                                recipient_email,
                            )
                        if active_after:
                            suppressions_seen = active_after
                            logger.warning(
                                "Recipient %s remains in SendGrid suppressions (%s). "
                                "Continuing with bypass_list_management for transactional setup email.",
                                recipient_email,
                                ", ".join(active_after),
                            )
                        elif active_before:
                            suppressions_seen = active_before
                response = await client.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    headers=headers,
                    json=payload,
                )
        except Exception as exc:
            logger.warning(
                "Failed to send onboarding email to %s (attempt %s/%s): %s",
                recipient_email,
                attempt,
                SENDGRID_MAX_ATTEMPTS,
                exc,
                exc_info=True,
            )
            if attempt < SENDGRID_MAX_ATTEMPTS:
                await asyncio.sleep(0.6 * attempt)
                continue
            return False, "Failed to send setup email. Share the setup link manually."

        if 200 <= response.status_code < 300:
            message_id = (
                (response.headers.get("X-Message-Id") or "").strip()
                or (response.headers.get("x-message-id") or "").strip()
            )
            suppression_note = ""
            if suppressions_seen:
                suppression_note = (
                    " Recipient appears in SendGrid suppressions "
                    f"({', '.join(suppressions_seen)}), but bypass_list_management was requested."
                )
            if message_id:
                return True, f"Setup email accepted by provider (message_id: {message_id}).{suppression_note}"
            return True, f"Setup email accepted by provider.{suppression_note}"

        should_retry = response.status_code in SENDGRID_RETRYABLE_STATUSES
        logger.warning(
            "Setup email provider rejected request for %s: status=%s attempt=%s/%s body=%s",
            recipient_email,
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
    provider_error = ""
    if response is not None:
        raw = (response.text or "").strip().replace("\n", " ")
        if raw:
            provider_error = f" ({raw[:200]})"
    return False, f"Email provider returned {status}{provider_error}. Share the setup link manually."
