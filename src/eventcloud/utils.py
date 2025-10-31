from pathlib import Path
import secrets

import air
from fastapi import Request

from eventcloud.db import SessionLocal
from eventcloud.models import EventMessageImage
from eventcloud.r2 import get_signed_url_for_key

BASE_DIR = Path(__file__).resolve().parent
jinja = air.JinjaRenderer(directory=str(BASE_DIR / "templates"))


def get_csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return token


def get_blurred_url_for_image_key(image_key: str, expires_in: int = 3600):
    """Checks if there is a blurred key for the image if not it tries
    to generate a blurred image and uploads it and saves the key in the db
    and returns it
    """
    db = SessionLocal()
    try:
        image = db.query(EventMessageImage).filter_by(image_key=image_key).first()

        if not image:
            raise ValueError(f"Image not found for key: {image_key}")

        if ".mp4" in image.image_key:
            # Generic image if video
            image_key = "blurred/pexels-splitshire-1526.jpg"
        elif key := image.blurred_image_key:
            image_key = key
        else:
            # Generic image if none
            image_key = "blurred/pexels-splitshire-1526.jpg"

        return get_signed_url_for_key(image_key, expires_in)

    except Exception as e:
        db.rollback()
        raise RuntimeError(f"Failed to get/generate blurred image: {e}")
    finally:
        db.close()
