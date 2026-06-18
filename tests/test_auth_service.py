from services.auth_service import AuthError, AuthService


def test_register_and_authenticate_user():
    auth = AuthService()
    username = "alice_test_auth"
    password = "secret123"

    try:
        user = auth.register(username, password, "Alice")
    except AuthError:
        user = auth.authenticate(username, password)

    assert user.username == username
    assert user.display_name in {"Alice", username}
    assert auth.authenticate(username, password).id == user.id
