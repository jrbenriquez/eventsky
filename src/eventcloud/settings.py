from typing import Annotated
from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # === General ===
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")

    # === Database ===
    database_url: str = Field(default=..., validation_alias="DATABASE_URL")

    # === R2 / S3 ===
    r2_access_key_id: str = Field(default=..., validation_alias="CLOUDFLARE_R2_ACCESS_KEY_ID")
    r2_secret_access_key: str = Field(default=..., validation_alias="CLOUDFLARE_R2_SECRET_ACCESS_KEY")
    r2_bucket_name: str = Field(default=..., validation_alias="CLOUDFLARE_R2_BUCKET_NAME")
    r2_s3_url: str = Field(default=..., validation_alias="CLOUDFLARE_S3_URL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
