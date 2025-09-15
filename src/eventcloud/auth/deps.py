from typing import Optional

from fastapi import Depends
from fastapi import Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session as SASession

# Reuse your app's DB session maker:
from eventcloud.db import get_db  # <- change to your DB dependency

from .models import User
from .utils import get_session_user_id


def current_user(request: Request, db: SASession = Depends(get_db)) -> User | RedirectResponse:
    uid = get_session_user_id(request)
    if not uid:
        return RedirectResponse(url="/login", status_code=303)
    user: Optional[User] = db.query(User).filter_by(id=uid).first()
    if not user or not user.is_active:
        return RedirectResponse(url="/login", status_code=303)
    return user
