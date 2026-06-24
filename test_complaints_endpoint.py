import os
import json
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# 테스트 환경 변수 설정 (기존 값이 없을 때만 기본값 적용)
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key")
os.environ.setdefault("USE_MOCK_AI", "true")  # 우선 Mock AI 모드로 안전하게 테스트

from database import get_db
from main import app
from models import Base

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
Base.metadata.create_all(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

def run_integration_test():
    print("🚀 [1단계] 테스트용 유저 회원가입 진행...")
    signup_resp = client.post(
        "/auth/signup",
        json={
            "email": "test-student@univ.ac.kr",
            "password": "securepassword123!",
            "nickname": "해커톤도전자",
            "student_id": "20269999"
        }
    )
    if signup_resp.status_code != 201:
        print(f"❌ 회원가입 실패: {signup_resp.json()}")
        return
    print("✅ 회원가입 성공!")

    print("\n🚀 [2단계] 로그인 및 JWT 발급...")
    login_resp = client.post(
        "/auth/login",
        json={
            "email": "test-student@univ.ac.kr",
            "password": "securepassword123!"
        }
    )
    if login_resp.status_code != 200:
        print(f"❌ 로그인 실패: {login_resp.json()}")
        return
    
    access_token = login_resp.json()["access_token"]
    print("✅ 로그인 성공 및 토큰 취득!")

    print("\n🚀 [3단계] 통합 민원 등록(POST /complaints) 및 AI 분석 연동 수행...")
    complaint_payload = {
        "title": "기숙사 복도 쓰레기장 악취 및 분리수거함 청소 요청",
        "content": "기숙사 A동 2층 복도 분리수거함 근처에 쓰레기가 너무 방치되어 있고 악취가 심합니다. 미화팀 분들께서 청소해 주시면 감사하겠습니다.",
        "desired_solution": "분리수거함 주변 청소 및 악취 제거 탈취제 분사",
        "location_name": "기숙사 A동 2층 복도",
        "latitude": 37.5665,
        "longitude": 126.9780,
        "image_url": "http://example.com/images/dorm_trash.png",
        "is_anonymous": False
    }

    headers = {"Authorization": f"Bearer {access_token}"}
    response = client.post("/complaints", json=complaint_payload, headers=headers)

    if response.status_code != 201:
        print(f"❌ 민원 등록 실패: {response.status_code}")
        print(response.json())
        return
    
    print("✅ 민원 등록 및 AI 분석 결과 DB 저장 성공!")
    
    print("\n📦 [최종 결과] DB에서 직렬화되어 반환된 민원 & AI 분석 정보:")
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))

if __name__ == "__main__":
    run_integration_test()
