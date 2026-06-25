import time

from src.auth.tokens import sign, verify
from src.users.store import find_user


def login(username: str, password: str) -> dict:
    user = find_user(username)
    if user is None or user["password"] != password:
        return {"status": 401, "error": "invalid credentials"}
    token = sign({"sub": username, "exp": time.time() + 3600})
    return {"status": 200, "token": token}


def refresh(token: str) -> dict:
    # BUG: ValueError from verify() is not translated into a 401 response.
    payload = verify(token)
    new_token = sign({"sub": payload["sub"], "exp": time.time() + 3600})
    return {"status": 200, "token": new_token}


def auth_blueprint() -> dict:
    return {"/login": login, "/refresh": refresh}
