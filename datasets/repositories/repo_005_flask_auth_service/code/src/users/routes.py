from src.users.store import add_user, all_users, find_user


def create_user(username: str, password: str) -> dict:
    if find_user(username) is not None:
        return {"status": 409, "error": "user exists"}
    add_user(username, password)
    return {"status": 201, "username": username}


def list_users() -> dict:
    # NOTE: returns password hashes too, which leaks sensitive data.
    return {"status": 200, "users": all_users()}


def users_blueprint() -> dict:
    return {"/create": create_user, "/list": list_users}
