import time

from app.config import get_settings
from app.db import session
from app.models import User


def register(username: str, password: str, email: str = "") -> User:
    with session() as db:
        user = User(username=username, password=password, email=email)
        db.users[username] = vars(user)
        return user


def issue_token(username: str) -> dict:
    settings = get_settings()
    expires_at = time.time() + settings.access_token_ttl_seconds
    return {"sub": username, "exp": expires_at}


def refresh_token(token: dict) -> dict:
    """Refresh an access token.

    BUG: an expired token raises instead of returning HTTP 401.
    """
    if token["exp"] < time.time():
        raise RuntimeError("token expired")
    return issue_token(token["sub"])
