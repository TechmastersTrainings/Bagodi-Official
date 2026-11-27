import io
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.core.storage import storage

router = APIRouter(prefix="/media", tags=["Media Storage"])

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_FOLDERS = {"products", "boutiques", "kyc", "branding", "banners"}


@router.post("/upload")
async def upload_media_file(
    file: Annotated[UploadFile, File(...)],
    folder: Annotated[str, Form()] = "products",
):
    """
    Directly upload an asset (image/document) to Cloudflare R2 bucket.
    Enforces file size limit (10MB), folder whitelisting, and strict MIME type validation.
    Returns the public CDN / custom domain URL.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valid file with filename required",
        )

    # Prevent directory traversal attacks
    target_folder = folder.strip().lower()
    if target_folder not in ALLOWED_FOLDERS:
        target_folder = "products"

    # Validate image or document mime types
    allowed_types = [
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/avif",
        "image/gif",
        "application/pdf",
    ]
    content_type = file.content_type or "image/jpeg"
    if content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type {content_type} not supported. Allowed: {allowed_types}",
        )

    # Read and enforce max file size
    contents = await file.read(MAX_FILE_SIZE_BYTES + 1)
    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size exceeds maximum permitted limit of 10MB.",
        )

    try:
        public_url = storage.upload_file(
            file_obj=io.BytesIO(contents),
            filename=file.filename,
            content_type=content_type,
            folder=target_folder,
        )
        return {
            "url": public_url,
            "filename": file.filename,
            "content_type": content_type,
            "folder": target_folder,
            "size_bytes": len(contents),
            "storage_provider": "cloudflare-r2",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file to Cloudflare R2: {e!s}",
        ) from e
