# scripts/generate_blurred_images.py
import io
from uuid import uuid4

from PIL import Image
from PIL import ImageFilter

from eventcloud.db import SessionLocal
from eventcloud.models import EventMessageImage
from eventcloud.r2 import download_object_from_r2
from eventcloud.r2 import upload_to_r2


def generate_missing_blurred_images(batch_size: int = 10):
    """Generate blurred versions for images that don't have them yet"""
    db = SessionLocal()
    try:
        # Get images without blurred versions
        images = (
            db.query(EventMessageImage)
            .filter(EventMessageImage.blurred_image_key.is_(None))
            .limit(batch_size)
            .all()
        )
        print(f"Found {len(images)} images without blurred versions")
        for image in images:
            try:
                print(f"Processing {image.image_key}...")
                # Download original
                image_data = download_object_from_r2(image.image_key)
                # Blur
                img = Image.open(io.BytesIO(image_data))
                img_format = img.format or "JPEG"
                blurred_img = img.filter(ImageFilter.GaussianBlur(radius=20))
                # Save to bytes
                output = io.BytesIO()
                blurred_img.save(output, format=img_format)
                output.seek(0)
                # Generate key
                file_extension = (
                    image.image_key.split(".")[-1] if "." in image.image_key else "jpg"
                )
                blurred_key = f"blurred/{uuid4()}.{file_extension}"
                content_type = f"image/{img_format.lower()}"
                # Upload
                upload_to_r2(blurred_key, output.getvalue(), content_type)
                # Update DB
                image.blurred_image_key = blurred_key
                db.commit()
                print(f"Generated blurred version: {blurred_key}")
            except Exception as e:
                print(f"Failed to process {image.image_key}: {e}")
                db.rollback()
                image.blurred_image_key = "blurred/pexels-splitshire-1526.jpg"
                db.commit()
                continue
        print("Done!")
    finally:
        db.close()


generate_missing_blurred_images()

if __name__ == "__main__":
    generate_missing_blurred_images()
