import secrets
from fastapi import Request, HTTPException, status

CSRF_KEY = "csrf"

def ensure_csrf(request: Request):
    token = request.session.get(CSRF_KEY)
    if not token:
        request.session[CSRF_KEY] = secrets.token_urlsafe(24)

def require_csrf(request: Request):
    sent = request.headers.get("X-CSRF-Token") or request.form().get(CSRF_KEY)
    real = request.session.get(CSRF_KEY)
    if not real or not sent or sent != real:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bad CSRF token")
