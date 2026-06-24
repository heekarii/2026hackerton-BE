from __future__ import annotations

import os
import uuid
from dataclasses import dataclass


ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


@dataclass(frozen=True)
class StorageUploadResult:
    path: str
    public_url: str


def _get_storage_settings() -> tuple[str, str, str]:
    supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    bucket = os.getenv("SUPABASE_STORAGE_BUCKET", "complaint-images")

    if not supabase_url or not service_role_key:
        raise RuntimeError(
            "SUPABASE_URL과 SUPABASE_SERVICE_ROLE_KEY 환경변수가 필요합니다."
        )
    return supabase_url, service_role_key, bucket


def build_image_path(user_id: int, content_type: str) -> str:
    extension = ALLOWED_IMAGE_TYPES[content_type]
    return f"complaints/{user_id}/{uuid.uuid4().hex}{extension}"


def upload_image(
    *,
    user_id: int,
    content: bytes,
    content_type: str,
) -> StorageUploadResult:
    from supabase import create_client

    supabase_url, service_role_key, bucket = _get_storage_settings()
    path = build_image_path(user_id, content_type)
    client = create_client(supabase_url, service_role_key)
    client.storage.from_(bucket).upload(
        path=path,
        file=content,
        file_options={
            "content-type": content_type,
            "cache-control": "3600",
            "upsert": "false",
        },
    )
    public_url = client.storage.from_(bucket).get_public_url(path)
    return StorageUploadResult(path=path, public_url=public_url)
