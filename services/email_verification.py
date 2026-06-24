from __future__ import annotations

import datetime
import os

import jwt
from jwt.exceptions import InvalidTokenError


ALGORITHM = "HS256"
TOKEN_PURPOSE = "email_verification"


class EmailVerificationError(Exception):
    pass


class InvalidSchoolEmailError(EmailVerificationError):
    pass


class VerificationCodeError(EmailVerificationError):
    pass


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _secret_key() -> str:
    secret = os.getenv("EMAIL_VERIFICATION_SECRET") or os.getenv("JWT_SECRET_KEY")
    if not secret:
        raise EmailVerificationError(
            "EMAIL_VERIFICATION_SECRET 또는 JWT_SECRET_KEY 환경변수가 필요합니다."
        )
    return secret


def _allowed_domains() -> set[str]:
    configured = os.getenv("SCHOOL_EMAIL_DOMAINS", "sju.ac.kr")
    return {
        domain.strip().lower().lstrip("@")
        for domain in configured.split(",")
        if domain.strip()
    }


def validate_school_email(email: str) -> str:
    normalized = normalize_email(email)
    domain = normalized.rsplit("@", 1)[-1]
    allowed_domains = _allowed_domains()
    if allowed_domains and domain not in allowed_domains:
        raise InvalidSchoolEmailError("허용된 학교 이메일 도메인이 아닙니다.")
    return normalized


def create_verification_token(email: str) -> str:
    normalized = normalize_email(email)
    now = datetime.datetime.now(datetime.timezone.utc)
    expires_minutes = int(
        os.getenv("EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES", "30")
    )
    payload = {
        "sub": normalized,
        "purpose": TOKEN_PURPOSE,
        "iat": now,
        "exp": now + datetime.timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, _secret_key(), algorithm=ALGORITHM)


def validate_verification_token(token: str, email: str) -> None:
    try:
        payload = jwt.decode(token, _secret_key(), algorithms=[ALGORITHM])
    except InvalidTokenError as exc:
        raise VerificationCodeError(
            "이메일 확인 정보가 유효하지 않거나 만료되었습니다."
        ) from exc

    if (
        payload.get("purpose") != TOKEN_PURPOSE
        or payload.get("sub") != normalize_email(email)
    ):
        raise VerificationCodeError("확인한 이메일과 회원가입 이메일이 일치하지 않습니다.")
