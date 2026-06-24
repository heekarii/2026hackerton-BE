from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="2026 Hackathon API",
    description="2026년 해커톤 백엔드 서버 API 문서입니다.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS 설정 (프론트엔드 개발 시 CORS 에러 방지를 위해 기본 허용 설정)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 해커톤 등 프로토타이핑을 위해 전체 허용. 실서버 배포 시 변경 필요
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", tags=["Root"])
def read_root():
    """
    서버 연결 확인을 위한 루트 엔드포인트입니다.
    """
    return {"message": "Welcome to 2026 Hackathon Backend API Server!"}

@app.get("/health", tags=["System"])
def health_check():
    """
    서버 헬스 체크 엔드포인트입니다.
    """
    return {"status": "healthy"}
