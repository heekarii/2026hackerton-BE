import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.openai_analysis_endpoint import router as openai_router

from routers.auth import router as auth_router
from routers.complaints import router as complaints_router
from routers.feedback import router as feedback_router
from routers.uploads import router as uploads_router


app = FastAPI(
    title="2026 Hackathon API",
    description="캠퍼스 민원 분석 플랫폼 API",
    version="1.0.0",
    openapi_url=os.getenv("OPENAPI_URL", "/openapi.json"),
    docs_url=os.getenv("DOCS_URL", "/docs"),
    redoc_url=os.getenv("REDOC_URL", "/redoc"),
)
app.include_router(openai_router, prefix="/openai")

cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,https://2026hackerton-fe.vercel.app").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(complaints_router)
app.include_router(feedback_router)
app.include_router(uploads_router)


@app.get("/", tags=["Root"])
def read_root():
    return {"message": "Welcome to 2026 Hackathon Backend API Server!"}


@app.get("/health", tags=["System"])
def health_check():
    return {"status": "healthy"}
