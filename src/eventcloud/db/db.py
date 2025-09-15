from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

from eventcloud.settings import settings

connect_args = {}
if settings.database_url.startswith("sqlite"):
    # Needed for SQLite + multithreaded servers
    connect_args = {"check_same_thread": False}


engine = create_engine(settings.database_url, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db  # <-- Session is given to whoever depends on it
    finally:
        db.close()  # <-- Always closes the session


# How to use db helper
# @app.get("/users/")
# def read_users(db: Session = Depends(get_db)):
#     return db.query(User).all()
