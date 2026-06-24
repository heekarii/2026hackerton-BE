from __future__ import annotations
import datetime

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from models import ComplaintStatus, UserRole


class SignUpRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    nickname: str = Field(min_length=1, max_length=100)
    student_id: Optional[str] = Field(default=None, min_length=1, max_length=50)

    @field_validator("nickname")
    @classmethod
    def validate_nickname(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("닉네임은 공백일 수 없습니다.")
        return value

    @field_validator("student_id")
    @classmethod
    def normalize_student_id(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("학번은 공백일 수 없습니다.")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    student_id: Optional[str]
    nickname: str
    role: UserRole
    created_at: datetime.datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


# ─────────────────────────── 민원(Complaint) 스키마 ───────────────────────────

class AttachmentCreate(BaseModel):
    """[요구사항 3] 민원 등록 시 첨부하는 사진/파일 1건."""
    file_url: str = Field(..., max_length=512, description="업로드된 파일의 URL")
    file_type: str = Field(..., max_length=50, description="MIME 타입 (예: image/jpeg)")


class AttachmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_url: str
    file_type: str
    created_at: datetime.datetime


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


class ComplaintUpdate(BaseModel):
    """민원 수정 요청. 보낸 필드만 부분 수정한다(미전송 필드는 유지)."""
    title: Optional[str] = Field(None, max_length=255, description="민원 제목")
    content: Optional[str] = Field(None, description="민원 사항 본문")
    expectation: Optional[str] = Field(None, description="개선 희망 사항")
    location: Optional[str] = Field(None, max_length=255, description="민원 발생 장소")
    occurred_at: Optional[datetime.datetime] = Field(None, description="민원 발생 시간대")
    is_anonymous: Optional[bool] = Field(None, description="익명 등록 여부")
    category_id: Optional[int] = Field(None, description="민원 분류 카테고리 ID")


class ComplaintResponse(BaseModel):
    """민원 등록/조회 응답.

    익명 민원(is_anonymous=True)인 경우 작성자 정보(user_id, author_nickname)는
    None 으로 마스킹하여 응답한다. (안전장치: 익명 공개)
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: Optional[int] = None  # 익명이면 None 으로 마스킹
    author_nickname: Optional[str] = None  # 익명이면 None
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
