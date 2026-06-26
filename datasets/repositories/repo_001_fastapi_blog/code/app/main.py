from app.api import auth, comments, posts


def build_routes() -> dict:
    """Map HTTP routes to handler callables."""
    return {
        "POST /auth/register": auth.register,
        "POST /auth/refresh": auth.refresh_token,
        "GET /posts": posts.list_posts,
        "POST /posts": posts.create_post,
        "DELETE /posts/{id}": posts.delete_post,
        "GET /posts/{id}/comments": comments.comments_for_post,
        "POST /posts/{id}/comments": comments.add_comment,
    }


def handle(route: str, *args, **kwargs):
    handler = build_routes()[route]
    return handler(*args, **kwargs)
