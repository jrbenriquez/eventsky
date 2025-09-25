# scripts/init_db.py
from eventcloud.db import Base
from eventcloud.db import engine

Base.metadata.create_all(bind=engine)

print("Database initialized")
