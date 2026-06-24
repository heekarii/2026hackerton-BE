import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from auth import get_current_user
from database import get_db
from models import (
    AdminAction,
    Category,
    Complaint,
    ComplaintStatus,
    Department,
    User,
    UserRole,
)
from routers.admin_complaints import require_admin_or_staff, router


def _setup_app(current_role: UserRole = UserRole.ADMIN):
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
        AdminAction.__table__,
    ):
        table.create(engine, checkfirst=True)

    testing_session = sessionmaker(bind=engine)
    with testing_session() as db:
        student = User(
            email="student@example.com",
            hashed_password="hashed",
            nickname="민원인",
            student_id="20260001",
            role=UserRole.STUDENT,
        )
        actor = User(
            email="actor@example.com",
            hashed_password="hashed",
            nickname="담당자",
            role=current_role,
        )
        department = Department(
            name="시설관리팀",
            description="교내 시설 유지보수",
        )
        db.add_all([student, actor, department])
        db.flush()
        complaint = Complaint(
            user_id=student.id,
            title="강의실 조명 고장",
            content="조명이 켜지지 않습니다.",
            expectation="빠른 수리를 요청합니다.",
            status=ComplaintStatus.RECEIVED,
            location="공학관 201호",
            occurred_at=datetime.datetime(2026, 6, 24, 10, 0),
        )
        db.add(complaint)
        db.commit()
        actor_id = actor.id
        department_id = department.id
        complaint_id = complaint.id

    def override_get_db():
        with testing_session() as db:
            yield db

    def override_actor():
        with testing_session() as db:
            return db.get(User, actor_id)

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = override_get_db
    if current_role in (UserRole.ADMIN, UserRole.STAFF):
        app.dependency_overrides[require_admin_or_staff] = override_actor
    else:
        app.dependency_overrides[get_current_user] = override_actor

    return (
        TestClient(app),
        testing_session,
        complaint_id,
        department_id,
    )


def test_admin_can_change_status_reply_and_department():
    client, testing_session, complaint_id, department_id = _setup_app()

    response = client.patch(
        f"/admin/complaints/{complaint_id}/process",
        json={
            "status": "in_progress",
            "response_content": "시설관리팀에서 현장을 확인하고 있습니다.",
            "department_id": department_id,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "in_progress"
    assert payload["department_name"] == "시설관리팀"
    assert payload["action"]["admin_nickname"] == "담당자"

    with testing_session() as db:
        complaint = db.get(Complaint, complaint_id)
        action = db.scalar(
            db.query(AdminAction).filter(
                AdminAction.complaint_id == complaint_id
            ).statement
        )
        assert complaint.status == ComplaintStatus.IN_PROGRESS
        assert complaint.recommended_dept_id == department_id
        assert action.response_content == "시설관리팀에서 현장을 확인하고 있습니다."


def test_staff_role_is_allowed():
    client, _, complaint_id, _ = _setup_app(UserRole.STAFF)

    response = client.patch(
        f"/admin/complaints/{complaint_id}/process",
        json={
            "status": "resolved",
            "response_content": "조명 교체를 완료했습니다.",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "resolved"


def test_student_role_is_forbidden():
    client, _, complaint_id, _ = _setup_app(UserRole.STUDENT)

    response = client.patch(
        f"/admin/complaints/{complaint_id}/process",
        json={
            "status": "in_progress",
            "response_content": "처리 중입니다.",
        },
    )

    assert response.status_code == 403


def test_invalid_status_transition_is_rejected():
    client, _, complaint_id, _ = _setup_app()
    first_response = client.patch(
        f"/admin/complaints/{complaint_id}/process",
        json={
            "status": "resolved",
            "response_content": "처리를 완료했습니다.",
        },
    )
    assert first_response.status_code == 200

    response = client.patch(
        f"/admin/complaints/{complaint_id}/process",
        json={
            "status": "rejected",
            "response_content": "완료된 민원을 반려 상태로 바꿉니다.",
        },
    )

    assert response.status_code == 409


def test_admin_action_history_is_returned_in_order():
    client, _, complaint_id, _ = _setup_app()
    for next_status, message in (
        ("in_progress", "처리를 시작했습니다."),
        ("resolved", "처리를 완료했습니다."),
    ):
        response = client.patch(
            f"/admin/complaints/{complaint_id}/process",
            json={
                "status": next_status,
                "response_content": message,
            },
        )
        assert response.status_code == 200

    response = client.get(
        f"/admin/complaints/{complaint_id}/actions"
    )

    assert response.status_code == 200
    actions = response.json()
    assert [action["status_to"] for action in actions] == [
        "in_progress",
        "resolved",
    ]
    assert actions[1]["response_content"] == "처리를 완료했습니다."
