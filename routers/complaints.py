from __future__ import annotations
import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import User, Complaint, Category, Department, ComplaintAttachment, ComplaintStatus
from schemas import ComplaintCreateRequest, ComplaintResponse
from services.openai_analysis import analyze_complaint

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
