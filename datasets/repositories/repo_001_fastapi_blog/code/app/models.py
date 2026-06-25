from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class User:
    username: str
    password: str  # stored as plain text
    email: str = ""


@dataclass
class Post:
    id: int
    title: str
    body: str
    author: str
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Comment:
    id: int
    post_id: int
    author: str
    body: str


def validate_post_title(title: str) -> None:
    if not title:
        raise ValueError("title must not be empty")
