from pathlib import Path

import boto3
from botocore.client import Config

from eventcloud.settings import settings

# Constants
R2_REGION = "auto"
TEST_FILE_PATH = "r2_test_upload.txt"
R2_TEST_KEY = "test-folder/r2_test_upload.txt"

# Create a dummy file to upload
Path(TEST_FILE_PATH).write_text("Hello from EventCloud!")

# Setup R2 client
session = boto3.session.Session()
r2_client = session.client(
    service_name="s3",
    region_name=R2_REGION,
    endpoint_url=settings.r2_s3_url,
    aws_access_key_id=settings.r2_access_key_id,
    aws_secret_access_key=settings.r2_secret_access_key,
    config=Config(signature_version="v4"),
)

# Upload the file
print(f"Uploading {TEST_FILE_PATH} to R2 bucket...")
r2_client.upload_file(TEST_FILE_PATH, settings.r2_bucket_name, R2_TEST_KEY)
print("✅ Upload complete!")

response = r2_client.get_object(Bucket=settings.r2_bucket_name, Key=R2_TEST_KEY)

# Read content
body = response["Body"].read().decode("utf-8")
print("File contents:", body)

response = r2_client.delete_object(Bucket=settings.r2_bucket_name, Key=R2_TEST_KEY)
print("Delete response:", response)
