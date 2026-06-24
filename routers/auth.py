from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth import authenticate_user, create_access_token, get_current_user, hash_password
from database import get_db
from models import User, UserRole
from schemas import (
    EmailVerificationResponse,
    EmailVerificationSendRequest,
    LoginRequest,
    SignUpRequest,
    TokenResponse,
    UserResponse,
)
from services.email_verification import (
    EmailVerificationError,
    InvalidSchoolEmailError,
    VerificationCodeError,
    create_verification_token,
    validate_verification_token,
    validate_school_email,
)


router = APIRouter(prefix="/auth", tags=["Auth"])


def _issue_token(user: User) -> TokenResponse:
    access_token, expires_in = create_access_token(user.id)
    return TokenResponse(
        access_token=access_token,
        expires_in=expires_in,
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/email-verification/send",
    response_model=EmailVerificationResponse,
    summary="학교 이메일 확인",
)
def send_email_verification(
    payload: EmailVerificationSendRequest,
    db: Session = Depends(get_db),
) -> EmailVerificationResponse:
    email = payload.email.lower()
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 가입된 이메일입니다.",
        )

    try:
        validate_school_email(email)
        verification_token = create_verification_token(email)
    except InvalidSchoolEmailError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except EmailVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    return EmailVerificationResponse(verification_token=verification_token)


@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="회원가입",
)
def signup(payload: SignUpRequest, db: Session = Depends(get_db)) -> User:
    email = payload.email.lower()
    try:
        validate_verification_token(payload.verification_token, email)
    except VerificationCodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except EmailVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    filters = [User.email == email]
    if payload.student_id:
        filters.append(User.student_id == payload.student_id)

    existing_user = db.scalar(select(User).where(or_(*filters)))
    if existing_user:
        detail = (
            "이미 가입된 이메일입니다."
            if existing_user.email == email
            else "이미 등록된 학번입니다."
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

    user = User(
        email=email,
        hashed_password=hash_password(payload.password),
        nickname=payload.nickname,
        student_id=payload.student_id,
        role=UserRole.STUDENT,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 등록된 회원 정보입니다.",
        )
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse, summary="로그인")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = authenticate_user(db, payload.email, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _issue_token(user)


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Swagger OAuth2 로그인",
)
def swagger_login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> TokenResponse:
    user = authenticate_user(db, form_data.username, form_data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _issue_token(user)


@router.get("/me", response_model=UserResponse, summary="내 정보 조회")
def read_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
