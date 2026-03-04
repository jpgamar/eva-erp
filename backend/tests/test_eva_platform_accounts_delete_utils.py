from fastapi import HTTPException
from sqlalchemy.exc import DBAPIError, IntegrityError

from src.eva_platform.router.accounts import _map_permanent_delete_error


def _integrity_error(message: str) -> IntegrityError:
    class _Orig(Exception):
        pass

    return IntegrityError("DELETE FROM accounts", params={}, orig=_Orig(message))


def _dbapi_error(message: str) -> DBAPIError:
    class _Orig(Exception):
        pass

    return DBAPIError("DELETE FROM accounts", params={}, orig=_Orig(message))


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


def test_map_permanent_delete_error_last_won_stage_to_409() -> None:
    exc = _dbapi_error("Cannot delete the last won stage in a pipeline")

    mapped = _map_permanent_delete_error(exc)

    assert isinstance(mapped, HTTPException)
    assert mapped.status_code == 409
    assert "last won stage" in mapped.detail.lower()
