import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import User
from notification_model import Notification

router = APIRouter(prefix="/notifications", tags=["Notifications"])


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    complaint_id: Optional[int]
    message: str
    is_read: bool
    created_at: datetime.datetime


@router.get(
    "/me",
    response_model=List[NotificationResponse],
    summary="내 알림 목록 조회",
    description="로그인한 사용자가 받은 알림을 최신순으로 조회합니다. (처리 현황 알림 등)",
)
def list_my_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    unread_only: bool = Query(False, description="읽지 않은 알림만 보기"),
):
    """내 알림 목록 (마이페이지 알림함)."""
    query = db.query(Notification).filter(Notification.user_id == current_user.id)
    if unread_only:
        query = query.filter(Notification.is_read.is_(False))
    return query.order_by(Notification.created_at.desc()).all()


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    summary="알림 읽음 처리",
    responses={404: {"description": "본인 알림이 아니거나 존재하지 않음"}},
)
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """알림을 읽음 상태로 변경 (본인 알림만)."""
    noti = db.get(Notification, notification_id)
    if noti is None or noti.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="알림을 찾을 수 없습니다.")
    noti.is_read = True
    db.commit()
    db.refresh(noti)
    return noti
