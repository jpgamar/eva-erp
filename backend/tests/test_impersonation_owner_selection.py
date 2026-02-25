from types import SimpleNamespace

from src.eva_platform.router.impersonation import _build_owner_candidates


def _account(owner_user_id: str | None):
    return SimpleNamespace(owner_user_id=owner_user_id)


def _user(
    *,
    user_id: str,
    email: str,
    role: str = "MEMBER",
    status: str = "ACTIVE",
):
    return SimpleNamespace(
        user_id=user_id,
        email=email,
        role=role,
        status=status,
    )


def test_owner_candidates_prioritize_account_owner_user_id():
    account = _account("owner-id")
    users = [
        _user(user_id="owner-role", email="owner-role@example.com", role="OWNER", status="ACTIVE"),
        _user(user_id="owner-id", email="owner-id@example.com", role="MEMBER", status="ACTIVE"),
    ]

    candidates = _build_owner_candidates(account, users)
    assert [u.user_id for u in candidates] == ["owner-id", "owner-role"]


def test_owner_candidates_only_include_owner_based_users():
    account = _account(None)
    users = [
        _user(user_id="member-1", email="member-1@example.com", role="MEMBER", status="ACTIVE"),
        _user(user_id="owner-1", email="owner-1@example.com", role="owner", status="ACTIVE"),
        _user(user_id="owner-2", email="owner-2@example.com", role="OWNER", status="INVITED"),
    ]

    candidates = _build_owner_candidates(account, users)
    assert [u.user_id for u in candidates] == ["owner-1", "owner-2"]


def test_owner_candidates_ignore_users_without_email():
    account = _account("owner-id")
    users = [
        _user(user_id="owner-id", email=" ", role="OWNER", status="ACTIVE"),
        _user(user_id="fallback-owner", email="fallback@example.com", role="OWNER", status="ACTIVE"),
    ]

    candidates = _build_owner_candidates(account, users)
    assert [u.user_id for u in candidates] == ["fallback-owner"]
