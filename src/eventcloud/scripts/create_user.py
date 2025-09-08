#!/usr/bin/env python3
import sys
import getpass
from typing import Optional

from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, ValidationError

# --- Import your app's DB and User model ---
# Adjust these imports to match your project structure.
from eventcloud.db import SessionLocal
from eventcloud.auth.models import User                # Base if you want optional auto-create


pwd_ctx = CryptContext(schemes=["argon2"], deprecated="auto")


class Inputs(BaseModel):
    email: EmailStr
    username: Optional[str] = None


def prompt_nonempty(prompt: str) -> str:
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("This field is required.")


def prompt_password() -> str:
    while True:
        p1 = getpass.getpass("Password: ")
        if not p1:
            print("Password cannot be empty.")
            continue
        p2 = getpass.getpass("Confirm password: ")
        if p1 != p2:
            print("Passwords do not match. Try again.\n")
            continue
        return p1


def hash_password(raw: str) -> str:
    return pwd_ctx.hash(raw)


def main():
    print("== Create User ==")
    # Optional: uncomment to ensure tables exist (or rely on Alembic/migrations)
    # Base.metadata.create_all(bind=engine)

    email_raw = prompt_nonempty("Email: ").lower()
    username = input("Username (optional, press Enter to skip): ").strip() or None

    # Validate email (and optional username) via Pydantic
    try:
        data = Inputs(email=email_raw, username=username)
    except ValidationError as e:
        print("Input error:", e)
        sys.exit(1)

    password = prompt_password()

    # Write to DB
    db = SessionLocal()
    try:
        # Uniqueness checks
        existing_email = db.query(User).filter(User.email.ilike(data.email)).first()
        if existing_email:
            print("Error: Email is already registered.")
            sys.exit(2)

        if data.username:
            existing_user = db.query(User).filter(User.username == data.username).first()
            if existing_user:
                print("Error: Username is already taken.")
                sys.exit(3)

        user = User(
            email=data.email,
            username=data.username,
            password_hash=hash_password(password),
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"Success: created user id={user.id}, email={user.email}, username={user.username or '(none)'}")
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(130)
    except Exception as e:
        db.rollback()
        print("Unexpected error:", repr(e))
        sys.exit(10)
    finally:
        db.close()


if __name__ == "__main__":
    main()

