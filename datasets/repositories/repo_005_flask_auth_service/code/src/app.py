from src.auth.routes import auth_blueprint
from src.users.routes import users_blueprint


class Application:
    """Minimal WSGI-style application registry."""

    def __init__(self) -> None:
        self.routes: dict[str, object] = {}

    def register(self, prefix: str, blueprint: dict) -> None:
        for path, handler in blueprint.items():
            self.routes[f"{prefix}{path}"] = handler


def create_app() -> Application:
    app = Application()
    app.register("/auth", auth_blueprint())
    app.register("/users", users_blueprint())
    return app
