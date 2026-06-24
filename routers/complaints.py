from __future__ import annotations
import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import User, Complaint, Category, Department, ComplaintAttachment, ComplaintStatus
from schemas import ComplaintCreateRequest, ComplaintResponse, ComplaintUpdate
from services.openai_analysis import analyze_complaint


def _validate_category(db: Session, category_id: Optional[int]) -> None:
    """category_id 가 주어졌으면 실제 존재하는 카테고리인지 검증한다 (없으면 친절한 400)."""
    if category_id is None:
        return
    if db.scalar(select(Category.id).where(Category.id == category_id)) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"존재하지 않는 카테고리입니다 (category_id={category_id}).",
        )

router = APIRouter(prefix="/complaints", tags=["Complaints"])

@router.post(
    "",
    response_model=ComplaintResponse,
    status_code=status.HTTP_201_CREATED,
    summary="민원 등록",
    description="새로운 민원을 등록하고 AI를 사용해 자동으로 분석한 카테고리, 긴급도, 담당부서 등의 정보를 함께 저장합니다."
)
def create_complaint(
    payload: ComplaintCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Complaint:
    # 1. OpenAI (또는 Mock) 분석 수행
    try:
        analysis = analyze_complaint(payload.content)
    except Exception as e:
        # services/openai_analysis.py 자체에서 예외 처리를 하지만
        # 예상하지 못한 에러 발생 시 최후의 방어막 역할을 합니다.
        from services.openai_analysis import get_mock_analysis
        print(f"[Complaints Router] AI 분석 중 예외 발생 ({e}), Mock 결과로 대체합니다.")
        analysis = get_mock_analysis(payload.content)

    # 2. 분석 카테고리 매핑 (Category 조회 또는 자동 생성)
    category = db.scalar(select(Category).where(Category.name == analysis.category))
    if not category:
        category = Category(
            name=analysis.category,
            description=f"AI가 자동으로 분류한 {analysis.category} 카테고리입니다."
        )
        db.add(category)
        db.flush()

    # 3. 추천 담당 부서 매핑 (Department 조회 또는 자동 생성)
    department = db.scalar(select(Department).where(Department.name == analysis.department))
    if not department:
        department = Department(
            name=analysis.department,
            description=f"AI가 추천한 {analysis.department} 담당 부서입니다."
        )
        db.add(department)
        db.flush()

    # 4. 긴급도 스코어 매핑
    urgency_map = {
        "LOW": 1.00,
        "MEDIUM": 2.50,
        "HIGH": 4.00,
        "CRITICAL": 5.00
    }
    urgency_score = urgency_map.get(analysis.urgency.upper(), 1.00)

    # 5. Complaint 인스턴스 생성
    complaint = Complaint(
        user_id=current_user.id,
        title=payload.title,
        content=payload.content,
        expectation=payload.desired_solution,
        is_anonymous=payload.is_anonymous,
        status=ComplaintStatus.RECEIVED,
        location=payload.location_name,
        occurred_at=datetime.datetime.utcnow(),
        
        # AI 분석 매핑 컬럼
        category_id=category.id,
        urgency_score=urgency_score,
        is_sensitive=analysis.sensitive,
        recommended_dept_id=department.id,
        
        # AI 분석 상세 내용 저장 컬럼 (complaints 테이블 신규 추가 필드)
        ai_category=analysis.category,
        ai_subcategory=analysis.subcategory,
        ai_sentiment=analysis.sentiment,
        ai_urgency=analysis.urgency,
        ai_sensitive=analysis.sensitive,
        ai_risk_type=analysis.risk_type,
        ai_department=analysis.department,
        ai_summary=analysis.summary,
        ai_keywords=analysis.keywords,
        ai_expected_days=analysis.expected_days,
        ai_recommended_action=analysis.recommended_action,
        
        # GPS 위도 경도
        latitude=payload.latitude,
        longitude=payload.longitude
    )
    db.add(complaint)
    db.flush()

    # 6. 이미지 첨부파일이 존재하는 경우 저장
    if payload.image_url:
        # 간단히 URL 확장자 등으로 파일 타입을 기본 추정
        file_type = "image/jpeg"
        if payload.image_url.endswith(".png"):
            file_type = "image/png"
        elif payload.image_url.endswith(".gif"):
            file_type = "image/gif"
            
        attachment = ComplaintAttachment(
            complaint_id=complaint.id,
            file_url=payload.image_url,
            file_type=file_type
        )
        db.add(attachment)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"민원 저장 처리 중 오류가 발생했습니다: {str(e)}"
        )

    db.refresh(complaint)
    return complaint


