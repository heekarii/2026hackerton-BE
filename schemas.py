import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from models import ComplaintStatus


class AttachmentCreate(BaseModel):
    """[요구사항 3] 민원 등록 시 첨부하는 사진/파일 1건."""
    file_url: str = Field(..., max_length=512, description="업로드된 파일의 URL")
    file_type: str = Field(..., max_length=50, description="MIME 타입 (예: image/jpeg)")


class AttachmentResponse(BaseModel):
    id: int
    file_url: str
    file_type: str
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class ComplaintCreate(BaseModel):
    """민원 등록 요청 본문."""
    title: str = Field(..., max_length=255, description="민원 제목")
    # [요구사항 4] 민원 사항과 개선 희망 사항을 분리하여 입력받는다.
    content: str = Field(..., description="민원 사항 본문")
    expectation: Optional[str] = Field(None, description="개선 희망 사항")
    # [요구사항 1, 2] 장소 및 발생 시간대
    location: str = Field(..., max_length=255, description="민원 발생 장소 (예: IT관 3층 복도)")
    occurred_at: datetime.datetime = Field(..., description="민원 발생 시간대 (ISO 8601)")
    # [요구사항 6] 익명 등록 여부
    is_anonymous: bool = Field(False, description="익명 등록 여부")
    category_id: Optional[int] = Field(None, description="민원 분류 카테고리 ID")
    # [요구사항 3] 사진 첨부 목록
    attachments: List[AttachmentCreate] = Field(default_factory=list, description="첨부 사진/파일 목록")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "IT관 3층 복도 형광등 고장",
                "content": "IT관 3층 복도 형광등 2개가 일주일째 깜빡이며 꺼져 있어 야간 통행이 어렵습니다.",
                "expectation": "형광등 교체 및 정기 점검을 요청합니다.",
                "location": "IT관 3층 복도",
                "occurred_at": "2026-06-24T19:30:00",
                "is_anonymous": True,
                "category_id": 1,
                "attachments": [
                    {"file_url": "https://example.com/uploads/light.jpg", "file_type": "image/jpeg"}
                ],
            }
        }
    )


class ComplaintResponse(BaseModel):
    """민원 등록/조회 응답."""
    id: int
    user_id: int
    title: str
    content: str
    expectation: Optional[str]
    location: str
    occurred_at: datetime.datetime
    is_anonymous: bool
    status: ComplaintStatus
    category_id: Optional[int]
    created_at: datetime.datetime
    updated_at: datetime.datetime
    attachments: List[AttachmentResponse] = []

    model_config = ConfigDict(from_attributes=True)
