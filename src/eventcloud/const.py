from sqlalchemy import case

from eventcloud.models import EventMessage

pin_rank = case((EventMessage.pinned.is_(True), 1), else_=0)
