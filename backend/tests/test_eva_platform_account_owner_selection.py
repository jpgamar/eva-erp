from types import SimpleNamespace

from src.eva_platform.router.accounts import _build_owner_candidates


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


def test_accounts_owner_candidates_prioritize_owner_user_id_active():
    account = _account("owner-id")
    users = [
        _user(user_id="owner-role", email="owner-role@example.com", role="OWNER", status="ACTIVE"),
        _user(user_id="owner-id", email="owner-id@example.com", role="MEMBER", status="ACTIVE"),
    ]

    candidates = _build_owner_candidates(account, users)
    assert [u.user_id for u in candidates] == ["owner-id", "owner-role"]


def test_accounts_owner_candidates_fallback_to_owner_role():
    account = _account(None)
    users = [
        _user(user_id="member", email="member@example.com", role="MEMBER", status="ACTIVE"),
        _user(user_id="owner-invited", email="owner-invited@example.com", role="OWNER", status="INVITED"),
        _user(user_id="owner-active", email="owner-active@example.com", role="OWNER", status="ACTIVE"),
    ]

    candidates = _build_owner_candidates(account, users)
    assert [u.user_id for u in candidates] == ["owner-active", "owner-invited"]


def test_accounts_owner_candidates_ignore_missing_email():
    account = _account("owner-id")
    users = [
        _user(user_id="owner-id", email=" ", role="OWNER", status="ACTIVE"),
        _user(user_id="owner-role", email="owner-role@example.com", role="OWNER", status="ACTIVE"),
    ]

    candidates = _build_owner_candidates(account, users)
    assert [u.user_id for u in candidates] == ["owner-role"]
