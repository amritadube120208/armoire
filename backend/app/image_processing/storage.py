import os
from pathlib import Path
from typing import Optional
from app.core.config import settings

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    boto3 = None
    ClientError = Exception


class StorageService:
    """
    Object storage service implementing Backend.md §7:
      - Private buckets for original & enhanced images
      - Signed URLs for access (no public bucket exposure)
      - Pluggable backends: Local disk (for dev/testing) and S3/R2 (for production)
    """

    def __init__(self):
        self.backend = settings.STORAGE_BACKEND
        self.local_dir = Path(settings.STORAGE_LOCAL_DIR)

        if self.backend == "local":
            self.local_dir.mkdir(parents=True, exist_ok=True)
            self.s3_client = None
        else:
            if not boto3:
                raise ImportError("boto3 is required for S3/R2 storage backend")
            self.s3_client = boto3.client(
                "s3",
                endpoint_url=settings.S3_ENDPOINT_URL,
                aws_access_key_id=settings.S3_ACCESS_KEY_ID,
                aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
                region_name=settings.S3_REGION
            )

    async def save_file(
        self,
        key: str,
        data: bytes,
        content_type: str = "image/jpeg"
    ) -> str:
        """Saves file bytes and returns reference path/key."""
        if self.backend == "local":
            file_path = self.local_dir / key
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(data)
            return f"/storage/{key}"
        else:
            self.s3_client.put_object(
                Bucket=settings.S3_BUCKET_NAME,
                Key=key,
                Body=data,
                ContentType=content_type,
                ServerSideEncryption="AES256"
            )
            return key

    async def get_file(self, key: str) -> Optional[bytes]:
        """Retrieves raw file bytes."""
        if self.backend == "local":
            clean_key = key.replace("/storage/", "")
            file_path = self.local_dir / clean_key
            if not file_path.exists():
                return None
            with open(file_path, "rb") as f:
                return f.read()
        else:
            clean_key = key.replace("/storage/", "")
            try:
                response = self.s3_client.get_object(
                    Bucket=settings.S3_BUCKET_NAME,
                    Key=clean_key
                )
                return response["Body"].read()
            except ClientError:
                return None

    def get_signed_url(self, key: str, expires_in: int = 3600) -> str:
        """
        Generates short-lived signed URL for private access.
        """
        if self.backend == "local":
            # For local dev, returns the static media route
            if not key.startswith("/storage/"):
                return f"/storage/{key}"
            return key
        else:
            clean_key = key.replace("/storage/", "")
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.S3_BUCKET_NAME, "Key": clean_key},
                ExpiresIn=expires_in
            )
            return url

    async def delete_file(self, key: str) -> bool:
        """Deletes file from storage."""
        clean_key = key.replace("/storage/", "")
        if self.backend == "local":
            file_path = self.local_dir / clean_key
            if file_path.exists():
                file_path.unlink()
                return True
            return False
        else:
            try:
                self.s3_client.delete_object(
                    Bucket=settings.S3_BUCKET_NAME,
                    Key=clean_key
                )
                return True
            except ClientError:
                return False


storage = StorageService()