@router.get(
    "",
    response_model=List[ComplaintResponse],
    summary="민원 목록 조회",
    description="등록된 민원을 최신순으로 조회합니다. 상태/카테고리 필터와 페이지네이션을 지원합니다.",
)
def list_complaints(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0, description="건너뛸 개수 (페이지네이션)"),
    limit: int = Query(20, ge=1, le=100, description="가져올 최대 개수"),
    status_filter: Optional[ComplaintStatus] = Query(None, alias="status", description="민원 상태로 필터링"),
    category_id: Optional[int] = Query(None, description="카테고리 ID로 필터링"),
) -> List[Complaint]:
    """민원 목록 조회."""
    query = db.query(Complaint)
    if status_filter is not None:
        query = query.filter(Complaint.status == status_filter)
    if category_id is not None:
        query = query.filter(Complaint.category_id == category_id)
    return query.order_by(Complaint.created_at.desc()).offset(skip).limit(limit).all()


@router.get(
    "/me",
    response_model=List[ComplaintResponse],
    summary="내 민원 목록 조회 (마이페이지)",
    description="로그인한 사용자가 작성한 민원만 최신순으로 조회합니다. [요구사항 민8]",
)
def list_my_complaints(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = Query(0, ge=0, description="건너뛸 개수 (페이지네이션)"),
    limit: int = Query(20, ge=1, le=100, description="가져올 최대 개수"),
) -> List[Complaint]:
    """내가 작성한 민원 목록 (마이페이지)."""
    return (
        db.query(Complaint)
        .filter(Complaint.user_id == current_user.id)
        .order_by(Complaint.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


# NOTE: "/me" 라우트는 반드시 "/{complaint_id}" 보다 먼저 정의되어야 한다.
#       (그렇지 않으면 "me" 가 complaint_id 로 해석되어 422 발생)
@router.get(
    "/{complaint_id}",
    response_model=ComplaintResponse,
    summary="민원 상세 조회",
    responses={404: {"description": "해당 ID의 민원이 존재하지 않음"}},
)
def get_complaint(complaint_id: int, db: Session = Depends(get_db)) -> Complaint:
    """민원 단건 상세 조회."""
    complaint = db.get(Complaint, complaint_id)
    if complaint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="민원을 찾을 수 없습니다.")
    return complaint


@router.patch(
    "/{complaint_id}",
    response_model=ComplaintResponse,
    summary="민원 수정",
    description="민원 작성자가 본인 민원의 내용을 부분 수정합니다. 보낸 필드만 변경됩니다.",
    responses={
        403: {"description": "본인 민원이 아님"},
        404: {"description": "해당 ID의 민원이 존재하지 않음"},
    },
)
def update_complaint(
    complaint_id: int,
    payload: ComplaintUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Complaint:
    """민원 수정 (작성자 본인만)."""
    complaint = db.get(Complaint, complaint_id)
    if complaint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="민원을 찾을 수 없습니다.")
    if complaint.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="본인이 작성한 민원만 수정할 수 있습니다.")

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="수정할 내용이 없습니다.")
    if "category_id" in updates:
        _validate_category(db, updates["category_id"])
    for field, value in updates.items():
        setattr(complaint, field, value)

    db.commit()
    db.refresh(complaint)
    return complaint


@router.delete(
    "/{complaint_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="민원 삭제",
    description="민원 작성자가 본인 민원을 삭제합니다. 첨부 파일도 함께 삭제됩니다.",
    responses={
        403: {"description": "본인 민원이 아님"},
        404: {"description": "해당 ID의 민원이 존재하지 않음"},
    },
)
def delete_complaint(
    complaint_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """민원 삭제 (작성자 본인만). 첨부는 cascade 로 함께 삭제."""
    complaint = db.get(Complaint, complaint_id)
    if complaint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="민원을 찾을 수 없습니다.")
    if complaint.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="본인이 작성한 민원만 삭제할 수 있습니다.")
    db.delete(complaint)
    db.commit()
    return None
