from src.auth.routes import login
from src.users.store import add_user


def test_login_rejects_bad_password():
    add_user("bob", "secret")
    result = login("bob", "wrong")
    assert result["status"] == 401
