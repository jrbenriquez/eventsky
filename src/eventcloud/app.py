import os
from datetime import datetime, timezone
from typing import Union
from uuid import uuid4

import air
from air.responses import JSONResponse, RedirectResponse, Response
from sqlalchemy import desc
from sqlalchemy.orm import selectinload

from eventcloud.db import SessionLocal
from eventcloud.models import Event, EventMessage, EventMessageImage
from eventcloud.r2 import (generate_presigned_upload_url,
                           get_signed_url_for_key, r2_client)
from eventcloud.schemas import (EventCreate, EventMessageCreate,
                                EventMessageImageCreate)
from eventcloud.settings import settings

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


app = air.Air()

jinja = air.JinjaRenderer(directory="templates")


@app.get("/")
def index(request: air.Request):
    return jinja(request, name="index.html")


@app.get("/event/new/")
def event_form(request: air.Request):
    return jinja(request, "event_form.html")


@app.get("/event/{code}/")
def event_wall(request: air.Request, code: str):
    db = SessionLocal()
    event = db.query(Event).filter_by(code=code).first()
    messages = (
        db.query(EventMessage)
        .filter_by(event_id=code)
        .options(selectinload(EventMessage.images))
        .order_by(desc(EventMessage.created_at))
        .all()
    )

    db.close()

    if not event:
        return Response("Event not found", 400)

    return jinja(request, "event_wall.html", {"event": event, "messages": messages})


@app.post("/event/")
async def create_event(request: air.Request):
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


@app.get("/event/")
def list_events(request: air.Request):
    db = SessionLocal()
    events = db.query(Event).all()

    return jinja(request, "event_list.html", {"events": events})


@app.get("/event/{code}/messages")
def get_messages(request: air.Request, code: str):
    db = SessionLocal()
    messages = (
        db.query(EventMessage)
        .filter_by(event_id=code)
        .options(selectinload(EventMessage.images))
        .order_by(desc(EventMessage.created_at))
        .all()
    )
    db.close()

    return jinja(request, "_messages.html", {"messages": messages})

@app.post("/message/{event_code}/")
async def send_message(request: air.Request, event_code: str):
    form_data = await request.form()
    message_data = {
        "text": str(form_data.get("text")),
    }

    image_keys = form_data.getlist("image_keys")

    data = EventMessageCreate(**message_data)

    db = SessionLocal()
    message = EventMessage(event_id=event_code, text=data.text)
    db.add(message)
    db.commit()
    db.refresh(message)

    if image_keys and isinstance(image_keys, list):
        for key in image_keys:
            data = EventMessageImageCreate(image_key=key)
            image = EventMessageImage(image_key=data.image_key, event_message_id=message.uuid)
            db.add(image)

    db.commit()
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
    return JSONResponse({
        "upload_url": presigned_url,
        "key": key,
    })

@app.get("/messageimage/")
def render_image(request: air.Request, key:str):
    url = get_signed_url_for_key(key)

    return jinja(request, "_message_image.html", {"url": url})

