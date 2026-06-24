import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# 테스트 환경 변수 설정 (기존 값이 없을 때만 기본값 적용)
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ.setdefault("USE_MOCK_AI", "true")  # 테스트 시 Mock AI 모드 강제 적용

from database import get_db
from main import app
from models import Base, User

# 데이터베이스 URL에 따른 엔진 초기화
database_url = os.environ["DATABASE_URL"]
connect_args = {}
pool_kwargs = {}
if database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    pool_kwargs["poolclass"] = StaticPool

engine = create_engine(
    database_url,
    connect_args=connect_args,
    **pool_kwargs
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 모든 테이블 생성 (pgvector 임베딩 타입은 SQLite에서 무시되거나 호환되도록 처리됨)
Base.metadata.create_all(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

def test_create_complaint_flow():
    # 1. 회원가입
    signup_resp = client.post(
        "/auth/signup",
        json={
            "email": "user@example.com",
            "password": "password123!",
            "nickname": "홍길동",
            "student_id": "20261122",
        }
    )
    assert signup_resp.status_code == 201

    # 2. 로그인 및 토큰 획득
    login_resp = client.post(
        "/auth/login",
        json={
            "email": "user@example.com",
            "password": "password123!"
        }
    )
    assert login_resp.status_code == 200
    access_token = login_resp.json()["access_token"]

    # 3. 민원 등록 요청 (POST /complaints)
    complaint_payload = {
        "title": "IT관 3층 복도 전등 고장",
        "content": "IT관 3층 화장실 옆 복도 전등이 깜빡거립니다. 교체해 주세요.",
        "desired_solution": "빠른 전등 전구 교체",
        "location_name": "IT관 3층 복도",
        "latitude": 37.12345678,
        "longitude": 127.87654321,
        "image_url": "http://example.com/attachments/light.jpg",
        "is_anonymous": False
    }

    headers = {"Authorization": f"Bearer {access_token}"}
    response = client.post("/complaints", json=complaint_payload, headers=headers)
    
    assert response.status_code == 201
    data = response.json()
    
    # 4. 반환값 검증
    assert data["title"] == "IT관 3층 복도 전등 고장"
    assert data["content"] == "IT관 3층 화장실 옆 복도 전등이 깜빡거립니다. 교체해 주세요."
    assert data["expectation"] == "빠른 전등 전구 교체"
    assert data["location"] == "IT관 3층 복도"
    assert data["latitude"] == 37.12345678
    assert data["longitude"] == 127.87654321
    assert data["is_anonymous"] is False
    assert data["status"] == "received"
    
    # 5. AI 분석 필드 검증 (Mock 모드가 적용되었으므로 키워드 기반으로 매칭된 시설관리 관련 정보여야 함)
    assert data["ai_category"] == "시설"
    assert data["ai_department"] == "시설관리팀"
    assert data["ai_urgency"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    assert "MOCK" in data["ai_summary"]
    assert isinstance(data["ai_keywords"], list)
    assert len(data["ai_keywords"]) > 0
