from __future__ import annotations
import datetime

from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from models import UserRole


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


class ComplaintCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="민원 제목")
    content: str = Field(..., min_length=1, description="민원 내용")
    desired_solution: Optional[str] = Field(default=None, description="개선 희망 사항")
    location_name: str = Field(..., min_length=1, max_length=255, description="민원 발생 장소 명칭")
    latitude: Optional[float] = Field(default=None, description="위도")
    longitude: Optional[float] = Field(default=None, description="경도")
    image_url: Optional[str] = Field(default=None, description="첨부 이미지 URL")
    is_anonymous: bool = Field(default=False, description="익명 여부")


class ComplaintResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str
    content: str
    expectation: Optional[str]
    is_anonymous: bool
    status: str
    location: str
    occurred_at: datetime.datetime
    latitude: Optional[float]
    longitude: Optional[float]
    created_at: datetime.datetime
    updated_at: datetime.datetime
    
    # AI 분석 관련 필드
    ai_category: Optional[str]
    ai_subcategory: Optional[str]
    ai_sentiment: Optional[str]
    ai_urgency: Optional[str]
    ai_sensitive: bool
    ai_risk_type: Optional[str]
    ai_department: Optional[str]
    ai_summary: Optional[str]
    ai_keywords: Optional[list[str]]
    ai_expected_days: Optional[str]
    ai_recommended_action: Optional[str]


class ComplaintUpdate(BaseModel):
    """민원 수정 요청. 보낸 필드만 부분 수정한다(미전송 필드는 유지)."""
    title: Optional[str] = Field(default=None, max_length=255, description="민원 제목")
    content: Optional[str] = Field(default=None, description="민원 사항 본문")
    expectation: Optional[str] = Field(default=None, description="개선 희망 사항")
    location: Optional[str] = Field(default=None, max_length=255, description="민원 발생 장소")
    occurred_at: Optional[datetime.datetime] = Field(default=None, description="민원 발생 시간대")
    is_anonymous: Optional[bool] = Field(default=None, description="익명 등록 여부")
    category_id: Optional[int] = Field(default=None, description="민원 분류 카테고리 ID")

