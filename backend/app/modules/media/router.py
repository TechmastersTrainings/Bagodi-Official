from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from app.core.storage import storage

router = APIRouter(prefix="/media", tags=["Media Storage"])


@router.post("/upload")
async def upload_media_file(
    file: UploadFile = File(...),
    folder: str = Form("products"),
):
    """
    Directly upload an asset (image/document) to Cloudflare R2 bucket.
    Returns the public CDN / custom domain URL.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valid file with filename required",
        )

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

    try:
        public_url = storage.upload_file(
            file_obj=file.file,
            filename=file.filename,
            content_type=content_type,
            folder=folder,
        )
        return {
            "url": public_url,
            "filename": file.filename,
            "content_type": content_type,
            "folder": folder,
            "storage_provider": "cloudflare-r2",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file to Cloudflare R2: {str(e)}",
        )
