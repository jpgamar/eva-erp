import asyncio

import pytest
import httpx

from src.eva_platform.supabase_client import (
    SupabaseAdminClient,
    SupabaseConfigError,
    SupabaseDuplicateUnresolvedError,
    SupabaseInvalidPayloadError,
    SupabaseUpstreamUnavailableError,
    _is_duplicate_user_error,
    map_supabase_error_to_http,
)


def test_duplicate_user_error_handles_422_registered_phrase():
    assert _is_duplicate_user_error(422, "A user with this email has already been registered", "email_exists")


def test_duplicate_user_error_handles_400_user_already_registered():
    assert _is_duplicate_user_error(400, "User already registered", "")


def test_duplicate_user_error_handles_spanish_registered_message():
    assert _is_duplicate_user_error(400, "El usuario ya esta registrado", "")


def test_duplicate_user_error_rejects_non_duplicate_errors():
    assert not _is_duplicate_user_error(401, "Invalid JWT", "")
    assert not _is_duplicate_user_error(500, "Internal server error", "")


def test_extract_user_id_prefers_top_level_id():
    payload = {"id": "top-level-id", "user": {"id": "nested-id"}}
    assert SupabaseAdminClient.extract_user_id(payload) == "top-level-id"


def test_extract_user_id_supports_nested_user_payload():
    payload = {"user": {"id": "nested-id"}}
    assert SupabaseAdminClient.extract_user_id(payload) == "nested-id"


def test_extract_user_id_supports_properties_payload():
    payload = {"properties": {"user_id": "properties-id"}}
    assert SupabaseAdminClient.extract_user_id(payload) == "properties-id"


def test_extract_user_id_raises_for_invalid_payload():
    with pytest.raises(SupabaseInvalidPayloadError):
        SupabaseAdminClient.extract_user_id({"email": "no-id@example.com"})


def test_map_supabase_error_duplicate_unresolved_to_409():
    status, detail = map_supabase_error_to_http(SupabaseDuplicateUnresolvedError("duplicate unresolved"))
    assert status == 409
    assert detail == "duplicate unresolved"


def test_map_supabase_error_upstream_unavailable_to_503():
    status, detail = map_supabase_error_to_http(SupabaseUpstreamUnavailableError("upstream unavailable"))
    assert status == 503
    assert detail == "upstream unavailable"


def test_map_supabase_error_config_to_500():
    status, detail = map_supabase_error_to_http(SupabaseConfigError("misconfigured"))
    assert status == 500
    assert detail == "misconfigured"


def test_request_with_retries_raises_upstream_unavailable_on_transport_failure():
    class _AlwaysFailClient:
        async def request(self, method: str, url: str, **kwargs):
            req = httpx.Request(method, url)
            raise httpx.ConnectError("connection failed", request=req)

    with pytest.raises(SupabaseUpstreamUnavailableError):
        asyncio.run(
            SupabaseAdminClient._request_with_retries(
                _AlwaysFailClient(),
                "GET",
                "https://example.com/auth/v1/admin/users",
            )
        )
