from __future__ import annotations
import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Notification(Base):
    """처리 현황 알림.

    관리자가 민원 상태를 변경하면 해당 민원 작성자에게 알림이 생성된다.
    (기존 models.py 를 건드리지 않기 위해 별도 파일에 정의한 신규 모델)
    """
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)  # 알림 수신자(민원인)
    complaint_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("complaints.id"), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, nullable=False)
