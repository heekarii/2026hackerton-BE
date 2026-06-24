from __future__ import annotations

import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from auth import get_current_user
from database import get_db
from models import (
    AdminAction,
    Complaint,
    ComplaintStatus,
    Department,
    User,
    UserRole,
)


router = APIRouter(prefix="/admin/complaints", tags=["Admin Complaints"])


ALLOWED_STATUS_TRANSITIONS = {
    ComplaintStatus.RECEIVED: {
        ComplaintStatus.RECEIVED,
        ComplaintStatus.IN_PROGRESS,
        ComplaintStatus.RESOLVED,
        ComplaintStatus.REJECTED,
    },
    ComplaintStatus.IN_PROGRESS: {
        ComplaintStatus.IN_PROGRESS,
        ComplaintStatus.RESOLVED,
        ComplaintStatus.REJECTED,
    },
    ComplaintStatus.RESOLVED: {
        ComplaintStatus.RESOLVED,
        ComplaintStatus.IN_PROGRESS,
    },
    ComplaintStatus.REJECTED: {
        ComplaintStatus.REJECTED,
        ComplaintStatus.IN_PROGRESS,
    },
}


class AdminComplaintProcessRequest(BaseModel):
    status: ComplaintStatus
    response_content: str = Field(
        min_length=1,
        max_length=5000,
        description="민원인에게 공개할 관리자 처리 답변",
    )
    department_id: Optional[int] = Field(
        default=None,
        ge=1,
        description="함께 변경할 담당 부서 ID",
    )


class AdminActionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    complaint_id: int
    admin_id: int
    admin_nickname: Optional[str]
    response_content: str
    status_to: ComplaintStatus
    created_at: datetime.datetime
    updated_at: datetime.datetime


class AdminComplaintProcessResponse(BaseModel):
    complaint_id: int
    status: ComplaintStatus
    department_id: Optional[int]
    department_name: Optional[str]
    action: AdminActionResponse


def require_admin_or_staff(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role not in (UserRole.ADMIN, UserRole.STAFF):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 또는 교직원 권한이 필요합니다.",
        )
    return current_user


def _validate_status_transition(
    current_status: ComplaintStatus,
    next_status: ComplaintStatus,
) -> None:
    if next_status not in ALLOWED_STATUS_TRANSITIONS[current_status]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"'{current_status.value}' 상태에서 "
                f"'{next_status.value}' 상태로 변경할 수 없습니다."
            ),
        )


def _to_action_response(action: AdminAction) -> AdminActionResponse:
    return AdminActionResponse(
        id=action.id,
        complaint_id=action.complaint_id,
        admin_id=action.admin_id,
        admin_nickname=action.admin.nickname if action.admin else None,
        response_content=action.response_content,
        status_to=action.status_to,
        created_at=action.created_at,
        updated_at=action.updated_at,
    )


@router.patch(
    "/{complaint_id}/process",
    response_model=AdminComplaintProcessResponse,
    summary="민원 처리 상태 변경 및 관리자 답변 등록",
)
def process_complaint(
    complaint_id: int,
    payload: AdminComplaintProcessRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_staff),
) -> AdminComplaintProcessResponse:
    complaint = db.scalar(
        select(Complaint)
        .options(selectinload(Complaint.recommended_dept))
        .where(Complaint.id == complaint_id)
    )
    if complaint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="민원을 찾을 수 없습니다.",
        )

    _validate_status_transition(complaint.status, payload.status)

    department = complaint.recommended_dept
    if payload.department_id is not None:
        department = db.get(Department, payload.department_id)
        if department is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="존재하지 않는 담당 부서입니다.",
            )
        complaint.recommended_dept = department

    complaint.status = payload.status
    action = AdminAction(
        complaint=complaint,
        admin=current_user,
        response_content=payload.response_content.strip(),
        status_to=payload.status,
    )
    db.add(action)
    db.commit()
    db.refresh(action)

    return AdminComplaintProcessResponse(
        complaint_id=complaint.id,
        status=complaint.status,
        department_id=department.id if department else None,
        department_name=department.name if department else None,
        action=_to_action_response(action),
    )


@router.get(
    "/{complaint_id}/actions",
    response_model=List[AdminActionResponse],
    summary="민원 관리자 처리 이력 조회",
)
def list_complaint_actions(
    complaint_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_or_staff),
) -> List[AdminActionResponse]:
    if db.get(Complaint, complaint_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="민원을 찾을 수 없습니다.",
        )

    actions = db.scalars(
        select(AdminAction)
        .options(selectinload(AdminAction.admin))
        .where(AdminAction.complaint_id == complaint_id)
        .order_by(AdminAction.created_at.asc(), AdminAction.id.asc())
    ).all()
    return [_to_action_response(action) for action in actions]
