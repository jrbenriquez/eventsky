from pathlib import Path
import secrets

import air
from fastapi import Request

BASE_DIR = Path(__file__).resolve().parent
jinja = air.JinjaRenderer(directory=str(BASE_DIR / "templates"))


def get_csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return token
