from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user_id
from models import Complaint, ComplaintAttachment, ComplaintStatus
import schemas

router = APIRouter(prefix="/complaints", tags=["Complaints"])


def _to_response(complaint: Complaint) -> schemas.ComplaintResponse:
    """ORM 민원 객체를 응답 스키마로 변환하며, 익명 민원의 작성자 정보를 마스킹한다."""
    data = schemas.ComplaintResponse.model_validate(complaint)
    if complaint.is_anonymous:
        data.user_id = None
        data.author_nickname = None
    else:
        data.user_id = complaint.user_id
        data.author_nickname = complaint.user.nickname if complaint.user else None
    return data


@router.post(
    "",
    response_model=schemas.ComplaintResponse,
    status_code=status.HTTP_201_CREATED,
    summary="민원 등록",
    description=(
        "새로운 민원을 등록합니다.\n\n"
        "- **민원 사항(content)**과 **개선 희망 사항(expectation)**을 분리 저장합니다. [요구사항 4]\n"
        "- **장소(location)**와 **발생 시간대(occurred_at)**를 함께 받습니다. [요구사항 1, 2]\n"
        "- **사진/파일(attachments)**을 여러 개 첨부할 수 있습니다. [요구사항 3]\n"
        "- **익명 등록(is_anonymous)**을 지원합니다. [요구사항 6]"
    ),
)
def create_complaint(
    payload: schemas.ComplaintCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """민원 등록 엔드포인트. 등록된 민원의 상태는 기본값(received)으로 시작한다."""
    complaint = Complaint(
        user_id=user_id,
        title=payload.title,
        content=payload.content,
        expectation=payload.expectation,
        location=payload.location,
        occurred_at=payload.occurred_at,
        is_anonymous=payload.is_anonymous,
        category_id=payload.category_id,
    )

    # [요구사항 3] 첨부 파일을 함께 저장 (cascade 설정으로 민원과 함께 영속화)
    for att in payload.attachments:
        complaint.attachments.append(
            ComplaintAttachment(file_url=att.file_url, file_type=att.file_type)
        )

    db.add(complaint)
    db.commit()
    db.refresh(complaint)
    return complaint


@router.get(
    "",
    response_model=List[schemas.ComplaintResponse],
    summary="민원 목록 조회",
    description=(
        "등록된 민원을 최신순으로 조회합니다. 상태/카테고리로 필터링하고 페이지네이션할 수 있습니다.\n\n"
        "익명 민원은 작성자 정보가 마스킹되어 응답됩니다."
    ),
)
def list_complaints(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0, description="건너뛸 개수 (페이지네이션)"),
    limit: int = Query(20, ge=1, le=100, description="가져올 최대 개수"),
    status_filter: Optional[ComplaintStatus] = Query(
        None, alias="status", description="민원 상태로 필터링"
    ),
    category_id: Optional[int] = Query(None, description="카테고리 ID로 필터링"),
):
    """민원 목록 조회 엔드포인트."""
    query = db.query(Complaint)
    if status_filter is not None:
        query = query.filter(Complaint.status == status_filter)
    if category_id is not None:
        query = query.filter(Complaint.category_id == category_id)

    complaints = (
        query.order_by(Complaint.created_at.desc()).offset(skip).limit(limit).all()
    )
    return [_to_response(c) for c in complaints]


@router.get(
    "/{complaint_id}",
    response_model=schemas.ComplaintResponse,
    summary="민원 상세 조회",
    description="민원 ID로 단건을 조회합니다. 익명 민원은 작성자 정보가 마스킹됩니다.",
    responses={404: {"description": "해당 ID의 민원이 존재하지 않음"}},
)
def get_complaint(complaint_id: int, db: Session = Depends(get_db)):
    """민원 상세 조회 엔드포인트."""
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if complaint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="민원을 찾을 수 없습니다.")
    return _to_response(complaint)


@router.patch(
    "/{complaint_id}",
    response_model=schemas.ComplaintResponse,
    summary="민원 수정",
    description=(
        "민원 작성자가 본인 민원의 내용을 부분 수정합니다. 보낸 필드만 변경됩니다.\n\n"
        "처리 상태(status) 변경은 관리자 권한이므로 이 엔드포인트에서 다루지 않습니다."
    ),
    responses={
        403: {"description": "본인 민원이 아님"},
        404: {"description": "해당 ID의 민원이 존재하지 않음"},
    },
)
def update_complaint(
    complaint_id: int,
    payload: schemas.ComplaintUpdate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """민원 수정 엔드포인트 (작성자 본인만 가능)."""
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if complaint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="민원을 찾을 수 없습니다.")

    # TODO(auth): 실제 인증 도입 시 작성자 본인 여부를 정식으로 검증한다.
    if complaint.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="본인이 작성한 민원만 수정할 수 있습니다.")

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="수정할 내용이 없습니다.")
    for field, value in updates.items():
        setattr(complaint, field, value)

    db.commit()
    db.refresh(complaint)
    return _to_response(complaint)


@router.delete(
    "/{complaint_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="민원 삭제",
    description=(
        "민원 작성자가 본인 민원을 삭제합니다. 첨부 파일도 함께 삭제됩니다.\n\n"
        "성공 시 본문 없이 204 No Content 를 반환합니다."
    ),
    responses={
        403: {"description": "본인 민원이 아님"},
        404: {"description": "해당 ID의 민원이 존재하지 않음"},
    },
)
def delete_complaint(
    complaint_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """민원 삭제 엔드포인트 (작성자 본인만 가능)."""
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if complaint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="민원을 찾을 수 없습니다.")

    # TODO(auth): 실제 인증 도입 시 작성자 본인 여부를 정식으로 검증한다.
    if complaint.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="본인이 작성한 민원만 삭제할 수 있습니다.")

    # 첨부(attachments)는 모델의 cascade="all, delete-orphan" 설정으로 함께 삭제된다.
    db.delete(complaint)
    db.commit()
    return None
