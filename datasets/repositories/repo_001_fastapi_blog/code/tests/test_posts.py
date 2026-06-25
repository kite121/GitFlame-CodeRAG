import pytest

from app.api.posts import create_post


def test_create_post_rejects_empty_title():
    with pytest.raises(ValueError):
        create_post("", "body", "alice")


def test_create_post_returns_post():
    post = create_post("Hello", "world", "alice")
    assert post.title == "Hello"
