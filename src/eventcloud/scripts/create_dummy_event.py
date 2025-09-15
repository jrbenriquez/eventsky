from datetime import datetime
from datetime import timezone

from eventcloud.db import SessionLocal
from eventcloud.models import Event

db = SessionLocal()

event = Event(
    code="demo123",
    title="Demo Event",
    description="This is a sample event created manually.",
    created_at=datetime.now(timezone.utc),
)

db.add(event)
db.commit()
db.close()

print("Dummy event created with code: demo123")
