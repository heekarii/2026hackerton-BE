import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, computed_field
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import User, UserRole, Complaint, AdminAction, ComplaintStatus
from notification_model import Notification

router = APIRouter(prefix="/admin/complaints", tags=["Admin - 민원 처리"])

# 처리 상태 한글 라벨
STATUS_LABEL = {
    ComplaintStatus.RECEIVED: "처리 전(접수됨)",
    ComplaintStatus.IN_PROGRESS: "처리 중",
    ComplaintStatus.RESOLVED: "처리 완료",
    ComplaintStatus.REJECTED: "반려됨",
}


def require_staff(current_user: User = Depends(get_current_user)) -> User:
    """관리자/담당자(ADMIN, STAFF)만 통과시킨다."""
    if current_user.role not in (UserRole.ADMIN, UserRole.STAFF):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자/담당자 권한이 필요합니다.",
        )
    return current_user


class StatusUpdateRequest(BaseModel):
    status: ComplaintStatus = Field(
        ..., description="변경할 처리 상태 (received=처리전 / in_progress=처리중 / resolved=처리완료 / rejected=반려)"
    )
    response_content: Optional[str] = Field(None, description="관리자 처리 답변/메모 (선택)")


class AdminActionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    complaint_id: int
    admin_id: int
    response_content: str
    status_to: ComplaintStatus
    created_at: datetime.datetime

    @computed_field
    @property
    def status_to_label(self) -> str:
        """변경 후 상태의 한글 라벨."""
        return STATUS_LABEL.get(self.status_to, self.status_to.value)


class StatusUpdateResponse(BaseModel):
    complaint_id: int
    status: ComplaintStatus
    status_label: str  # 한글 라벨 (예: "처리 완료", "반려됨")
    notified_user_id: int
    action: AdminActionResponse


@router.patch(
    "/{complaint_id}/status",
    response_model=StatusUpdateResponse,
    summary="민원 처리 상태 변경 (관리자)",
    description=(
        "관리자/담당자가 민원의 처리 상태를 변경합니다 (처리전→처리중→처리완료/반려).\n\n"
        "- 변경 이력을 admin_actions 에 기록합니다.\n"
        "- 변경 시 해당 민원 **작성자에게 알림이 생성**됩니다."
    ),
    responses={
        403: {"description": "관리자/담당자 권한 없음"},
        404: {"description": "해당 ID의 민원이 존재하지 않음"},
    },
)
def update_complaint_status(
    complaint_id: int,
    payload: StatusUpdateRequest,
    db: Session = Depends(get_db),
    staff: User = Depends(require_staff),
):
    """민원 처리 상태 변경 + 처리 이력 기록 + 작성자 알림 생성."""
    complaint = db.get(Complaint, complaint_id)
    if complaint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="민원을 찾을 수 없습니다.")

    label = STATUS_LABEL.get(payload.status, payload.status.value)
    author_id = complaint.user_id
    title = complaint.title

    # 모든 상태(반려 포함) 동일 처리: 상태만 변경하고 유지한다.
    # 반려여도 삭제하지 않으므로 민원인은 마이페이지에서 '반려됨' 상태를 확인할 수 있다.
    complaint.status = payload.status
    content = payload.response_content or f"민원 상태가 '{label}'(으)로 변경되었습니다."
    action = AdminAction(
        complaint_id=complaint.id,
        admin_id=staff.id,
        response_content=content,
        status_to=payload.status,
    )
    db.add(action)

    msg = f"[{title}] 민원이 '{label}' 상태가 되었습니다."
    if payload.response_content:
        msg += f" 담당자 답변: {payload.response_content}"
    db.add(Notification(user_id=author_id, complaint_id=complaint.id, message=msg))

    db.commit()
    db.refresh(action)
    return StatusUpdateResponse(
        complaint_id=complaint.id,
        status=complaint.status,
        status_label=label,
        notified_user_id=author_id,
        action=AdminActionResponse.model_validate(action),
    )


@router.get(
    "/{complaint_id}/actions",
    response_model=List[AdminActionResponse],
    summary="민원 처리 이력 조회 (관리자)",
    description="해당 민원의 처리 상태 변경/답변 이력을 최신순으로 조회합니다.",
)
def list_complaint_actions(
    complaint_id: int,
    db: Session = Depends(get_db),
    staff: User = Depends(require_staff),
):
    """민원 처리 이력 조회."""
    return (
        db.query(AdminAction)
        .filter(AdminAction.complaint_id == complaint_id)
        .order_by(AdminAction.created_at.desc())
        .all()
    )
