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
