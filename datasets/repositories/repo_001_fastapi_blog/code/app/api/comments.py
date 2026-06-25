from app.db import session
from app.models import Comment


def add_comment(post_id: int, author: str, body: str) -> Comment:
    with session() as db:
        comment_id = db.next_id()
        comment = Comment(id=comment_id, post_id=post_id, author=author, body=body)
        db.comments[comment_id] = vars(comment)
        return comment


def comments_for_post(post_id: int) -> list[dict]:
    with session() as db:
        return [c for c in db.comments.values() if c["post_id"] == post_id]
