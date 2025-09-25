import air
from air.responses import Response
from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy import and_
from sqlalchemy import case
from sqlalchemy import or_
from sqlalchemy.orm import Session

from eventcloud.db import get_db
from eventcloud.db import SessionLocal
from eventcloud.models import EventMessage
from eventcloud.r2 import get_signed_url_for_key
from eventcloud.utils import jinja

router = APIRouter(tags=["messages"])


@router.get("/messageimage/")
def render_image(request: air.Request, key: str):
    url = get_signed_url_for_key(key)
    return jinja(request, "_message_image.html", {"url": url})


@router.get("/messageimagepreview/")
def render_image_preview(request: air.Request, key: str):
    url = get_signed_url_for_key(key)
    return jinja(request, "_message_image_preview.html", {"url": url})


@router.get("/events/{code}/check_older/")
def check_older_message(request: air.Request, code: str, before_id: str, limit: int = 10):
    """Checks for older messages and if yes returns the older button indicator"""
    db = SessionLocal()

    pivot = (
        db.query(EventMessage.pinned, EventMessage.created_at, EventMessage.uuid)
        .filter_by(uuid=before_id)
        .first()
    )
    if not pivot:
        db.close()
        return Response("", 204)  # nothing to add

    pin, ca, uid = pivot

    # Build a stable rank for 'pinned' (DB-agnostic ordering)
    pin_rank = case((EventMessage.pinned.is_(True), 1), else_=0)
    pivot_rank = 1 if pin else 0

    has_more = (
        db.query(EventMessage.uuid)
        .filter_by(event_id=code)
        .filter(
            or_(
                pin_rank < pivot_rank,
                and_(
                    pin_rank == pivot_rank,
                    or_(
                        EventMessage.created_at < ca,
                        and_(
                            EventMessage.created_at == ca,
                            EventMessage.uuid < uid,
                        ),
                    ),
                ),
            )
        )
        .limit(1)
        .first()
        is not None
    )

    db.close()
    if not has_more:
        return Response("", 204)  # no button

    # Return just the button HTML
    return jinja(
        request,
        "_older_button.html",
        {
            "event_code": code,
            "before_id": before_id,
            "limit": limit,
        },
    )


@router.post("/message/{uuid}/pin/")
def toggle_pin(request: air.Request, uuid: str, db: Session = Depends(get_db)):
    message = db.get(EventMessage, uuid)
    if message is None:
        raise ValueError(f"No EventMessage found for uuid={uuid}")
    message.pinned = not message.pinned
    db.add(message)
    db.commit()

    return Response("", 200)
