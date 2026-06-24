from __future__ import annotations

import datetime
import math
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from auth import get_current_user
from database import get_db
from models import AdminAction, Complaint, ComplaintStatus, User


router = APIRouter(prefix="/users/me", tags=["My Page"])


STATUS_META = {
    ComplaintStatus.RECEIVED: {
        "label": "접수됨",
        "progress": 25,
        "description": "민원이 접수되어 담당 부서 확인을 기다리고 있습니다.",
    },
    ComplaintStatus.IN_PROGRESS: {
        "label": "처리 중",
        "progress": 60,
        "description": "담당 부서에서 민원을 확인하고 처리하고 있습니다.",
    },
    ComplaintStatus.RESOLVED: {
        "label": "해결됨",
        "progress": 100,
        "description": "민원 처리가 완료되었습니다.",
    },
    ComplaintStatus.REJECTED: {
        "label": "반려됨",
        "progress": 100,
        "description": "민원이 반려되었습니다. 처리 답변을 확인해 주세요.",
    },
}


class MyComplaintStatus(BaseModel):
    code: ComplaintStatus
    label: str
    progress: int = Field(ge=0, le=100)
    description: str
    is_terminal: bool


class MyComplaintListItem(BaseModel):
    id: int
    title: str
    location: str
    is_anonymous: bool
    status: MyComplaintStatus
    department_name: Optional[str]
    expected_days: Optional[str]
    latest_response: Optional[str]
    occurred_at: datetime.datetime
    created_at: datetime.datetime
    updated_at: datetime.datetime


class MyComplaintSummary(BaseModel):
    total: int
    received: int
    in_progress: int
    resolved: int
    rejected: int


class MyComplaintListResponse(BaseModel):
    items: List[MyComplaintListItem]
    page: int
    page_size: int
    total: int
    total_pages: int
    summary: MyComplaintSummary


