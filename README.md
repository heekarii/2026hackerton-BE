# 2026 Hackathon BE (백엔드 - 캠퍼스 민원 분석 플랫폼)

FastAPI와 PostgreSQL + SQLAlchemy DB 설정이 완료된 백엔드 템플릿입니다.

## 기술 스택
- **Language**: Python 3.x
- **Framework**: FastAPI
- **Database**: PostgreSQL (with pgvector)
- **ORM**: SQLAlchemy 2.0
- **Migration**: Alembic

---

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

### 3. 데이터베이스 구성 (PostgreSQL + pgvector)
로컬 또는 Docker 환경에 PostgreSQL이 기동 중이어야 하며, `pgvector` 확장이 지원되어야 합니다.
기본 접속 URL은 `postgresql://postgres:postgres@localhost:5432/campus_complaints` 입니다.

*만약 접속 계정이나 DB명이 다른 경우 환경변수를 지정하여 실행하세요:*
```bash
export DATABASE_URL="postgresql://user:password@localhost:5432/dbname"
```

#### Alembic을 이용한 마이그레이션 실행
Alembic 초기 마이그레이션 생성 및 DB 반영 명령어:
```bash
# 마이그레이션 버전 생성
alembic revision --autogenerate -m "Initial schema"

# DB에 테이블 및 pgvector 확장 적용
alembic upgrade head
```

### 4. 로컬 서버 실행
```bash
uvicorn main:app --reload
```

---

## 데이터베이스 설계 검증
프로젝트 루트에서 ORM 설계의 논리적 오류(관계 설정, 외래키 연결 등)를 검증하기 위한 테스트 코드가 포함되어 있습니다.
```bash
python test_db.py

## 로그인 / 회원가입 API

실행 전 `.env.example`을 참고해 환경변수를 설정하세요. 특히
`DATABASE_URL`과 `JWT_SECRET_KEY`는 저장소에 커밋하지 않습니다.

| Method | Path | 설명 |
| --- | --- | --- |
| POST | `/auth/signup` | 학생 회원가입 |
| POST | `/auth/login` | JSON 로그인 및 JWT 발급 |
| POST | `/auth/token` | Swagger OAuth2 로그인 |
| GET | `/auth/me` | Bearer 토큰으로 내 정보 조회 |

Swagger의 **Authorize** 버튼에서는 username 칸에 이메일을 입력합니다.

## 유관 부서 라우팅 API

민원 제목, 내용, 개선 희망 사항, 장소를 부서별 키워드 목록과 비교해
가장 적합한 부서를 추천합니다. OpenAI 분석 결과의 부서명을
`suggested_department`로 전달하면 목록의 이름 또는 별칭과 매칭해
추천 점수에 반영합니다.

| Method | Path | 설명 |
| --- | --- | --- |
| GET | `/departments` | 부서, 키워드, 별칭 목록 |
| POST | `/departments/recommend` | 저장 없이 추천 후보 확인 |
| POST | `/complaints/{id}/department/recommend` | 관리자 자동 매칭 및 저장 |
| PATCH | `/complaints/{id}/department` | 관리자 수동 부서 지정 |
| GET | `/departments/{name}/complaints` | 부서별 배정 민원 조회 |
```

---

## 핵심 기능 구현 가이드 (SQLAlchemy 2.0 예시)

### 1. [요구사항 9] AI 유사도 검색 (동일/유사 민원 탐색)
`pgvector`를 사용해 입력된 임베딩(예: OpenAI embedding 1536차원)과 가장 유사한 기존 민원 5개를 코사인 유사도 기반으로 검색합니다.

```python
from sqlalchemy import select
from models import Complaint

# 새로운 민원 데이터의 1536차원 임베딩 벡터 (예시)
new_embedding = [0.012, -0.004, ..., 0.089] 

# 코사인 유사도 오름차순 검색 (거리가 가까울수록 유사함)
stmt = (
    select(Complaint)
    .order_by(Complaint.embedding.cosine_distance(new_embedding))
    .limit(5)
)
results = db.scalars(stmt).all()
```

### 2. [요구사항 12] 동일 사용자의 반복 도배 방지
특정 사용자(`user_id`)가 최근 5분 이내에 작성한 민원이 존재하는지 인덱스(`idx_complaints_user_created_at`)를 태워 신속하게 조회합니다.

```python
import datetime
from sqlalchemy import select, func
from models import Complaint

limit_time = datetime.datetime.utcnow() - datetime.timedelta(minutes=5)

stmt = (
    select(func.count(Complaint.id))
    .where(Complaint.user_id == current_user_id)
    .where(Complaint.created_at >= limit_time)
)
complaint_count = db.scalar(stmt)

if complaint_count > 0:
    raise HTTPException(status_code=429, detail="도배 방지를 위해 5분 후 다시 시도해 주세요.")
```

### 3. [요구사항 10] 위치/시간대별 통계 쿼리
```python
from sqlalchemy import select, func
from models import Complaint

# 위치별 민원 접수 건수 집계
stmt = (
    select(Complaint.location, func.count(Complaint.id).label("count"))
    .group_by(Complaint.location)
    .order_by(func.count(Complaint.id).desc())
)
stats = db.execute(stmt).all()
```
