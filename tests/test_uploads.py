from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import get_current_user
from models import User, UserRole
from routers import uploads
from services.storage import StorageUploadResult, build_image_path


app = FastAPI()
app.include_router(uploads.router)
app.dependency_overrides[get_current_user] = lambda: User(
    id=7,
    email="student@example.com",
    hashed_password="hashed",
    nickname="학생",
    student_id="20260001",
    role=UserRole.STUDENT,
)
client = TestClient(app)


def test_upload_png_image(monkeypatch):
    captured = {}

    def fake_upload_image(*, user_id, content, content_type):
        captured.update(
            user_id=user_id,
            content=content,
            content_type=content_type,
        )
        return StorageUploadResult(
            path="complaints/7/example.png",
            public_url=(
                "https://project.supabase.co/storage/v1/object/public/"
                "complaint-images/complaints/7/example.png"
            ),
        )

    monkeypatch.setattr(uploads, "upload_image", fake_upload_image)
    png = b"\x89PNG\r\n\x1a\n" + b"test-image"

    response = client.post(
        "/uploads/complaint-images",
        files={"file": ("evidence.png", png, "image/png")},
    )

    assert response.status_code == 201
    assert response.json()["storage_path"] == "complaints/7/example.png"
    assert response.json()["size"] == len(png)
    assert captured["user_id"] == 7
    assert captured["content_type"] == "image/png"


def test_non_image_file_is_rejected():
    response = client.post(
        "/uploads/complaint-images",
        files={"file": ("memo.txt", b"plain text", "text/plain")},
    )

    assert response.status_code == 415


def test_fake_image_signature_is_rejected():
    response = client.post(
        "/uploads/complaint-images",
        files={"file": ("fake.png", b"not-a-png", "image/png")},
    )

    assert response.status_code == 400


def test_oversized_image_is_rejected(monkeypatch):
    monkeypatch.setenv("MAX_IMAGE_UPLOAD_MB", "1")
    png = b"\x89PNG\r\n\x1a\n" + b"x" * (1024 * 1024)

    response = client.post(
        "/uploads/complaint-images",
        files={"file": ("large.png", png, "image/png")},
    )

    assert response.status_code == 413


def test_missing_supabase_settings_returns_service_unavailable(monkeypatch):
    def fake_upload_image(**_kwargs):
        raise RuntimeError(
            "SUPABASE_URL과 SUPABASE_SERVICE_ROLE_KEY 환경변수가 필요합니다."
        )

    monkeypatch.setattr(uploads, "upload_image", fake_upload_image)
    jpeg = b"\xff\xd8\xff\xe0" + b"image"

    response = client.post(
        "/uploads/complaint-images",
        files={"file": ("photo.jpg", jpeg, "image/jpeg")},
    )

    assert response.status_code == 503


def test_storage_path_uses_user_folder_and_extension():
    path = build_image_path(42, "image/webp")

    assert path.startswith("complaints/42/")
    assert path.endswith(".webp")
