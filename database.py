import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# 환경변수로부터 데이터베이스 URL 로드 (기본값 제공)
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://postgres:postgres@localhost:5432/campus_complaints"
)

# SQLAlchemy 엔진 생성
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # 연결 유효성 자동 체크
)

# 세션 팩토리 생성
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Declarative Base 클래스 생성
Base = declarative_base()

# FastAPI 의존성 주입을 위한 DB 세션 생성 헬퍼 함수
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
