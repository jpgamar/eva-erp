from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from src.eva_platform.router.accounts import _map_permanent_delete_error


def _integrity_error(message: str) -> IntegrityError:
    class _Orig(Exception):
        pass

    return IntegrityError("DELETE FROM accounts", params={}, orig=_Orig(message))


def test_map_permanent_delete_error_foreign_key_to_409_with_table_name() -> None:
    exc = _integrity_error(
        'update or delete on table "accounts" violates foreign key constraint '
        '"billing_documents_account_id_fkey" on table "billing_documents"'
    )

    mapped = _map_permanent_delete_error(exc)

    assert isinstance(mapped, HTTPException)
    assert mapped.status_code == 409
    assert "blocking table: billing_documents" in mapped.detail


def test_map_permanent_delete_error_unknown_to_500() -> None:
    exc = _integrity_error("some unexpected integrity error")

    mapped = _map_permanent_delete_error(exc)

    assert isinstance(mapped, HTTPException)
    assert mapped.status_code == 500
