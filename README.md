# 2026 Hackathon BE (백엔드)

FastAPI와 Swagger 설정이 완료된 백엔드 템플릿입니다.

## 기술 스택
- **Language**: Python 3.x
- **Framework**: FastAPI
- **Web Server**: Uvicorn

## 실행 방법

### 1. 가상환경 생성 및 활성화
```bash
# 가상환경 생성
python3 -m venv .venv

# 가상환경 활성화 (macOS/Linux)
source .venv/bin/activate
```

### 2. 패키지 설치
```bash
pip install -r requirements.txt
```

### 3. 로컬 서버 실행
```bash
uvicorn main:app --reload
```

## API 문서 확인 (Swagger)
서버 실행 후 브라우저에서 아래 주소로 접속하면 Swagger UI로 정의된 API 문서를 확인하고 테스트할 수 있습니다.
- **Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
