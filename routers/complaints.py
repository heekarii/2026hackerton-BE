from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user_id
from models import Complaint, ComplaintAttachment
import schemas

router = APIRouter(prefix="/complaints", tags=["Complaints"])


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
