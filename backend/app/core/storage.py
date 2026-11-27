import base64
import io
import logging
import uuid
from typing import BinaryIO

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

    def upload_base64_data_url(self, data_url: str, folder: str = "products") -> str:
        """
        If given a base64 data URL (e.g. data:image/jpeg;base64,...), decodes it
        and uploads directly to Cloudflare R2 bucket, returning the public CDN URL.
        If already an HTTP/HTTPS URL, returns it as-is without re-uploading.
        Prevents raw image binary/base64 strings from bloating database tables.
        """
        if not data_url or not isinstance(data_url, str):
            return ""

        trimmed = data_url.strip()
        if not trimmed.startswith("data:"):
            return trimmed

        try:
            if ";base64," in trimmed:
                header, encoded = trimmed.split(";base64,", 1)
                content_type = header.replace("data:", "").strip()
            else:
                header, encoded = trimmed.split(",", 1)
                content_type = "image/jpeg"

            ext_map = {
                "image/jpeg": "jpg",
                "image/jpg": "jpg",
                "image/png": "png",
                "image/webp": "webp",
                "image/gif": "gif",
                "image/avif": "avif",
                "application/pdf": "pdf",
            }
            ext = ext_map.get(content_type, "jpg")
            decoded_bytes = base64.b64decode(encoded)

            return self.upload_file(
                file_obj=io.BytesIO(decoded_bytes),
                filename=f"product-{uuid.uuid4().hex[:8]}.{ext}",
                content_type=content_type,
                folder=folder,
            )
        except Exception as e:
            logger.error(f"Failed to process base64 data URL to Cloudflare R2: {e}")
            return trimmed

    def delete_file(self, object_key: str) -> bool:
        """
        Deletes an object key from the Cloudflare R2 bucket.
        """
        client = self._get_client()
        if client and self.settings.r2_bucket_name and object_key:
            try:
                client.delete_object(
                    Bucket=self.settings.r2_bucket_name,
                    Key=object_key.lstrip("/"),
                )
                logger.info(f"Successfully deleted {object_key} from Cloudflare R2.")
                return True
            except Exception as e:
                logger.error(f"Failed to delete {object_key} from Cloudflare R2: {e}")
                return False
        return False

    def delete_by_url(self, file_url: str) -> bool:
        """
        Given a full CDN or R2 URL, extracts the object key and deletes it from Cloudflare R2.
        e.g. 'https://assets.bagodi.in/products/product-1234.jpg' -> 'products/product-1234.jpg'
        """
        if not file_url or not isinstance(file_url, str):
            return False

        try:
            from urllib.parse import urlparse
            clean_url = file_url.split("?")[0].strip()
            parsed = urlparse(clean_url)
            path = parsed.path.lstrip("/")

            # If path starts with bucket_name, strip it
            if self.settings.r2_bucket_name and path.startswith(f"{self.settings.r2_bucket_name}/"):
                path = path[len(self.settings.r2_bucket_name) + 1:]

            if path:
                return self.delete_file(path)
        except Exception as e:
            logger.error(f"Error parsing URL for R2 deletion ({file_url}): {e}")
        return False


storage = CloudflareR2Storage()
