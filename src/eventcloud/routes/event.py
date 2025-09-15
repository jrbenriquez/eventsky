import asyncio
from datetime import datetime
from datetime import timezone
from uuid import uuid4

import air
from air.responses import JSONResponse
from air.responses import RedirectResponse
from air.responses import Response
from fastapi import Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import and_
from sqlalchemy import desc
from sqlalchemy import or_
from sqlalchemy.orm import selectinload

from eventcloud.app import app
from eventcloud.auth.deps import current_user
from eventcloud.auth.models import User
from eventcloud.db import SessionLocal
from eventcloud.event_broker import broker
from eventcloud.models import Event
from eventcloud.models import EventMessage
from eventcloud.models import EventMessageImage
from eventcloud.r2 import generate_presigned_upload_url
from eventcloud.r2 import get_signed_url_for_key
from eventcloud.schemas import EventCreate
from eventcloud.schemas import EventMessageCreate
from eventcloud.schemas import EventMessageImageCreate
from eventcloud.settings import settings
from eventcloud.utils import jinja


@app.get(
    "/events/new/",
)
def event_form(request: air.Request, user: User = Depends(current_user)):
    return jinja(request, "event_form.html")


@app.get("/events/{code}/")
def event_wall(request: air.Request, code: str):
    db = SessionLocal()
    event = db.query(Event).filter_by(code=code).first()
    messages = (
        db.query(EventMessage)
        .filter_by(event_id=code)
        .options(selectinload(EventMessage.images))
        .order_by(desc(EventMessage.created_at))
        .limit(10)
        .all()
    )

    db.close()

    if not event:
        return Response("Event not found", 400)

    return jinja(
        request,
        "event_wall.html",
        {
            "event": event,
            "messages": messages,
            "event_url": f"{settings.host}/events/{event.code}",
        },
    )


@app.post("/events/")
async def create_event(request: air.Request, user: User = Depends(current_user)):
    create_data: dict[str, str] = dict(await request.form())
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
    return RedirectResponse(url=f"/event/{data.code}", status_code=302)


@app.get("/events/")
def list_events(request: air.Request, user: User = Depends(current_user)):
    db = SessionLocal()
    events = db.query(Event).all()

    return jinja(request, "event_list.html", {"events": events})


@app.get("/event/{code}/messages")
def get_messages(request: air.Request, code: str, before_id: str | None = None, limit: int = 10):
    db = SessionLocal()

    q = db.query(EventMessage).filter_by(event_id=code).options(selectinload(EventMessage.images))

    if before_id:
        # Use (created_at, uuid) as a stable cursor
        pivot = (
            db.query(EventMessage.created_at, EventMessage.uuid).filter_by(uuid=before_id).first()
        )
        if pivot:
            ca, uid = pivot
            q = q.filter(
                or_(
                    EventMessage.created_at < ca,
                    and_(EventMessage.created_at == ca, EventMessage.uuid < uid),
                )
            )

    # Grab the next page newest->oldest, then flip to oldest->newest for display
    rows = q.order_by(EventMessage.created_at.desc(), EventMessage.uuid.desc()).limit(limit).all()
    # Oldest in this chunk becomes the next 'before_id'
    next_before_id = rows[0].uuid if rows else None

    db.close()

    return jinja(
        request,
        "_messages_load_chunk.html",
        {
            "messages": rows,
            "event_code": code,
            "next_before_id": next_before_id,
        },
    )


@app.post("/message/{event_code}/")
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
            data = EventMessageImageCreate(image_key=key)
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


@app.post("/r2/presign-upload")
async def get_presigned_upload_url(request: air.Request):
    form_data = await request.json()
    extension = form_data.get("extension")
    content_type = str(form_data.get("content_type"))

    file_id = str(uuid4())
    key = f"uploads/{file_id}.{extension}"

    presigned_url = generate_presigned_upload_url(key=key, content_type=content_type)
    return JSONResponse(
        {
            "upload_url": presigned_url,
            "key": key,
        }
    )


@app.get("/messageimage/")
def render_image(request: air.Request, key: str):
    url = get_signed_url_for_key(key)

    return jinja(request, "_message_image.html", {"url": url})


@app.get("/messageimagepreview/")
def render_image_preview(request: air.Request, key: str):
    url = get_signed_url_for_key(key)

    return jinja(request, "_message_image_preview.html", {"url": url})


@app.get("/event/{code}/stream")
async def event_stream(request: air.Request, code: str):
    queue = await broker.connect(code)

    async def generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield data
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            await broker.disconnect(code, queue)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
        },
    )


@app.get("/event/{code}/check_older/")
def check_older_message(request: air.Request, code: str, before_id: str, limit: int = 10):
    """Checks for older messages and if yes returns the older button indicator"""
    db = SessionLocal()

    pivot = db.query(EventMessage.created_at, EventMessage.uuid).filter_by(uuid=before_id).first()
    if not pivot:
        db.close()
        return Response("", 204)  # nothing to add

    ca, uid = pivot
    has_more = (
        db.query(EventMessage.uuid)
        .filter_by(event_id=code)
        .filter(
            or_(
                EventMessage.created_at < ca,
                and_(EventMessage.created_at == ca, EventMessage.uuid < uid),
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
