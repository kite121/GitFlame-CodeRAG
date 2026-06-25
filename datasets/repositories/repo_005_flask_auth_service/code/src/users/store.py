_USERS: dict[str, dict] = {}


def add_user(username: str, password: str, role: str = "member") -> dict:
    user = {"username": username, "password": password, "role": role}
    _USERS[username] = user
    return user


def find_user(username: str) -> dict | None:
    return _USERS.get(username)


def all_users() -> list[dict]:
    return list(_USERS.values())
