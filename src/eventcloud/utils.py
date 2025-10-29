import io
from pathlib import Path
import secrets
from uuid import uuid4

import air
from fastapi import Request
from PIL import Image
from PIL import ImageFilter

from eventcloud.db import SessionLocal
from eventcloud.models import EventMessageImage
from eventcloud.r2 import download_object_from_r2
from eventcloud.r2 import get_signed_url_for_key
from eventcloud.r2 import upload_to_r2

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

        if key := image.blurred_image_key:
            image_key = key
        else:
            # Download the original image from R2
            image_data = download_object_from_r2(image_key)

            # Open and blur the image
            img = Image.open(io.BytesIO(image_data))
            # Preserve the original format
            img_format = img.format or "JPEG"
            blurred_img = img.filter(ImageFilter.GaussianBlur(radius=20))

            # Save blurred image to bytes
            output = io.BytesIO()
            blurred_img.save(output, format=img_format)
            output.seek(0)

            # Generate new key for blurred image
            file_extension = image_key.split(".")[-1] if "." in image_key else "jpg"
            blurred_key = f"blurred/{uuid4()}.{file_extension}"
            content_type = f"image/{img_format.lower()}" if img_format else "image/jpeg"

            # Upload blurred image to R2
            upload_to_r2(blurred_key, output.getvalue(), content_type)
            # Save blurred key to database
            image.blurred_image_key = blurred_key
            db.commit()

            image_key = blurred_key

        return get_signed_url_for_key(image_key, expires_in)

    except Exception as e:
        db.rollback()
        raise RuntimeError(f"Failed to get/generate blurred image: {e}")
    finally:
        db.close()
