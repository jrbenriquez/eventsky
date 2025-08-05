# scripts/init_db.py
from eventcloud.db import Base, engine
from eventcloud.models import Event 

Base.metadata.create_all(bind=engine)

print("Database initialized")
