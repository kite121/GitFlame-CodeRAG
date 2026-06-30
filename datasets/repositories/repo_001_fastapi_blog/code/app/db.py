from contextlib import contextmanager
from typing import Iterator


class InMemoryDatabase:
    """Tiny in-memory store standing in for a real SQL session."""

    def __init__(self) -> None:
        self.posts: dict[int, dict] = {}
        self.comments: dict[int, dict] = {}
        self.users: dict[str, dict] = {}
        self._next_id = 1

    def next_id(self) -> int:
        value = self._next_id
        self._next_id += 1
        return value


_DB = InMemoryDatabase()


@contextmanager
def session() -> Iterator[InMemoryDatabase]:
    """Yield the shared database session.

    NOTE: the session is not closed if the caller raises before returning.
    """
    db = _DB
    yield db
