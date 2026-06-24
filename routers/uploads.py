from __future__ import annotations

import os

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from auth import get_current_user
from models import User
from services.storage import ALLOWED_IMAGE_TYPES, upload_image


router = APIRouter(prefix="/uploads", tags=["Uploads"])


class ImageUploadResponse(BaseModel):
    file_url: str
    storage_path: str
    content_type: str
    size: int


def _max_upload_bytes() -> int:
    max_mb = int(os.getenv("MAX_IMAGE_UPLOAD_MB", "6"))
    return max_mb * 1024 * 1024


def _has_valid_signature(content: bytes, content_type: str) -> bool:
    if content_type == "image/jpeg":
        return content.startswith(b"\xff\xd8\xff")
    if content_type == "image/png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/gif":
        return content.startswith((b"GIF87a", b"GIF89a"))
    if content_type == "image/webp":
        return (
            len(content) >= 12
            and content.startswith(b"RIFF")
            and content[8:12] == b"WEBP"
        )
    return False


@router.post(
    "/complaint-images",
    response_model=ImageUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="민원 이미지 Supabase Storage 업로드",
)
async def upload_complaint_image(
    file: UploadFile = File(..., description="민원에 첨부할 이미지"),
    current_user: User = Depends(get_current_user),
) -> ImageUploadResponse:
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="JPEG, PNG, WebP, GIF 이미지만 업로드할 수 있습니다.",
        )

    max_bytes = _max_upload_bytes()
    content = await file.read(max_bytes + 1)
    await file.close()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="빈 파일은 업로드할 수 없습니다.",
        )
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"이미지 크기는 최대 {max_bytes // (1024 * 1024)}MB입니다.",
        )
    if not _has_valid_signature(content, content_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="파일 내용과 이미지 형식이 일치하지 않습니다.",
        )

    try:
        result = upload_image(
            user_id=current_user.id,
            content=content,
            content_type=content_type,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Supabase Storage 이미지 업로드에 실패했습니다.",
        )

    return ImageUploadResponse(
        file_url=result.public_url,
        storage_path=result.path,
        content_type=content_type,
        size=len(content),
    )
