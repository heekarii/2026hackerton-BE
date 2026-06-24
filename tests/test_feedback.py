import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from auth import get_current_user
from database import get_db
from models import (
    Category,
    Complaint,
    ComplaintStatus,
    Feedback,
    User,
    UserRole,
)
from routers.feedback import router


def _setup_app(complaint_status=ComplaintStatus.RESOLVED):
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
        Category.__table__,
        Complaint.__table__,
        Feedback.__table__,
    ):
        table.create(engine, checkfirst=True)

    testing_session = sessionmaker(bind=engine)
    with testing_session() as db:
        owner = User(
            email="owner@example.com",
            hashed_password="hashed",
            nickname="민원인",
            student_id="20260001",
            role=UserRole.STUDENT,
        )
        other_user = User(
            email="other@example.com",
            hashed_password="hashed",
            nickname="다른학생",
            student_id="20260002",
            role=UserRole.STUDENT,
        )
        db.add_all([owner, other_user])
        db.flush()
        complaint = Complaint(
            user_id=owner.id,
            title="강의실 조명 고장",
            content="조명이 켜지지 않습니다.",
            expectation="조명 교체를 요청합니다.",
            status=complaint_status,
            location="공학관 201호",
            occurred_at=datetime.datetime(2026, 6, 24, 10, 0),
        )
        db.add(complaint)
        db.commit()
        owner_id = owner.id
        other_user_id = other_user.id
        complaint_id = complaint.id

    def override_get_db():
        with testing_session() as db:
            yield db

    active_user_id = {"value": owner_id}

    def override_current_user():
        with testing_session() as db:
            return db.get(User, active_user_id["value"])

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    return (
        TestClient(app),
        testing_session,
        complaint_id,
        active_user_id,
        other_user_id,
    )


def test_owner_can_create_feedback_for_resolved_complaint():
    client, testing_session, complaint_id, _, _ = _setup_app()

    response = client.post(
        f"/complaints/{complaint_id}/feedback",
        json={"rating": 5, "comment": "빠르게 처리해 주셔서 감사합니다."},
    )

    assert response.status_code == 201
    assert response.json()["rating"] == 5
    with testing_session() as db:
        saved = db.query(Feedback).one()
        assert saved.comment == "빠르게 처리해 주셔서 감사합니다."


def test_feedback_requires_resolved_complaint():
    client, _, complaint_id, _, _ = _setup_app(
        ComplaintStatus.IN_PROGRESS
    )

    response = client.post(
        f"/complaints/{complaint_id}/feedback",
        json={"rating": 4, "comment": "아직 처리 중입니다."},
    )

    assert response.status_code == 409


def test_duplicate_feedback_is_rejected():
    client, _, complaint_id, _, _ = _setup_app()
    first_response = client.post(
        f"/complaints/{complaint_id}/feedback",
        json={"rating": 4},
    )
    assert first_response.status_code == 201

    response = client.post(
        f"/complaints/{complaint_id}/feedback",
        json={"rating": 5},
    )

    assert response.status_code == 409


def test_feedback_rating_must_be_between_one_and_five():
    client, _, complaint_id, _, _ = _setup_app()

    response = client.post(
        f"/complaints/{complaint_id}/feedback",
        json={"rating": 6},
    )

    assert response.status_code == 422


def test_owner_can_read_and_update_feedback():
    client, _, complaint_id, _, _ = _setup_app()
    create_response = client.post(
        f"/complaints/{complaint_id}/feedback",
        json={"rating": 3, "comment": "보통입니다."},
    )
    assert create_response.status_code == 201

    update_response = client.patch(
        f"/complaints/{complaint_id}/feedback",
        json={"rating": 5, "comment": "다시 보니 만족스럽습니다."},
    )
    assert update_response.status_code == 200
    assert update_response.json()["rating"] == 5

    get_response = client.get(
        f"/complaints/{complaint_id}/feedback"
    )
    assert get_response.status_code == 200
    assert get_response.json()["comment"] == "다시 보니 만족스럽습니다."


def test_other_user_cannot_access_feedback():
    client, _, complaint_id, active_user_id, other_user_id = _setup_app()
    create_response = client.post(
        f"/complaints/{complaint_id}/feedback",
        json={"rating": 5},
    )
    assert create_response.status_code == 201

    active_user_id["value"] = other_user_id
    response = client.get(
        f"/complaints/{complaint_id}/feedback"
    )

    assert response.status_code == 404
