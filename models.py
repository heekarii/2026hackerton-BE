import datetime
from typing import List, Optional
import enum
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Text, Enum as SQLEnum, Index, Numeric, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from database import Base

class UserRole(str, enum.Enum):
    STUDENT = "student"
    ADMIN = "admin"
    STAFF = "staff"

class ComplaintStatus(str, enum.Enum):
    RECEIVED = "received"       # 접수됨
    IN_PROGRESS = "in_progress" # 처리중
    RESOLVED = "resolved"       # 해결됨
    REJECTED = "rejected"       # 반려됨

class User(Base):
    """
    사용자 정보 테이블 (학생 및 교직원/관리자)
    """
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    student_id: Mapped[Optional[str]] = mapped_column(String(50), unique=True, index=True, nullable=True) # 학번 혹은 사번
    nickname: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole), default=UserRole.STUDENT, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)
    
    # 릴레이션 관계 설정
    complaints: Mapped[List["Complaint"]] = relationship(back_populates="user")
    admin_actions: Mapped[List["AdminAction"]] = relationship(back_populates="admin")


class Category(Base):
    """
    민원 분류 카테고리 (예: 시설물 장애, 장학/학사, 위생, 안전 등)
    """
    __tablename__ = "categories"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    complaints: Mapped[List["Complaint"]] = relationship(back_populates="category")


class Department(Base):
    """
    담당 부서 정보 (예: 학생지원팀, 시설관리팀, IT 서비스 데스크 등)
    """
    __tablename__ = "departments"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    complaints: Mapped[List["Complaint"]] = relationship(
        back_populates="recommended_dept",
        foreign_keys="[Complaint.recommended_dept_id]"
    )


class Complaint(Base):
    """
    민원 사항 테이블 (핵심 요구사항 반영)
    """
    __tablename__ = "complaints"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # [요구사항 4] 민원사항과 개선 희망 사항 분리 저장
    content: Mapped[str] = mapped_column(Text, nullable=False)          # 민원사항 본문
    expectation: Mapped[Optional[str]] = mapped_column(Text, nullable=True) # 개선 희망 사항
    
    # [요구사항 2] 익명 민원 등록 여부
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # [요구사항 5] 민원 처리 상태 관리
    status: Mapped[ComplaintStatus] = mapped_column(SQLEnum(ComplaintStatus), default=ComplaintStatus.RECEIVED, nullable=False)
    
    # [요구사항 3] 장소 및 시간대 저장 컬럼
    location: Mapped[str] = mapped_column(String(255), nullable=False)       # 장소 (예: "IT관 3층 복도")
    occurred_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)  # 민원 발생 시간대
    
    # GPS 위도/경도
    latitude: Mapped[Optional[float]] = mapped_column(Numeric(10, 8), nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Numeric(11, 8), nullable=True)
    
    # [요구사항 8] AI 민원 분석 결과 컬럼들
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories.id"), nullable=True)
    urgency_score: Mapped[Optional[float]] = mapped_column(Numeric(3, 2), nullable=True) # 긴급도 점수 (1.00 ~ 5.00)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False) # 민감 민원 여부 (개인정보 노출, 언어폭력 등)
    recommended_dept_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id"), nullable=True) # AI 추천 담당 부서
    
    # AI 상세 분석 필드들
    ai_category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ai_subcategory: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ai_sentiment: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ai_urgency: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ai_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ai_risk_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ai_department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ai_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_keywords: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    ai_expected_days: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ai_recommended_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # [요구사항 9] AI 유사도 검색을 위한 pgvector 임베딩 컬럼 (1536차원)
    embedding: Mapped[Optional[Vector]] = mapped_column(Vector(1536), nullable=True)

    # 위치 좌표 (지도 시각화용)
    latitude: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Numeric, nullable=True)

    # OpenAI 분석 결과 컬럼들 (분석 서비스가 등록 후 채움)
    # NOTE: 실제 Supabase DB 스키마에 이미 존재하던 컬럼들을 models.py 에 반영한 것.
    #       ai_sensitive 는 NOT NULL 이라 등록 시점 누락을 막기 위해 기본값 False 를 둔다.
    ai_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ai_category: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ai_subcategory: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ai_sentiment: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ai_urgency: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ai_risk_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ai_department: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ai_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_keywords: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    ai_expected_days: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ai_recommended_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)
    
    # 릴레이션 관계 설정
    user: Mapped["User"] = relationship(back_populates="complaints")
    category: Mapped[Optional["Category"]] = relationship(back_populates="complaints")
    recommended_dept: Mapped[Optional["Department"]] = relationship(
        back_populates="complaints",
        foreign_keys=[recommended_dept_id]
    )
    
    # [요구사항 3] 사진 첨부 릴레이션
    attachments: Mapped[List["ComplaintAttachment"]] = relationship(back_populates="complaint", cascade="all, delete-orphan")
    # [요구사항 6] 관리자 답변/처리 내역
    actions: Mapped[List["AdminAction"]] = relationship(back_populates="complaint", cascade="all, delete-orphan")
    # [요구사항 7] 해결 후 만족도 피드백
    feedback: Mapped[Optional["Feedback"]] = relationship(back_populates="complaint", uselist=False, cascade="all, delete-orphan")


# [요구사항 12] 동일 사용자의 반복 도배 방지 필터링 최적화를 위한 복합 인덱스 지정
# 최근 N분 내 작성 글 수를 확인할 때 쿼리 속도 보장
Index("idx_complaints_user_created_at", Complaint.user_id, Complaint.created_at)


class ComplaintAttachment(Base):
    """
    [요구사항 3] 민원 사진 및 파일 첨부 테이블
    """
    __tablename__ = "complaint_attachments"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    complaint_id: Mapped[int] = mapped_column(ForeignKey("complaints.id"), nullable=False)
    file_url: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False) # e.g. "image/jpeg", "image/png"
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    
    complaint: Mapped["Complaint"] = relationship(back_populates="attachments")


class AdminAction(Base):
    """
    [요구사항 6] 관리자 답변 및 상태 변경 히스토리 테이블
    """
    __tablename__ = "admin_actions"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    complaint_id: Mapped[int] = mapped_column(ForeignKey("complaints.id"), nullable=False)
    admin_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    response_content: Mapped[str] = mapped_column(Text, nullable=False) # 관리자 처리 답변 내용
    status_to: Mapped[ComplaintStatus] = mapped_column(SQLEnum(ComplaintStatus), nullable=False) # 변경 후 상태
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)
    
    complaint: Mapped["Complaint"] = relationship(back_populates="actions")
    admin: Mapped["User"] = relationship(back_populates="admin_actions")


class Feedback(Base):
    """
    [요구사항 7] 해결 후 학생이 등록하는 만족도 피드백 테이블
    """
    __tablename__ = "feedbacks"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    complaint_id: Mapped[int] = mapped_column(ForeignKey("complaints.id"), unique=True, nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False) # 만족도 점수 (1 ~ 5)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True) # 추가 건의 사항
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    
    complaint: Mapped["Complaint"] = relationship(back_populates="feedback")


class Report(Base):
    """
    [요구사항 11] 학기별/연말 리포트 테이블
    """
    __tablename__ = "reports"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False) # 예: "2026학년도 1학기 통계 보고서"
    term: Mapped[str] = mapped_column(String(50), nullable=False)       # 예: "2026-1", "2026-annual"
    summary: Mapped[str] = mapped_column(Text, nullable=False)          # 총평 및 요약
    statistics_json: Mapped[dict] = mapped_column(JSON, nullable=False) # 카테고리별/시간대별/부서별 상세 통계 수치
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, nullable=False)
