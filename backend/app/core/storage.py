import uuid
import logging
from typing import Optional, BinaryIO
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class CloudflareR2Storage:
    def __init__(self):
        self.settings = get_settings()
        self._client = None

    def _get_client(self):
        if self._client is None and self.settings.r2_account_id and self.settings.r2_access_key_id:
            try:
                import boto3
                from botocore.config import Config

                self._client = boto3.client(
                    "s3",
                    endpoint_url=self.settings.r2_endpoint_url,
                    aws_access_key_id=self.settings.r2_access_key_id,
                    aws_secret_access_key=self.settings.r2_secret_access_key,
                    config=Config(signature_version="s3v4"),
                    region_name="auto",
                )
            except Exception as e:
                logger.error(f"Failed to initialize Cloudflare R2 boto3 client: {e}")
                self._client = None
        return self._client

    def upload_file(
        self,
        file_obj: BinaryIO,
        filename: str,
        content_type: str = "image/jpeg",
        folder: str = "products",
    ) -> str:
        """
        Uploads a file object to Cloudflare R2 bucket and returns the public CDN URL.
        """
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
        object_key = f"{folder}/{uuid.uuid4().hex}.{extension}"

        client = self._get_client()
        if client and self.settings.r2_bucket_name:
            try:
                client.upload_fileobj(
                    file_obj,
                    self.settings.r2_bucket_name,
                    object_key,
                    ExtraArgs={"ContentType": content_type},
                )
                if self.settings.r2_public_domain:
                    domain = self.settings.r2_public_domain.rstrip("/")
                    return f"{domain}/{object_key}"
                return f"{self.settings.r2_endpoint_url}/{self.settings.r2_bucket_name}/{object_key}"
            except Exception as e:
                logger.error(f"Cloudflare R2 upload error: {e}")
                raise

        # Fallback for dev / unconfigured environments
        logger.warning("Cloudflare R2 storage credentials not configured, returning placeholder URL.")
        return f"https://assets.bagodi.in/{object_key}"


storage = CloudflareR2Storage()
