# eventcloud/auth/session_backend.py
from starlette.authentication import (
    AuthenticationBackend, AuthCredentials, BaseUser, UnauthenticatedUser
)
from starlette.requests import HTTPConnection
from sqlalchemy.orm import sessionmaker
from eventcloud.db import engine
from eventcloud.auth.models import User

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class AuthUser(BaseUser):
    def __init__(self, user: User):
        self._user = user

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def display_name(self) -> str:
        return self._user.username or self._user.email

    @property
    def identity(self) -> str:
        return str(self._user.id)

    # Optional: expose your model if you want in templates as request.user.user
    @property
    def email(self) -> User:
        return self._user.email

class SessionAuthBackend(AuthenticationBackend):
    async def authenticate(self, conn: HTTPConnection):
        # SessionMiddleware provides this
        session = conn.session  # type: ignore[attr-defined]
        user_id = session.get("uid")
        if not user_id:
            # no auth; Starlette will set UnauthenticatedUser()
            return

        # Load the user (sync DB here; fine for most apps)
        with SessionLocal() as db:
            user = db.get(User, user_id)

        if not user or not user.is_active:
            return  # treat as unauthenticated

        return AuthCredentials(["authenticated"]), AuthUser(user)
