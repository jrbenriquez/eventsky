from typing import Optional

import air
from fastapi import Depends
from fastapi import HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session as SASession

from eventcloud.db import get_db

from .models import User
from .utils import get_session_user_id


def current_user(request: air.Request, db: SASession = Depends(get_db)) -> User | RedirectResponse:
    uid = get_session_user_id(request)
    if not uid:
        raise HTTPException(status_code=303, headers={"Location": "/auth/login"})
    user: Optional[User] = db.query(User).filter_by(id=uid).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=303, headers={"Location": "/auth/login"})
    return user
