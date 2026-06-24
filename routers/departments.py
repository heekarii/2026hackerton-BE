from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import Complaint, Department, User, UserRole
from services.department_routing import (
    DEPARTMENT_RULES,
    DepartmentMatch,
    DepartmentRule,
    get_department_rule,
    match_departments,
)


router = APIRouter(tags=["Department Routing"])


class DepartmentCatalogResponse(BaseModel):
    name: str
    description: str
    keywords: List[str]
    aliases: List[str]


class DepartmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str]


class DepartmentMatchResponse(BaseModel):
    department: DepartmentCatalogResponse
    score: int
    confidence: float
    matched_keywords: List[str]


class DepartmentRecommendRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)
    expectation: Optional[str] = None
    location: Optional[str] = None
    suggested_department: Optional[str] = Field(
        default=None,
        description="AI 분석 결과의 부서명. 부서 목록 또는 별칭과 일치하면 가중치를 부여합니다.",
    )


class DepartmentRecommendationResponse(BaseModel):
    recommended: DepartmentMatchResponse
    candidates: List[DepartmentMatchResponse]


class DepartmentAssignmentRequest(BaseModel):
    department_name: str = Field(
        min_length=1,
        description="부서 목록의 이름 또는 별칭",
    )


class ComplaintRoutingResponse(BaseModel):
    complaint_id: int
    department: DepartmentResponse
    matched_keywords: List[str] = Field(default_factory=list)
    confidence: float = 1.0


class RoutedComplaintResponse(BaseModel):
    id: int
    title: str
    content: str
    location: str
    status: str
    recommended_dept_id: Optional[int]


def _catalog_response(rule: DepartmentRule) -> DepartmentCatalogResponse:
    return DepartmentCatalogResponse(
        name=rule.name,
        description=rule.description,
        keywords=list(rule.keywords),
        aliases=list(rule.aliases),
    )


def _match_response(match: DepartmentMatch) -> DepartmentMatchResponse:
    return DepartmentMatchResponse(
        department=_catalog_response(match.rule),
        score=match.score,
        confidence=match.confidence,
        matched_keywords=list(match.matched_keywords),
    )


def _require_staff(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in (UserRole.ADMIN, UserRole.STAFF):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 또는 교직원 권한이 필요합니다.",
        )
    return current_user


def _get_or_create_department(db: Session, rule: DepartmentRule) -> Department:
    department = db.scalar(select(Department).where(Department.name == rule.name))
    if department is None:
        department = Department(name=rule.name, description=rule.description)
        db.add(department)
        db.flush()
    elif department.description != rule.description:
        department.description = rule.description
    return department


@router.get(
    "/departments",
    response_model=List[DepartmentCatalogResponse],
    summary="라우팅 가능한 유관 부서 목록",
)
def list_department_catalog() -> List[DepartmentCatalogResponse]:
    return [_catalog_response(rule) for rule in DEPARTMENT_RULES]


@router.post(
    "/departments/recommend",
    response_model=DepartmentRecommendationResponse,
    summary="민원 내용과 부서 목록을 매칭해 유관 부서 추천",
)
def recommend_department(
    payload: DepartmentRecommendRequest,
) -> DepartmentRecommendationResponse:
    matches = match_departments(
        texts=(
            payload.title,
            payload.content,
            payload.expectation,
            payload.location,
        ),
        suggested_department=payload.suggested_department,
    )
    candidates = [_match_response(match) for match in matches]
    return DepartmentRecommendationResponse(
        recommended=candidates[0],
        candidates=candidates,
    )


@router.post(
    "/complaints/{complaint_id}/department/recommend",
    response_model=ComplaintRoutingResponse,
    summary="민원을 부서 목록과 자동 매칭하고 추천 부서 저장",
)
def route_complaint_automatically(
    complaint_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(_require_staff),
) -> ComplaintRoutingResponse:
    complaint = db.get(Complaint, complaint_id)
    if complaint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="민원을 찾을 수 없습니다.",
        )

    matches = match_departments(
        texts=(
            complaint.title,
            complaint.content,
            complaint.expectation,
            complaint.location,
        ),
    )
    best_match = matches[0]
    department = _get_or_create_department(db, best_match.rule)
    complaint.recommended_dept = department
    db.commit()
    db.refresh(complaint)

    return ComplaintRoutingResponse(
        complaint_id=complaint.id,
        department=DepartmentResponse.model_validate(department),
        matched_keywords=list(best_match.matched_keywords),
        confidence=best_match.confidence,
    )


@router.patch(
    "/complaints/{complaint_id}/department",
    response_model=ComplaintRoutingResponse,
    summary="관리자가 민원의 유관 부서를 수동 지정",
)
def assign_department_manually(
    complaint_id: int,
    payload: DepartmentAssignmentRequest,
    db: Session = Depends(get_db),
    _: User = Depends(_require_staff),
) -> ComplaintRoutingResponse:
    complaint = db.get(Complaint, complaint_id)
    if complaint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="민원을 찾을 수 없습니다.",
        )

    rule = get_department_rule(payload.department_name)
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="부서 목록에 없는 이름입니다. GET /departments에서 이름을 확인해 주세요.",
        )

    department = _get_or_create_department(db, rule)
    complaint.recommended_dept = department
    db.commit()
    db.refresh(complaint)

    return ComplaintRoutingResponse(
        complaint_id=complaint.id,
        department=DepartmentResponse.model_validate(department),
    )


@router.get(
    "/departments/{department_name}/complaints",
    response_model=List[RoutedComplaintResponse],
    summary="부서별 배정 민원 조회",
)
def list_department_complaints(
    department_name: str,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(_require_staff),
) -> List[RoutedComplaintResponse]:
    rule = get_department_rule(department_name)
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="부서 목록에 없는 이름입니다.",
        )

    department = db.scalar(select(Department).where(Department.name == rule.name))
    if department is None:
        return []

    complaints = db.scalars(
        select(Complaint)
        .where(Complaint.recommended_dept_id == department.id)
        .order_by(Complaint.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()

    return [
        RoutedComplaintResponse(
            id=complaint.id,
            title=complaint.title,
            content=complaint.content,
            location=complaint.location,
            status=complaint.status.value,
            recommended_dept_id=complaint.recommended_dept_id,
        )
        for complaint in complaints
    ]
