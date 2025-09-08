from passlib.context import CryptContext
from fastapi import Request

pwd_ctx = CryptContext(schemes=["argon2"], deprecated="auto")

def hash_password(raw: str) -> str:
    return pwd_ctx.hash(raw)

def verify_password(raw: str, hashed: str) -> bool:
    return pwd_ctx.verify(raw, hashed)

SESSION_USER_KEY = "uid"

def set_session_user(request: Request, user_id: int) -> None:
    request.session[SESSION_USER_KEY] = user_id

def clear_session_user(request: Request) -> None:
    request.session.pop(SESSION_USER_KEY, None)

def get_session_user_id(request: Request):
    return request.session.get(SESSION_USER_KEY)
