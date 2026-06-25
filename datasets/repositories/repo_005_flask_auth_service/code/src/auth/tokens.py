import base64
import hmac
import json
import time
from hashlib import sha256

SECRET = b"change-me"


def sign(payload: dict) -> str:
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    signature = hmac.new(SECRET, body.encode(), sha256).hexdigest()
    return f"{body}.{signature}"


def verify(token: str) -> dict:
    body, signature = token.split(".")
    expected = hmac.new(SECRET, body.encode(), sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise ValueError("invalid signature")
    payload = json.loads(base64.urlsafe_b64decode(body))
    if payload.get("exp", 0) < time.time():
        raise ValueError("token expired")
    return payload
