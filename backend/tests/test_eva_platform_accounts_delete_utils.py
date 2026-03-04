import asyncio
import uuid
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy.exc import DBAPIError, IntegrityError

from src.eva_platform.router.accounts import (
    _cleanup_pipeline_stage_account_refs,
    _is_last_won_stage_delete_error,
    _map_permanent_delete_error,
)


def _integrity_error(message: str) -> IntegrityError:
    class _Orig(Exception):
        pass

    return IntegrityError("DELETE FROM accounts", params={}, orig=_Orig(message))


def _dbapi_error(message: str) -> DBAPIError:
    class _Orig(Exception):
        pass

    return DBAPIError("DELETE FROM accounts", params={}, orig=_Orig(message))


class _RowsResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _ExecResult:
    def __init__(self, rowcount: int):
        self.rowcount = rowcount


class _FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    async def execute(self, stmt, params=None):
        self.calls.append((str(stmt), params))
        return self._responses.pop(0)


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


def test_map_permanent_delete_error_generic_cannot_delete_to_409() -> None:
    exc = _dbapi_error("Cannot delete account while active rents pipeline state exists")

    mapped = _map_permanent_delete_error(exc)

    assert isinstance(mapped, HTTPException)
    assert mapped.status_code == 409
    assert "related records still exist" in mapped.detail.lower()
    assert "reason:" in mapped.detail.lower()


def test_is_last_won_stage_delete_error_detects_raise_error_message() -> None:
    exc = _dbapi_error("Cannot delete the last won stage in a pipeline")
    assert _is_last_won_stage_delete_error(exc) is True


def test_cleanup_pipeline_stage_account_refs_updates_nullable_and_not_null_refs() -> None:
    account_id = uuid.uuid4()
    refs = [
        SimpleNamespace(
            qualified_table="public.pipeline_stages",
            quoted_column="account_id",
            is_nullable=True,
        ),
        SimpleNamespace(
            qualified_table="public.pipeline_stage_states",
            quoted_column="owner_account_id",
            is_nullable=False,
        ),
    ]
    session = _FakeSession(
        [
            _RowsResult(refs),
            _ExecResult(2),
            _ExecResult(1),
        ]
    )

    changed = asyncio.run(_cleanup_pipeline_stage_account_refs(session, account_id))

    assert changed is True
    assert "SET account_id = NULL" in session.calls[1][0]
    assert "DELETE FROM public.pipeline_stage_states" in session.calls[2][0]
    assert "WHERE owner_account_id = :account_id" in session.calls[2][0]


def test_cleanup_pipeline_stage_account_refs_returns_false_when_no_refs() -> None:
    session = _FakeSession([_RowsResult([])])
    changed = asyncio.run(_cleanup_pipeline_stage_account_refs(session, uuid.uuid4()))
    assert changed is False


def test_cleanup_pipeline_stage_account_refs_deletes_not_null_refs_without_fallback() -> None:
    refs = [
        SimpleNamespace(
            qualified_table="public.pipeline_stage_states",
            quoted_column="owner_account_id",
            is_nullable=False,
        ),
    ]
    session = _FakeSession([_RowsResult(refs), _ExecResult(1)])
    changed = asyncio.run(_cleanup_pipeline_stage_account_refs(session, uuid.uuid4()))
    assert changed is True
