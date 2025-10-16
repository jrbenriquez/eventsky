from datetime import datetime
from datetime import timezone
from uuid import uuid4

from sqlalchemy import and_
from sqlalchemy import Boolean
from sqlalchemy import case
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import or_
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import column_property
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy.orm import selectinload

from eventcloud.db import Base
from eventcloud.settings import settings


class Event(Base):
    __tablename__ = "events"

    uuid = Column(String, default=lambda: str(uuid4()), index=True, nullable=True)
    code = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    posting_messages_disabled: Mapped[bool | None] = mapped_column(
        Boolean, default=False, nullable=True
    )

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
    pinned: Mapped[bool | None] = mapped_column(Boolean, default=False, nullable=True)

    images = relationship("EventMessageImage", back_populates="event_message")
    pin_rank = column_property(case((pinned.is_(True), 1), else_=0))

    @staticmethod
    def get_messages_for_event(db, event_code, limit=10, before_id=None, pinned=False, all=False):
        if pinned:
            all = False

        if all and not pinned:
            pinned = True
        if before_id:
            q = (
                db.query(EventMessage)
                .filter_by(event_id=event_code, pinned=pinned)
                .options(selectinload(EventMessage.images))
            )

            # Use (created_at, uuid) as a stable cursor
            pivot = (
                db.query(EventMessage.created_at, EventMessage.uuid)
                .filter_by(uuid=before_id, pinned=pinned)
                .first()
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
            messages = (
                q.order_by(
                    EventMessage.pin_rank.desc(),
                    EventMessage.created_at.desc(),
                    EventMessage.uuid.desc(),
                )
                .limit(limit)
                .all()
            )
        else:
            messages = (
                db.query(EventMessage)
                .filter_by(event_id=event_code, pinned=pinned)
                .options(selectinload(EventMessage.images))
                .order_by(EventMessage.pin_rank.desc(), EventMessage.created_at.desc())
                .limit(limit)
                .all()
            )
        return messages


class EventMessageImage(Base):
    __tablename__ = "eventmessageimages"

    uuid = Column(String, primary_key=True, default=lambda: str(uuid4()), index=True)
    event_message_id = Column(String, ForeignKey("eventmessages.uuid"), nullable=False)
    image_key = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    event_message = relationship("EventMessage", back_populates="images")
