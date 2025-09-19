# schemas.py
from datetime import datetime

from pydantic import BaseModel
from pydantic import ConfigDict


class EventBase(BaseModel):
    title: str
    description: str
    code: str


class EventCreate(EventBase): ...


class EventUpdate(EventBase): ...


class EventRead(BaseModel):
    code: str
    title: str
    description: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EventMessageImageRead(BaseModel):
    uuid: str
    image_key: str
    sender_name: str
    created_at: datetime

    class Config:
        from_attributes = True


class EventMessageCreate(BaseModel):
    text: str
    sender_name: str


class EventMessageImageCreate(BaseModel):
    image_key: str
