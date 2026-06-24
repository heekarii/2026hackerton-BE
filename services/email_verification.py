from __future__ import annotations

import datetime
import hashlib
import hmac
import os
import secrets
import smtplib
import threading
from dataclasses import dataclass
from email.message import EmailMessage

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


class VerificationRateLimitError(EmailVerificationError):
    pass


class EmailDeliveryError(EmailVerificationError):
    pass


@dataclass
class VerificationChallenge:
    code_hash: str
    expires_at: datetime.datetime
    last_sent_at: datetime.datetime
    attempts: int = 0


_challenges: dict[str, VerificationChallenge] = {}
_debug_codes: dict[str, str] = {}
_lock = threading.Lock()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _secret_key() -> str:
    secret = os.getenv("EMAIL_VERIFICATION_SECRET") or os.getenv("JWT_SECRET_KEY")
    if not secret:
        raise EmailVerificationError(
            "EMAIL_VERIFICATION_SECRET 또는 JWT_SECRET_KEY 환경변수가 필요합니다."
        )
    return secret


def _allowed_domains() -> set[str]:
    configured = os.getenv("SCHOOL_EMAIL_DOMAINS", "university.ac.kr")
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


def _hash_code(email: str, code: str) -> str:
    value = f"{email}:{code}".encode()
    return hmac.new(_secret_key().encode(), value, hashlib.sha256).hexdigest()


def _send_email(email: str, code: str) -> None:
    if os.getenv("EMAIL_VERIFICATION_DEBUG", "false").lower() == "true":
        print(f"[EMAIL_VERIFICATION_DEBUG] {email} 인증번호: {code}")
        return

    host = os.getenv("SMTP_HOST")
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    from_email = os.getenv("SMTP_FROM_EMAIL") or username
    if not host or not from_email:
        raise EmailDeliveryError("SMTP 환경변수가 설정되지 않았습니다.")

    port = int(os.getenv("SMTP_PORT", "587"))
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    message = EmailMessage()
    message["Subject"] = "[캠퍼스 민원] 이메일 인증번호"
    message["From"] = from_email
    message["To"] = email
    message.set_content(
        f"회원가입 인증번호는 {code}입니다.\n"
        f"{os.getenv('EMAIL_VERIFICATION_CODE_EXPIRE_MINUTES', '10')}분 안에 입력해 주세요."
    )

    try:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            if use_tls:
                smtp.starttls()
            if username and password:
                smtp.login(username, password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise EmailDeliveryError("인증 메일 전송에 실패했습니다.") from exc


def send_verification_code(email: str) -> None:
    normalized = validate_school_email(email)
    now = _now()
    resend_seconds = int(os.getenv("EMAIL_VERIFICATION_RESEND_SECONDS", "60"))
    expires_minutes = int(
        os.getenv("EMAIL_VERIFICATION_CODE_EXPIRE_MINUTES", "10")
    )

    with _lock:
        existing = _challenges.get(normalized)
        if existing and (now - existing.last_sent_at).total_seconds() < resend_seconds:
            raise VerificationRateLimitError(
                f"인증번호는 {resend_seconds}초 후 다시 요청할 수 있습니다."
            )

        code = f"{secrets.randbelow(1_000_000):06d}"
        challenge = VerificationChallenge(
            code_hash=_hash_code(normalized, code),
            expires_at=now + datetime.timedelta(minutes=expires_minutes),
            last_sent_at=now,
        )
        _challenges[normalized] = challenge
        if os.getenv("EMAIL_VERIFICATION_DEBUG", "false").lower() == "true":
            _debug_codes[normalized] = code

    try:
        _send_email(normalized, code)
    except EmailDeliveryError:
        with _lock:
            if _challenges.get(normalized) is challenge:
                _challenges.pop(normalized, None)
                _debug_codes.pop(normalized, None)
        raise


def verify_code(email: str, code: str) -> str:
    normalized = validate_school_email(email)
    now = _now()
    max_attempts = int(os.getenv("EMAIL_VERIFICATION_MAX_ATTEMPTS", "5"))

    with _lock:
        challenge = _challenges.get(normalized)
        if challenge is None:
            raise VerificationCodeError("인증번호를 먼저 요청해 주세요.")
        if challenge.expires_at <= now:
            _challenges.pop(normalized, None)
            _debug_codes.pop(normalized, None)
            raise VerificationCodeError("인증번호가 만료되었습니다.")
        if challenge.attempts >= max_attempts:
            _challenges.pop(normalized, None)
            _debug_codes.pop(normalized, None)
            raise VerificationCodeError("인증 시도 횟수를 초과했습니다.")

        challenge.attempts += 1
        if not hmac.compare_digest(challenge.code_hash, _hash_code(normalized, code)):
            raise VerificationCodeError("인증번호가 올바르지 않습니다.")
        _challenges.pop(normalized, None)
        _debug_codes.pop(normalized, None)

    return create_verification_token(normalized)


def create_verification_token(email: str) -> str:
    now = _now()
    expires_minutes = int(
        os.getenv("EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES", "30")
    )
    payload = {
        "sub": normalize_email(email),
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
            "이메일 인증 정보가 유효하지 않거나 만료되었습니다."
        ) from exc

    if (
        payload.get("purpose") != TOKEN_PURPOSE
        or payload.get("sub") != normalize_email(email)
    ):
        raise VerificationCodeError("인증한 이메일과 회원가입 이메일이 일치하지 않습니다.")


def get_debug_verification_code(email: str) -> str | None:
    """테스트 환경에서만 현재 인증번호를 찾기 위한 헬퍼."""
    if os.getenv("EMAIL_VERIFICATION_DEBUG", "false").lower() != "true":
        return None
    normalized = normalize_email(email)
    return _debug_codes.get(normalized)
