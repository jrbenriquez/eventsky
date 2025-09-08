from uuid import uuid4
from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from datetime import datetime, timezone
from eventcloud.db import Base
from sqlalchemy.orm import relationship

class Event(Base):
    __tablename__ = "events"

    code = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class EventMessage(Base):
    __tablename__ = "eventmessages"

    uuid = Column(String, primary_key=True, default=lambda: str(uuid4()), index=True)
    event_id = Column(String, ForeignKey("events.code", name="fk_eventmessages_event"), nullable=False)
    text = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    sender_name = Column(String, nullable=True)

    images = relationship("EventMessageImage", back_populates="event_message")

class EventMessageImage(Base):
    __tablename__ = "eventmessageimages"

    uuid = Column(String, primary_key=True, default=lambda: str(uuid4()), index=True)
    event_message_id = Column(String, ForeignKey("eventmessages.uuid"), nullable=False)
    image_key = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    event_message = relationship("EventMessage", back_populates="images")
