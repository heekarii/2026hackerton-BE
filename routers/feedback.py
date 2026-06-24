from __future__ import annotations

import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import Complaint, ComplaintStatus, Feedback, User


router = APIRouter(
    prefix="/complaints/{complaint_id}/feedback",
    tags=["Complaint Feedback"],
)


class FeedbackCreateRequest(BaseModel):
    rating: int = Field(
        ge=1,
        le=5,
        description="민원 처리 만족도 점수(1점~5점)",
    )
    comment: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="처리 결과에 대한 추가 의견",
    )

    @field_validator("comment")
    @classmethod
    def normalize_comment(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None


class FeedbackUpdateRequest(BaseModel):
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    comment: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("comment")
    @classmethod
    def normalize_comment(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None


class FeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    complaint_id: int
    rating: int
    comment: Optional[str]
    created_at: datetime.datetime


def _get_owned_complaint(
    db: Session,
    complaint_id: int,
    current_user: User,
) -> Complaint:
    complaint = db.get(Complaint, complaint_id)
    if complaint is None or complaint.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="본인이 작성한 민원을 찾을 수 없습니다.",
        )
    return complaint


def _get_feedback_or_404(
    db: Session,
    complaint: Complaint,
) -> Feedback:
    if complaint.feedback is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="등록된 만족도 피드백이 없습니다.",
        )
    return complaint.feedback


@router.post(
    "",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="해결된 민원 만족도 피드백 등록",
)
def create_feedback(
    complaint_id: int,
    payload: FeedbackCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Feedback:
    complaint = _get_owned_complaint(db, complaint_id, current_user)
    if complaint.status != ComplaintStatus.RESOLVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="해결 완료된 민원에만 만족도 피드백을 등록할 수 있습니다.",
        )
    if complaint.feedback is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 만족도 피드백을 등록한 민원입니다.",
        )

    feedback = Feedback(
        complaint=complaint,
        rating=payload.rating,
        comment=payload.comment,
    )
    db.add(feedback)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 만족도 피드백을 등록한 민원입니다.",
        )
    db.refresh(feedback)
    return feedback


@router.get(
    "",
    response_model=FeedbackResponse,
    summary="내 민원 만족도 피드백 조회",
)
def get_feedback(
    complaint_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Feedback:
    complaint = _get_owned_complaint(db, complaint_id, current_user)
    return _get_feedback_or_404(db, complaint)


@router.patch(
    "",
    response_model=FeedbackResponse,
    summary="내 민원 만족도 피드백 수정",
)
def update_feedback(
    complaint_id: int,
    payload: FeedbackUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Feedback:
    complaint = _get_owned_complaint(db, complaint_id, current_user)
    feedback = _get_feedback_or_404(db, complaint)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="수정할 피드백 내용이 없습니다.",
        )

    for field, value in updates.items():
        setattr(feedback, field, value)
    db.commit()
    db.refresh(feedback)
    return feedback
