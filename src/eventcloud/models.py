from datetime import datetime
from datetime import timezone
from uuid import uuid4

from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import relationship

from eventcloud.db import Base
from eventcloud.settings import settings


class Event(Base):
    __tablename__ = "events"

    uuid = Column(
        String, primary_key=True, default=lambda: str(uuid4()), index=True, nullable=True
    )
    code = Column(String, index=True, unique=True, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def get_event_url(self):
        return f"{settings.host}/events/{self.code}"


class EventMessage(Base):
    __tablename__ = "eventmessages"

    uuid = Column(String, primary_key=True, default=lambda: str(uuid4()), index=True)
    event_id = Column(
        String, ForeignKey("events.code", name="fk_eventmessages_event"), nullable=False
    )
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
