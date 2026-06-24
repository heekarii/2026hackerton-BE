import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import get_db
from models import Category, Complaint, Department, User
from routers.departments import _require_staff, router
from services.department_routing import (
    DEFAULT_DEPARTMENT_NAME,
    get_department_rule,
    match_departments,
)


app = FastAPI()
app.include_router(router)
client = TestClient(app)


@compiles(JSONB, "sqlite")
def compile_jsonb_for_sqlite(_type, _compiler, **_kwargs):
    return "JSON"


def test_facility_complaint_matches_facility_department():
    matches = match_departments(
        texts=(
            "공학관 에어컨 고장",
            "강의실 에어컨과 조명이 작동하지 않습니다.",
            "빠른 시설 수리를 바랍니다.",
            "공학관 301호",
        )
    )

    assert matches[0].rule.name == "시설관리팀"
    assert "에어컨" in matches[0].matched_keywords
    assert matches[0].confidence == 1.0


def test_department_alias_is_matched():
    rule = get_department_rule("전산팀")

    assert rule is not None
    assert rule.name == "정보통신팀"


def test_ai_suggested_department_gets_extra_weight():
    matches = match_departments(
        texts=("인터넷 연결 문제",),
        suggested_department="정보화팀",
    )

    assert matches[0].rule.name == "정보통신팀"
    assert matches[0].score >= 4


def test_unknown_complaint_falls_back_to_student_support():
    matches = match_departments(texts=("분류하기 어려운 요청입니다.",))

    assert matches[0].rule.name == DEFAULT_DEPARTMENT_NAME
    assert matches[0].confidence == 0.0


def test_department_catalog_api_returns_matching_list():
    response = client.get("/departments")

    assert response.status_code == 200
    names = [department["name"] for department in response.json()]
    assert "시설관리팀" in names
    assert "정보통신팀" in names


def test_department_recommend_api_returns_candidates():
    response = client.post(
        "/departments/recommend",
        json={
            "title": "도서관 와이파이가 안 됩니다",
            "content": "인터넷과 네트워크 연결이 계속 끊깁니다.",
            "location": "중앙도서관",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["recommended"]["department"]["name"] == "정보통신팀"
    assert "와이파이" in payload["recommended"]["matched_keywords"]


def test_admin_can_route_complaint_and_save_department():
    import os
    database_url = os.getenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
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
    for table in (
        User.__table__,
        Department.__table__,
        Category.__table__,
        Complaint.__table__,
    ):
        table.create(engine, checkfirst=True)

    testing_session = sessionmaker(bind=engine)
    with testing_session() as db:
        complaint = Complaint(
            user_id=1,
            title="강의실 조명 고장",
            content="조명이 꺼져서 수업하기 어렵습니다.",
            expectation="시설 수리를 요청합니다.",
            location="공학관 201호",
            occurred_at=datetime.datetime.now(),
        )
        db.add(complaint)
        db.commit()
        complaint_id = complaint.id

    def override_get_db():
        with testing_session() as db:
            yield db

    routing_app = FastAPI()
    routing_app.include_router(router)
    routing_app.dependency_overrides[get_db] = override_get_db
    routing_app.dependency_overrides[_require_staff] = lambda: None
    routing_client = TestClient(routing_app)

    response = routing_client.post(
        f"/complaints/{complaint_id}/department/recommend"
    )

    assert response.status_code == 200
    assert response.json()["department"]["name"] == "시설관리팀"

    with testing_session() as db:
        saved_complaint = db.get(Complaint, complaint_id)
        saved_department = db.get(
            Department, saved_complaint.recommended_dept_id
        )
        assert saved_department.name == "시설관리팀"
