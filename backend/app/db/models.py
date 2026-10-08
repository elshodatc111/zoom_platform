from datetime import datetime

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, UTCDateTime, utcnow

# LessonBlock.status: reserved -> creating -> created -> finished | failed | cancelled | missed
ACTIVE_BLOCK_STATES = ("reserved", "creating", "created")
# LessonSession.status: active -> completed | cancelled | failed


class Admin(Base):
    __tablename__ = "admins"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Teacher(Base):
    __tablename__ = "teachers"
    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(128))
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, nullable=True)
    tg_username: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    sessions: Mapped[list["LessonSession"]] = relationship(back_populates="teacher")


class ZoomAccount(Base):
    __tablename__ = "zoom_accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    email: Mapped[str] = mapped_column(String(128))  # meeting yaratiladigan Zoom foydalanuvchi
    zoom_account_id: Mapped[str] = mapped_column(String(64))
    client_id: Mapped[str] = mapped_column(String(128))
    client_secret_enc: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(16), default="unknown")  # unknown|ok|error
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class LessonSession(Base):
    __tablename__ = "lesson_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"), index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    blocks_count: Mapped[int] = mapped_column(Integer)
    block_minutes: Mapped[int] = mapped_column(Integer, default=40)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    actual_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stop_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)

    teacher: Mapped[Teacher] = relationship(back_populates="sessions")
    blocks: Mapped[list["LessonBlock"]] = relationship(
        back_populates="session", order_by="LessonBlock.idx", cascade="all, delete-orphan"
    )

    @property
    def planned_minutes(self) -> int:
        return self.blocks_count * self.block_minutes


class LessonBlock(Base):
    __tablename__ = "lesson_blocks"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("lesson_sessions.id"), index=True)
    idx: Mapped[int] = mapped_column(Integer)  # 1 dan boshlanadi
    account_id: Mapped[int | None] = mapped_column(ForeignKey("zoom_accounts.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(16), default="reserved", index=True)
    create_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)  # meeting yaratilish vaqti
    planned_start: Mapped[datetime] = mapped_column(UTCDateTime)
    planned_end: Mapped[datetime] = mapped_column(UTCDateTime)
    meeting_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    join_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    passcode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_real_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)

    session: Mapped[LessonSession] = relationship(back_populates="blocks")
    account: Mapped[ZoomAccount | None] = relationship()


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    actor: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)


class AppSetting(Base):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
