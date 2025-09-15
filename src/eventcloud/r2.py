import boto3
from botocore.client import Config

from eventcloud.settings import settings

R2_REGION = "auto"

session = boto3.session.Session()

r2_client = session.client(
    service_name="s3",
    region_name=R2_REGION,
    endpoint_url=settings.r2_s3_url,
    aws_access_key_id=settings.r2_access_key_id,
    aws_secret_access_key=settings.r2_secret_access_key,
    config=Config(signature_version="v4", s3={"addressing_style": "path"}),
)


def generate_presigned_upload_url(
    key: str,
    expires_in: int = 3600,
    content_type: str = "application/octet-stream",
    http_method: str = "PUT",
) -> str:
    return r2_client.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": settings.r2_bucket_name,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=expires_in,
        HttpMethod=http_method,
    )


def get_signed_url_for_key(image_key: str, expires_in: int = 3600):
    try:
        url = r2_client.generate_presigned_url(
            ClientMethod="get_object",
            Params={
                "Bucket": settings.r2_bucket_name,
                "Key": image_key,
            },
            ExpiresIn=expires_in,  # e.g., 1 hour = 3600 seconds
            HttpMethod="GET",
        )
        return url
    except Exception as e:
        raise RuntimeError(f"Failed to generate presigned URL: {e}")