class MyComplaintAttachment(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_url: str
    file_type: str
    created_at: datetime.datetime


class ComplaintProgressEvent(BaseModel):
    event_type: str
    status: ComplaintStatus
    status_label: str
    title: str
    content: Optional[str]
    actor_nickname: Optional[str]
    created_at: datetime.datetime


class MyComplaintDetailResponse(BaseModel):
    id: int
    title: str
    content: str
    expectation: Optional[str]
    location: str
    occurred_at: datetime.datetime
    is_anonymous: bool
    status: MyComplaintStatus
    department_name: Optional[str]
    expected_days: Optional[str]
    ai_summary: Optional[str]
    attachments: List[MyComplaintAttachment]
    timeline: List[ComplaintProgressEvent]
    created_at: datetime.datetime
    updated_at: datetime.datetime


def _status_response(complaint_status: ComplaintStatus) -> MyComplaintStatus:
    meta = STATUS_META[complaint_status]
    return MyComplaintStatus(
        code=complaint_status,
        label=meta["label"],
        progress=meta["progress"],
        description=meta["description"],
        is_terminal=complaint_status
        in (ComplaintStatus.RESOLVED, ComplaintStatus.REJECTED),
    )


def _latest_action(complaint: Complaint) -> Optional[AdminAction]:
    if not complaint.actions:
        return None
    return max(complaint.actions, key=lambda action: action.created_at)


def _to_list_item(complaint: Complaint) -> MyComplaintListItem:
    latest_action = _latest_action(complaint)
    return MyComplaintListItem(
        id=complaint.id,
        title=complaint.title,
        location=complaint.location,
        is_anonymous=complaint.is_anonymous,
        status=_status_response(complaint.status),
        department_name=(
            complaint.recommended_dept.name
            if complaint.recommended_dept
            else complaint.ai_department
        ),
        expected_days=complaint.ai_expected_days,
        latest_response=(
            latest_action.response_content if latest_action else None
        ),
        occurred_at=complaint.occurred_at,
        created_at=complaint.created_at,
        updated_at=complaint.updated_at,
    )


def _build_timeline(complaint: Complaint) -> List[ComplaintProgressEvent]:
    events = [
        ComplaintProgressEvent(
            event_type="submitted",
            status=ComplaintStatus.RECEIVED,
            status_label=STATUS_META[ComplaintStatus.RECEIVED]["label"],
            title="민원 접수",
            content="민원이 정상적으로 접수되었습니다.",
            actor_nickname=None,
            created_at=complaint.created_at,
        )
    ]

    for action in sorted(complaint.actions, key=lambda item: item.created_at):
        events.append(
            ComplaintProgressEvent(
                event_type="admin_action",
                status=action.status_to,
                status_label=STATUS_META[action.status_to]["label"],
                title=f"처리 상태가 '{STATUS_META[action.status_to]['label']}'로 변경됨",
                content=action.response_content,
                actor_nickname=(
                    action.admin.nickname if action.admin is not None else None
                ),
                created_at=action.created_at,
            )
        )
    return events


def _summary_for_user(db: Session, user_id: int) -> MyComplaintSummary:
    rows = db.execute(
        select(Complaint.status, func.count(Complaint.id))
        .where(Complaint.user_id == user_id)
        .group_by(Complaint.status)
    ).all()
    counts: Dict[ComplaintStatus, int] = {
        complaint_status: count for complaint_status, count in rows
    }
    return MyComplaintSummary(
        total=sum(counts.values()),
        received=counts.get(ComplaintStatus.RECEIVED, 0),
        in_progress=counts.get(ComplaintStatus.IN_PROGRESS, 0),
        resolved=counts.get(ComplaintStatus.RESOLVED, 0),
        rejected=counts.get(ComplaintStatus.REJECTED, 0),
    )


@router.get(
    "/complaints",
    response_model=MyComplaintListResponse,
    summary="내 민원 목록 및 진행 상황 조회",
)
def list_my_complaints(
    complaint_status: Optional[ComplaintStatus] = Query(
        default=None,
        alias="status",
        description="접수됨, 처리 중, 해결됨, 반려됨 상태 필터",
    ),
    date_from: Optional[datetime.date] = Query(
        default=None,
        description="등록일 시작 날짜",
    ),
    date_to: Optional[datetime.date] = Query(
        default=None,
        description="등록일 종료 날짜",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MyComplaintListResponse:
    conditions = [Complaint.user_id == current_user.id]
    if complaint_status is not None:
        conditions.append(Complaint.status == complaint_status)
    if date_from is not None:
        conditions.append(
            Complaint.created_at
            >= datetime.datetime.combine(date_from, datetime.time.min)
        )
    if date_to is not None:
        conditions.append(
            Complaint.created_at
            <= datetime.datetime.combine(date_to, datetime.time.max)
        )

    total = db.scalar(
        select(func.count(Complaint.id)).where(*conditions)
    ) or 0
    complaints = db.scalars(
        select(Complaint)
        .options(
            selectinload(Complaint.recommended_dept),
            selectinload(Complaint.actions),
        )
        .where(*conditions)
        .order_by(Complaint.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return MyComplaintListResponse(
        items=[_to_list_item(complaint) for complaint in complaints],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=math.ceil(total / page_size) if total else 0,
        summary=_summary_for_user(db, current_user.id),
    )


@router.get(
    "/complaints/{complaint_id}",
    response_model=MyComplaintDetailResponse,
    summary="내 민원 상세 진행 상황 조회",
)
def get_my_complaint(
    complaint_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MyComplaintDetailResponse:
    complaint = db.scalar(
        select(Complaint)
        .options(
            selectinload(Complaint.recommended_dept),
            selectinload(Complaint.attachments),
            selectinload(Complaint.actions).selectinload(AdminAction.admin),
        )
        .where(
            Complaint.id == complaint_id,
            Complaint.user_id == current_user.id,
        )
    )
    if complaint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="본인이 작성한 민원을 찾을 수 없습니다.",
        )

    return MyComplaintDetailResponse(
        id=complaint.id,
        title=complaint.title,
        content=complaint.content,
        expectation=complaint.expectation,
        location=complaint.location,
        occurred_at=complaint.occurred_at,
        is_anonymous=complaint.is_anonymous,
        status=_status_response(complaint.status),
        department_name=(
            complaint.recommended_dept.name
            if complaint.recommended_dept
            else complaint.ai_department
        ),
        expected_days=complaint.ai_expected_days,
        ai_summary=complaint.ai_summary,
        attachments=[
            MyComplaintAttachment.model_validate(attachment)
            for attachment in complaint.attachments
        ],
        timeline=_build_timeline(complaint),
        created_at=complaint.created_at,
        updated_at=complaint.updated_at,
    )
