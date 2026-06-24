import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# 테스트 환경 변수 설정
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "test-secret-key"
os.environ["USE_MOCK_AI"] = "true"  # 테스트 시 Mock AI 모드 강제 적용

from database import get_db
from main import app
from models import Base, User, Complaint, ComplaintAttachment
from schemas import ImageAnalysisResponse
from services.email_verification import create_verification_token

# In-memory SQLite 설정
engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 모든 테이블 생성
Base.metadata.create_all(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@pytest.fixture(name="db_session")
def fixture_db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(name="auth_headers")
def fixture_auth_headers():
    # 테스트 사용자 생성 및 로그인
    email = "vision_user@example.com"
    password = "password123!"
    
    # 중복 가입 방지 처리를 위해 db 확인
    db = TestingSessionLocal()
    user = db.scalar(select(User).where(User.email == email))
    if not user:
        client.post(
            "/auth/signup",
            json={
                "email": email,
                "password": password,
                "nickname": "비전테스터",
                "student_id": "20269999",
                "verification_token": create_verification_token(email),
            }
        )
    db.close()

    # 로그인 진행
    login_resp = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": password
        }
    )
    access_token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {access_token}"}

def test_analyze_image_without_complaint_id():
    """
    complaint_id 없이 이미지 분석을 요청할 경우, Mock 이미지 분석 결과만 제대로 반환되는지 확인합니다.
    """
    image_url = "http://example.com/images/dirty_trash.jpg"
    payload = {
        "image_url": image_url,
        "complaint_id": None
    }
    
    response = client.post("/openai/analyze-image", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert data["image_category"] == "쓰레기"
    assert "쓰레기 봉투" in data["detected_objects"]
    assert data["danger_level"] == "MEDIUM"
    assert "[MOCK]" in data["image_description"]
    assert data["photo_based_category_hint"] == "총무팀"
    assert "청소 미화 담당" in data["recommended_action"]


def test_analyze_image_with_invalid_complaint_id():
    """
    존재하지 않는 complaint_id를 전달하는 경우, 404 Error를 응답하는지 확인합니다.
    """
    payload = {
        "image_url": "http://example.com/images/broken_window.jpg",
        "complaint_id": 99999  # 존재하지 않는 ID
    }
    
    response = client.post("/openai/analyze-image", json=payload)
    assert response.status_code == 404
    assert "민원을 찾을 수 없습니다" in response.json()["detail"]


def test_analyze_image_with_valid_complaint_id(auth_headers, db_session):
    """
    유효한 complaint_id를 전달하는 경우, 이미지 분석 결과가 DB(ComplaintAttachment)에 올바르게 저장되는지 확인합니다.
    """
    # 1. 민원 생성
    complaint_payload = {
        "title": "기숙사 화장실 세면대 오염",
        "content": "세면대 상태가 너무 지저분합니다. 청소 부탁드려요.",
        "desired_solution": "세면대 물때 청소",
        "location_name": "기숙사 화장실",
        "latitude": 37.1234,
        "longitude": 127.8765,
        "image_url": "http://example.com/images/restroom_toilet.jpg",
        "is_anonymous": False
    }
    
    complaint_resp = client.post("/complaints", json=complaint_payload, headers=auth_headers)
    assert complaint_resp.status_code == 201
    complaint_id = complaint_resp.json()["id"]
    
    # 2. 이미지 분석 요청 (생성된 민원의 이미지 URL과 매칭)
    analysis_payload = {
        "image_url": "http://example.com/images/restroom_toilet.jpg",
        "complaint_id": complaint_id
    }
    
    response = client.post("/openai/analyze-image", json=analysis_payload)
    assert response.status_code == 200
    
    # 3. 반환값 검증
    data = response.json()
    assert data["image_category"] == "청결 문제"
    assert "세면대 물때" in data["detected_objects"]
    assert data["danger_level"] == "MEDIUM"
    
    # 4. DB 검증: ComplaintAttachment 테이블에 Vision 분석 결과가 제대로 저장되었는지 확인
    # /complaints 생성 시 이미 attachment가 하나 등록되어 있을 것이므로, 그것을 불러옴
    attachment = db_session.scalar(
        select(ComplaintAttachment)
        .where(
            ComplaintAttachment.complaint_id == complaint_id,
            ComplaintAttachment.file_url == "http://example.com/images/restroom_toilet.jpg"
        )
    )
    assert attachment is not None
    assert attachment.image_category == "청결 문제"
    assert "세면대 물때" in attachment.detected_objects
    assert attachment.danger_level == "MEDIUM"
    assert "[MOCK]" in attachment.image_description
    assert attachment.photo_based_category_hint == "총무팀"
    assert "위생 점검 및 바닥 물청소" in attachment.recommended_action
    
    # 5. 다른 새로운 이미지 URL을 전달하여 신규 ComplaintAttachment 레코드가 자동 생성되는지 확인
    new_image_url = "http://example.com/images/broken_facility.jpg"
    new_analysis_payload = {
        "image_url": new_image_url,
        "complaint_id": complaint_id
    }
    
    response_new = client.post("/openai/analyze-image", json=new_analysis_payload)
    assert response_new.status_code == 200
    
    # 새로운 첨부파일이 DB에 등록되었는지 확인
    new_attachment = db_session.scalar(
        select(ComplaintAttachment)
        .where(
            ComplaintAttachment.complaint_id == complaint_id,
            ComplaintAttachment.file_url == new_image_url
        )
    )
    assert new_attachment is not None
    assert new_attachment.image_category == "시설 파손"
    assert new_attachment.file_type == "image/jpeg"
    assert new_attachment.photo_based_category_hint == "시설관리팀"
