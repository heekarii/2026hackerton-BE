import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from auth import get_current_user
from database import get_db
from models import (
    AdminAction,
    Category,
    Complaint,
    ComplaintAttachment,
    ComplaintStatus,
    Department,
    User,
    UserRole,
)
from routers.my_page import router


@compiles(JSONB, "sqlite")
def compile_jsonb_for_sqlite(_type, _compiler, **_kwargs):
    return "JSON"


def _build_test_client():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in (
        User.__table__,
        Department.__table__,
        Category.__table__,
        Complaint.__table__,
        ComplaintAttachment.__table__,
        AdminAction.__table__,
    ):
        table.create(engine, checkfirst=True)

    testing_session = sessionmaker(bind=engine)
    with testing_session() as db:
        student = User(
            email="owner@example.com",
            hashed_password="hashed",
            nickname="민원인",
            student_id="20260001",
            role=UserRole.STUDENT,
        )
        other_student = User(
            email="other@example.com",
            hashed_password="hashed",
            nickname="다른학생",
            student_id="20260002",
            role=UserRole.STUDENT,
        )
        admin = User(
            email="admin@example.com",
            hashed_password="hashed",
            nickname="관리자",
            role=UserRole.ADMIN,
        )
        department = Department(
            name="정보통신팀",
            description="네트워크 및 전산 시스템 운영",
        )
        db.add_all([student, other_student, admin, department])
        db.flush()

        received = Complaint(
            user_id=student.id,
            title="와이파이 연결 문제",
            content="도서관 와이파이가 계속 끊깁니다.",
            expectation="네트워크 점검을 요청합니다.",
            is_anonymous=True,
            status=ComplaintStatus.RECEIVED,
            location="중앙도서관",
            occurred_at=datetime.datetime(2026, 6, 24, 9, 0),
            ai_expected_days="3일",
        )
        in_progress = Complaint(
            user_id=student.id,
            title="앱 로그인 오류",
            content="학교 앱에 로그인할 수 없습니다.",
            status=ComplaintStatus.IN_PROGRESS,
            location="온라인",
            occurred_at=datetime.datetime(2026, 6, 23, 10, 0),
            recommended_dept=department,
            ai_expected_days="1일",
        )
        other_complaint = Complaint(
            user_id=other_student.id,
            title="다른 사용자의 민원",
            content="현재 사용자 목록에 보이면 안 됩니다.",
            status=ComplaintStatus.RESOLVED,
            location="학생회관",
            occurred_at=datetime.datetime(2026, 6, 22, 10, 0),
        )
        db.add_all([received, in_progress, other_complaint])
        db.flush()

        in_progress.attachments.append(
            ComplaintAttachment(
                file_url="https://example.com/error.png",
                file_type="image/png",
            )
        )
        in_progress.actions.append(
            AdminAction(
                admin_id=admin.id,
                response_content="정보통신팀에서 원인을 확인하고 있습니다.",
                status_to=ComplaintStatus.IN_PROGRESS,
            )
        )
        db.commit()
        current_user_id = student.id
        in_progress_id = in_progress.id
        other_complaint_id = other_complaint.id

    current_user = User(
        id=current_user_id,
        email="owner@example.com",
        hashed_password="hashed",
        nickname="민원인",
        student_id="20260001",
        role=UserRole.STUDENT,
    )

    def override_get_db():
        with testing_session() as db:
            yield db

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: current_user
    return TestClient(app), in_progress_id, other_complaint_id


def test_my_complaints_only_returns_current_users_complaints():
    client, _, _ = _build_test_client()

    response = client.get("/users/me/complaints")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["summary"]["received"] == 1
    assert payload["summary"]["in_progress"] == 1
    assert all(
        item["title"] != "다른 사용자의 민원" for item in payload["items"]
    )


def test_my_complaints_supports_status_filter():
    client, _, _ = _build_test_client()

    response = client.get(
        "/users/me/complaints",
        params={"status": "in_progress"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["status"]["label"] == "처리 중"
    assert payload["items"][0]["status"]["progress"] == 60
    assert payload["items"][0]["department_name"] == "정보통신팀"


def test_my_complaint_detail_returns_progress_timeline():
    client, complaint_id, _ = _build_test_client()

    response = client.get(f"/users/me/complaints/{complaint_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["department_name"] == "정보통신팀"
    assert payload["expected_days"] == "1일"
    assert len(payload["attachments"]) == 1
    assert [event["event_type"] for event in payload["timeline"]] == [
        "submitted",
        "admin_action",
    ]
    assert payload["timeline"][1]["actor_nickname"] == "관리자"


def test_cannot_read_another_users_complaint():
    client, _, other_complaint_id = _build_test_client()

    response = client.get(
        f"/users/me/complaints/{other_complaint_id}"
    )

    assert response.status_code == 404
