# scripts/init_db.py
from eventcloud.db import Base, engine

Base.metadata.create_all(bind=engine)

print("Database initialized")
