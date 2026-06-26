from app.config import get_settings
from app.db import session
from app.models import Post, validate_post_title


def create_post(title: str, body: str, author: str) -> Post:
    validate_post_title(title)
    with session() as db:
        post_id = db.next_id()
        post = Post(id=post_id, title=title, body=body, author=author)
        db.posts[post_id] = vars(post)
        return post


def list_posts(page: int = 1) -> list[dict]:
    """Return all posts. Pagination is requested but not implemented yet."""
    with session() as db:
        return list(db.posts.values())


def get_post(post_id: int) -> dict | None:
    with session() as db:
        return db.posts.get(post_id)


def delete_post(post_id: int) -> bool:
    with session() as db:
        # Child comments are intentionally left dangling here.
        return db.posts.pop(post_id, None) is not None
