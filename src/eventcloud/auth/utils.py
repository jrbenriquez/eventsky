from functools import wraps

import air
from fastapi import Request
from passlib.context import CryptContext
from starlette.responses import RedirectResponse

pwd_ctx = CryptContext(schemes=["argon2"], deprecated="auto")

SESSION_USER_KEY = "uid"


def login_required(fn):
    @wraps(fn)
    def wrapper(request: air.Request, *args, **kwargs):
        print("TESSSSSST")
        print(request.session)
        if not request.session.get(SESSION_USER_KEY):
            return RedirectResponse("/auth/login", status_code=303)
        return fn(request, *args, **kwargs)

    return wrapper


def hash_password(raw: str) -> str:
    return pwd_ctx.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    return pwd_ctx.verify(raw, hashed)


def set_session_user(request: Request, user_id: int) -> None:
    request.session[SESSION_USER_KEY] = user_id


def clear_session_user(request: Request) -> None:
    request.session.pop(SESSION_USER_KEY, None)


def get_session_user_id(request: Request):
    return request.session.get(SESSION_USER_KEY)
