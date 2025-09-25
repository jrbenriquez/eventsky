from collections.abc import Mapping
from datetime import datetime
from datetime import timezone
from typing import Optional

import air
from air.responses import RedirectResponse
from air.responses import Response
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from sqlalchemy.orm import selectinload
from sqlalchemy.orm import Session

from eventcloud.auth.deps import current_user
from eventcloud.auth.models import User
from eventcloud.auth.utils import get_session_user_id
from eventcloud.db import get_db
from eventcloud.db import SessionLocal
from eventcloud.event_broker import broker
from eventcloud.models import Event
from eventcloud.models import EventMessage
from eventcloud.models import EventMessageImage
from eventcloud.schemas import EventCreate
from eventcloud.schemas import EventMessageCreate
from eventcloud.schemas import EventMessageImageCreate
from eventcloud.schemas import EventUpdate
from eventcloud.utils import get_csrf_token
from eventcloud.utils import jinja

router = APIRouter(tags=["events"])


@router.get("/events/new/")
def event_form(request: air.Request):
    csrf_token = get_csrf_token(request)
    return jinja(request, "event_form.html", {"csrf_token": csrf_token})


@router.get("/manage/events/{uuid}")
def manage_event_form(
    request: air.Request,
    uuid: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    csrf_token = get_csrf_token(request)
    event = db.query(Event).filter_by(uuid=uuid).first()

    messages = EventMessage.get_messages_for_event(db, event.code, limit=1, all=True)

    return jinja(
        request,
        "manage_event.html",
        {
            "event": event,
            "csrf_token": csrf_token,
            "messages": messages,
            "user": user,
        },
    )


@router.post("/manage/events/{uuid}")
async def update_event(request: air.Request, uuid: str, db: Session = Depends(get_db)):
    form_data: Mapping[str, str] = {k: str(v) for k, v in (await request.form()).items()}
    csrf_token = form_data.pop("csrf_token", None)
    session_token = request.session.get("csrf_token")
    if not session_token or csrf_token != session_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF failed")

    serialized_data = EventUpdate(**form_data)
    event = db.query(Event).filter_by(uuid=uuid).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    for field, value in serialized_data.dict(exclude_unset=True).items():
        setattr(event, field, value)

    db.add(event)
    db.commit()
    db.refresh(event)

    return RedirectResponse(f"/manage/events/{event.uuid}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/events/{code}/")
def event_wall(request: air.Request, code: str, db: Session = Depends(get_db)):
    event = db.query(Event).filter_by(code=code).first()
    messages = EventMessage.get_messages_for_event(db, event_code=code, pinned=False)
    pinned_messages = EventMessage.get_messages_for_event(db, event_code=code, pinned=True)
    uid = get_session_user_id(request)
    if uid:
        user: Optional[User] = db.query(User).filter_by(id=uid).first()
    else:
        user = None

    if not event:
        return Response("Event not found", 400)

    return jinja(
        request,
        "event_wall.html",
        {
            "event": event,
            "messages": messages,
            "pinned_messages": pinned_messages,
            "event_url": event.get_event_url(),
            "user": user,
        },
    )


@router.post("/events/")
async def create_event(request: air.Request, user: User = Depends(current_user)):
    create_data: Mapping[str, str] = {k: str(v) for k, v in (await request.form()).items()}
    data = EventCreate(**create_data)
    created_at = datetime.now(timezone.utc)

    db = SessionLocal()
    event = Event(
        code=data.code,
        title=data.title,
        description=data.description,
        created_at=created_at,
    )
    db.add(event)
    db.commit()
    db.close()
    return RedirectResponse(url=f"/events/{data.code}", status_code=302)


@router.get("/events/")
def list_events(
    request: air.Request, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    events = db.query(Event).all()

    return jinja(request, "event_list.html", {"events": events})


@router.get("/events/{code}/messages")
def get_messages(
    request: air.Request,
    code: str,
    before_id: str | None = None,
    limit: int = 10,
    db: Session = Depends(get_db),
):
    messages = EventMessage.get_messages_for_event(db, code, limit, before_id)

    # Oldest in this chunk becomes the next 'before_id'
    next_before_id = messages[0].uuid if messages else None

    return jinja(
        request,
        "_messages_load_chunk.html",
        {
            "messages": messages,
            "event_code": code,
            "next_before_id": next_before_id,
        },
    )


@router.post("/message/{event_code}/")
async def send_message(request: air.Request, event_code: str):
    form_data = await request.form()
    message_data = {
        "text": str(form_data.get("text")),
        "sender_name": str(form_data.get("sender_name")),
    }

    image_keys = form_data.getlist("image_keys")

    data = EventMessageCreate(**message_data)

    db = SessionLocal()
    message = EventMessage(event_id=event_code, **data.model_dump())
    db.add(message)
    db.commit()
    db.refresh(message)

    if image_keys and isinstance(image_keys, list):
        for key in image_keys:
            data = EventMessageImageCreate(image_key=str(key))
            image = EventMessageImage(image_key=data.image_key, event_message_id=message.uuid)
            db.add(image)

    db.commit()
    db.refresh(message)
    message = db.query(EventMessage).options(selectinload(EventMessage.images)).get(message.uuid)

    html = jinja(request, "_messages.html", {"messages": [message]}).body.decode()
    payload = '<span data-autoscroll="1" style="display:none"></span>' + html
    await broker.publish(event_code, payload)

    db.close()
    return Response("OK", 200)
