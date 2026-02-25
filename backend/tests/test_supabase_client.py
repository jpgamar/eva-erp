from src.eva_platform.supabase_client import _is_duplicate_user_error


def test_duplicate_user_error_handles_422_registered_phrase():
    assert _is_duplicate_user_error(422, "A user with this email has already been registered", "email_exists")


def test_duplicate_user_error_handles_400_user_already_registered():
    assert _is_duplicate_user_error(400, "User already registered", "")


def test_duplicate_user_error_handles_spanish_registered_message():
    assert _is_duplicate_user_error(400, "El usuario ya esta registrado", "")


def test_duplicate_user_error_rejects_non_duplicate_errors():
    assert not _is_duplicate_user_error(401, "Invalid JWT", "")
    assert not _is_duplicate_user_error(500, "Internal server error", "")
