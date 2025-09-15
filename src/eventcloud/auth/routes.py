import air
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy.orm import Session as SASession
from air.responses import RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import User
from .schema import UserOut
from .utils import hash_password, verify_password, set_session_user
from eventcloud.db import get_db  # your SessionLocal dependency
from eventcloud.utils import jinja

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=UserOut)
def signup(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    username: str | None = Form(None),
    db: SASession = Depends(get_db),
):
    email_norm = email.strip().lower()
    exists = db.query(User).filter(func.lower(User.email) == email_norm).first()
    if exists:
        raise HTTPException(status_code=400, detail="Email already registered.")

    if username:
        uname_taken = db.query(User).filter(User.username == username).first()
        if uname_taken:
            raise HTTPException(status_code=400, detail="Username already taken.")

    user = User(
        email=email_norm, username=username, password_hash=hash_password(password)
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    set_session_user(request, user.id)  # auto-login
    return user


@router.post("/login")
def login(
    request: air.Request,
    identifier: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    ident = identifier.strip()

    # Lookup by email (case-insensitive) or username
    user = (
        db.query(User).filter(func.lower(User.email) == ident.lower()).first()
        or db.query(User).filter(User.username == ident).first()
    )

    if not user or not verify_password(password, user.password_hash):
        # Store error in session (flash-like)
        request.session["login_error"] = (
            "Last attempt was invalid email/username or password"
        )
        return RedirectResponse(url="/auth/login", status_code=303)

    if not user.is_active:
        request.session["login_error"] = "User account inactive"
        return RedirectResponse(url="/auth/login", status_code=303)

    # Success: store uid in session
    set_session_user(request, user.id)

    # Optional: clean up any stale login_error
    request.session.pop("login_error", None)

    # Redirect to dashboard (or previous URL if you track it)
    return RedirectResponse(url="/events/", status_code=303)


@router.get("/login")
def login_page(request: air.Request):
    if request.session.get("uid"):
        return RedirectResponse(url="/", status_code=303)
    return jinja(request, "login.html")


@router.get("/logout")
def logout_page(request: Request):
    if not request.session.get("uid"):
        return RedirectResponse(url="/", status_code=303)
    return jinja(request, "logout.html")


@router.post("/logout")
def perform_logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=303)
