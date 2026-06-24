import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "test-secret-key"
os.environ["EMAIL_VERIFICATION_SECRET"] = "test-email-verification-secret"
os.environ["SCHOOL_EMAIL_DOMAINS"] = "university.ac.kr"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import get_db
from main import app
from models import User
from services.email_verification import create_verification_token


engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
User.__table__.create(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def test_signup_login_and_me():
    email = "student@university.ac.kr"
    signup_response = client.post(
        "/auth/signup",
        json={
            "email": email,
            "password": "password123!",
            "nickname": "학생",
            "student_id": "20260001",
            "verification_token": create_verification_token(email),
        },
    )
    assert signup_response.status_code == 201
    assert signup_response.json()["email"] == email
    assert signup_response.json()["role"] == "student"
    assert "hashed_password" not in signup_response.json()

    login_response = client.post(
        "/auth/login",
        json={"email": email, "password": "password123!"},
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]

    me_response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["student_id"] == "20260001"


def test_duplicate_email_is_rejected():
    email = "student@university.ac.kr"
    response = client.post(
        "/auth/signup",
        json={
            "email": email,
            "password": "another-password",
            "nickname": "중복",
            "student_id": "20260002",
            "verification_token": create_verification_token(email),
        },
    )
    assert response.status_code == 409


def test_wrong_password_is_rejected():
    response = client.post(
        "/auth/login",
        json={
            "email": "student@university.ac.kr",
            "password": "wrong-password",
        },
    )
    assert response.status_code == 401


def test_email_check_returns_signup_token():
    email = "new-student@university.ac.kr"
    send_response = client.post(
        "/auth/email-verification/send",
        json={"email": email},
    )
    assert send_response.status_code == 200
    assert send_response.json()["verified"] is True
    assert send_response.json()["verification_token"]


def test_non_school_email_is_rejected():
    response = client.post(
        "/auth/email-verification/send",
        json={"email": "student@gmail.com"},
    )
    assert response.status_code == 400


def test_signup_requires_matching_verification_token():
    response = client.post(
        "/auth/signup",
        json={
            "email": "other@university.ac.kr",
            "password": "password123!",
            "nickname": "다른 학생",
            "verification_token": create_verification_token(
                "verified@university.ac.kr"
            ),
        },
    )
    assert response.status_code == 400
